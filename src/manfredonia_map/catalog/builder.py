"""Walk the project tree and build the data catalog.

Reads:
- ``data/raw/**/*.provenance.json`` — every acquisition sidecar.
- ``data/processed/*.geojson`` — every per-layer processed vector.
- ``data/processed/*_8bit.tif`` — every 8-bit COG produced by raster
  processing (including hillshade derivations).
- ``config/aoi*.geojson`` — the three AOI shapes + the alias.

Outputs a deterministic ``data/catalog.yaml`` validated against the
pydantic models in :mod:`manfredonia_map.catalog.models`. Atomic write
(tempfile + rename, ``sort_keys=True``).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
import rasterio
import yaml

from manfredonia_map.catalog import models
from manfredonia_map.paths import CONFIG_DIR, DATA_PROCESSED, DATA_RAW
from manfredonia_map.processing import raster as raster_module

#: Suffix that marks a published 8-bit COG raster output.
_RASTER_SUFFIX = "_8bit.tif"
#: Suffix that marks a hillshade-derived raster output.
_HILLSHADE_SUFFIX = "_hillshade_8bit.tif"


def _now_iso_utc() -> str:
    """Return the current UTC time as ISO 8601 (matches acquisition.base)."""
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat()


def _sha256_of_file(path: Path) -> str:
    """SHA-256 of a file's contents (streaming)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_sources(data_raw: Path = DATA_RAW) -> list[models.Source]:
    """Find every ``*.provenance.json`` sidecar under ``data_raw``."""
    sources: list[models.Source] = []
    for sidecar in sorted(data_raw.rglob("*.provenance.json")):
        prov = json.loads(sidecar.read_text(encoding="utf-8"))
        sources.append(
            models.Source(
                source_id=prov["source_id"],
                publisher=prov["publisher"],
                dataset=prov["dataset"],
                url=prov["url"],
                access_method=prov["access_method"],
                license=prov["license"],
                accessed_at=prov["accessed_at"],
                raw_path=str(Path(prov["raw_path"]).relative_to(_repo_root(data_raw))
                             if Path(prov["raw_path"]).is_absolute()
                             else prov["raw_path"]),
                sha256=prov["sha256"],
                byte_count=int(prov["byte_count"]),
                bbox=(tuple(prov["bbox"]) if prov.get("bbox") else None),  # type: ignore[arg-type]
                year_data=prov.get("year_data"),
            )
        )
    return sources


def _repo_root(known_dir: Path) -> Path:
    """Walk upward from a known directory to find the repo root."""
    p = known_dir.resolve()
    for ancestor in [p, *p.parents]:
        if (ancestor / "pyproject.toml").exists():
            return ancestor
    return p


def _rel(path: Path, repo_root: Path) -> str:
    """Format ``path`` relative to ``repo_root`` (deterministic across machines)."""
    p = path.resolve()
    try:
        return str(p.relative_to(repo_root))
    except ValueError:
        return str(p)


def _inspect_vector(
    geojson_path: Path,
) -> tuple[int, list[str], str | None, str | None, int | None]:
    """Return ``(feature_count, geom_types_sorted, source_id, category, year_data)``."""
    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        return (0, [], None, None, None)
    geom_types = sorted({str(t) for t in gdf.geometry.geom_type.tolist()})

    def _scalar(col: str) -> object | None:
        if col not in gdf.columns:
            return None
        s = gdf[col].dropna()
        return s.iloc[0] if not s.empty else None

    source_id = _scalar("source_id")
    category = _scalar("category")
    year_data = _scalar("year_data")
    return (
        len(gdf),
        geom_types,
        str(source_id) if source_id is not None else None,
        str(category) if category is not None else None,
        int(year_data) if year_data is not None else None,
    )


def discover_vector_layers(
    processed_dir: Path = DATA_PROCESSED, repo_root: Path | None = None,
) -> list[models.VectorLayer]:
    """One :class:`VectorLayer` per ``*.geojson`` directly under ``processed_dir``."""
    root = repo_root or _repo_root(processed_dir)
    layers: list[models.VectorLayer] = []
    for geojson_path in sorted(processed_dir.glob("*.geojson")):
        layer_id = geojson_path.stem
        feature_count, geom_types, source_id, category, year_data = _inspect_vector(geojson_path)
        layers.append(
            models.VectorLayer(
                layer_id=layer_id,
                source_id=source_id,
                processed_path=_rel(geojson_path, root),
                processed_sha256=_sha256_of_file(geojson_path),
                feature_count=feature_count,
                geom_types=geom_types,
                category=category,
                year_data=year_data,
            )
        )
    return layers


def _raster_source_id_for(stem: str) -> str | None:
    """Look up the source_id for a processed raster filename stem."""
    # ``tinitaly_dtm_hillshade_8bit`` → base ``tinitaly_dtm``
    base = stem.removesuffix("_hillshade").removesuffix("_8bit").removesuffix("_hillshade_8bit")
    if base.endswith("_hillshade"):
        base = base.removesuffix("_hillshade")
    spec = raster_module.PROCESSORS.get(base)
    return spec.source_id if spec is not None else None


def _inspect_raster(tif_path: Path) -> tuple[int, int, int, str]:
    """Return ``(width, height, band_count, crs_string)``."""
    with rasterio.open(tif_path) as ds:
        crs = ds.crs.to_string() if ds.crs is not None else ""
        return ds.width, ds.height, ds.count, crs


def discover_raster_layers(
    processed_dir: Path = DATA_PROCESSED, repo_root: Path | None = None,
) -> list[models.RasterLayer]:
    """One :class:`RasterLayer` per published 8-bit COG under ``processed_dir``."""
    root = repo_root or _repo_root(processed_dir)
    layers: list[models.RasterLayer] = []
    for tif in sorted(processed_dir.glob(f"*{_RASTER_SUFFIX}")):
        stem = tif.stem
        width, height, bands, crs = _inspect_raster(tif)
        source_id = _raster_source_id_for(stem)
        derived_from: str | None = None
        layer_id = stem.removesuffix("_8bit")
        if stem.endswith(_HILLSHADE_SUFFIX.removesuffix(".tif")):
            base = stem.removesuffix("_hillshade_8bit")
            derived_from = base
            layer_id = f"{base}_hillshade"
        layers.append(
            models.RasterLayer(
                layer_id=layer_id,
                source_id=source_id,
                processed_path=_rel(tif, root),
                processed_sha256=_sha256_of_file(tif),
                width=width,
                height=height,
                bands=bands,
                crs=crs,
                derived_from=derived_from,
            )
        )
    return layers


def _read_build_settings(config_dir: Path) -> tuple[float, float, str]:
    """Pull ``buffer_m`` / ``coastal_band_m`` / alias from ``config/build.yaml``."""
    p = config_dir / "build.yaml"
    if not p.exists():
        return (1000.0, 2000.0, "near_coast")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    aoi = cfg.get("aoi") or {}
    return (
        float(aoi.get("buffer_m", 1000.0)),
        float(aoi.get("coastal_band_m", 2000.0)),
        str(aoi.get("alias", "near_coast")),
    )


def build_aoi_info(
    config_dir: Path = CONFIG_DIR, repo_root: Path | None = None,
) -> models.AoiInfo:
    """Snapshot the AOI shapes + the build settings as an :class:`AoiInfo`."""
    root = repo_root or _repo_root(config_dir)
    buffer_m, coastal_band_m, _alias = _read_build_settings(config_dir)
    source = config_dir / "aoi_source.geojson"
    buffered = config_dir / "aoi_buffered.geojson"
    near_coast = config_dir / "aoi_near_coast.geojson"
    alias = config_dir / "aoi.geojson"
    missing = [p for p in (source, buffered, near_coast, alias) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"missing AOI files in {config_dir}: {[str(p) for p in missing]}"
        )
    return models.AoiInfo(
        source_path=_rel(source, root),
        buffered_path=_rel(buffered, root),
        near_coast_path=_rel(near_coast, root),
        alias_path=_rel(alias, root),
        buffer_m=buffer_m,
        coastal_band_m=coastal_band_m,
        source_sha256=_sha256_of_file(source),
        buffered_sha256=_sha256_of_file(buffered),
        near_coast_sha256=_sha256_of_file(near_coast),
        alias_sha256=_sha256_of_file(alias),
    )


def assemble(
    *,
    config_dir: Path = CONFIG_DIR,
    data_raw: Path = DATA_RAW,
    processed_dir: Path = DATA_PROCESSED,
    repo_root: Path | None = None,
    now: str | None = None,
) -> models.Catalog:
    """Build and return the full :class:`Catalog` model."""
    root = repo_root or _repo_root(processed_dir)
    return models.Catalog(
        version=models.SCHEMA_VERSION,
        generated_at=now or _now_iso_utc(),
        aoi=build_aoi_info(config_dir=config_dir, repo_root=root),
        sources=discover_sources(data_raw=data_raw),
        vector_layers=discover_vector_layers(processed_dir=processed_dir, repo_root=root),
        raster_layers=discover_raster_layers(processed_dir=processed_dir, repo_root=root),
    )


def write(catalog: models.Catalog, out_path: Path) -> None:
    """Atomically write ``catalog`` as deterministic YAML."""
    payload = catalog.model_dump(mode="json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out_path.name + ".", dir=out_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                payload,
                f,
                sort_keys=True,
                allow_unicode=True,
                default_flow_style=False,
            )
        os.replace(tmp, out_path)
        os.chmod(out_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(path: Path) -> models.Catalog:
    """Read + validate a catalog YAML file."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return models.Catalog.model_validate(payload)


def iter_layer_ids(catalog: models.Catalog) -> Iterable[str]:
    """Stable iteration over every layer id in the catalog."""
    yield from (lv.layer_id for lv in catalog.vector_layers)
    yield from (lr.layer_id for lr in catalog.raster_layers)
