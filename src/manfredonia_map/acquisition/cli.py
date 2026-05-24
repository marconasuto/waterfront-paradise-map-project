"""Click subcommands grouped under ``mfd-map acquire``."""

from __future__ import annotations

import logging
from pathlib import Path

import click
import geopandas as gpd

from manfredonia_map.acquisition import base, emodnet, http, istat, mase, osm, tinitaly
from manfredonia_map.paths import CONFIG_DIR, DATA_RAW

logger = logging.getLogger(__name__)


@click.group(name="acquire", help="Download raw data into data/raw/.")
def acquire() -> None:
    """Group of acquisition subcommands."""


def _bbox_from_aoi(aoi_path: Path) -> tuple[float, float, float, float]:
    """Return ``(west, south, east, north)`` from a single-feature GeoJSON."""
    gdf = gpd.read_file(aoi_path)
    minx, miny, maxx, maxy = gdf.total_bounds
    return (float(minx), float(miny), float(maxx), float(maxy))


def _persist_osm_layer(
    gdf: gpd.GeoDataFrame,
    out_path: Path,
    *,
    spec: osm.OsmLayerSpec,
    bbox: tuple[float, float, float, float],
) -> base.Provenance:
    """Write the GeoJSON + provenance sidecar for an OSM layer.

    pyogrio (the GeoPandas backend) handles nested-type columns (lists,
    dicts from osmnx) natively, serialising them as JSON arrays / objects
    inside the GeoJSON ``properties``. No manual coercion required.
    """
    if gdf.empty:
        raise click.ClickException(
            f"Overpass returned 0 features for source={spec.source_id} bbox={bbox}."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_path, driver="GeoJSON")
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="OpenStreetMap contributors",
        dataset=spec.dataset,
        url="https://overpass-api.de/api/interpreter",
        access_method="Overpass via osmnx",
        license="ODbL-1.0",
        accessed_at=base.now_iso_utc(),
        bbox=bbox,
        query={"tags": spec.tags},
    )
    stamped = base.stamp_provenance(prov, out_path)
    base.write_provenance(stamped, out_path.with_suffix(".provenance.json"))
    click.echo(f"Wrote {out_path}  ({len(gdf)} features)")
    return stamped


@acquire.group(name="osm")
def acquire_osm() -> None:
    """Download OSM layers configured in ``osm.LAYERS``."""


def _default_aoi_path() -> Path:
    return CONFIG_DIR / "aoi_buffered.geojson"


def _out_path_for(layer: str) -> Path:
    spec = osm.LAYERS[layer]
    return DATA_RAW / spec.source_id / f"{layer}.geojson"


@acquire_osm.command(name="layer")
@click.argument("layer", type=click.Choice(sorted(osm.LAYERS), case_sensitive=False))
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_aoi_path,
    show_default="config/aoi_buffered.geojson",
    help="GeoJSON whose bounding box defines the Overpass query area.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination GeoJSON path. Defaults to data/raw/<source_id>/<layer>.geojson.",
)
def acquire_osm_layer(layer: str, aoi_path: Path, out_path: Path | None) -> None:
    """Fetch a single OSM layer (e.g. ``coastline``, ``roads``, ``wetlands``)."""
    spec = osm.LAYERS[layer]
    out = out_path if out_path is not None else _out_path_for(layer)
    bbox = _bbox_from_aoi(aoi_path)
    logger.info("Fetching OSM layer %s for bbox=%s", layer, bbox)
    gdf = osm.fetch_layer(layer, bbox)
    _persist_osm_layer(gdf, out, spec=spec, bbox=bbox)


@acquire_osm.command(name="all")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_aoi_path,
    show_default="config/aoi_buffered.geojson",
    help="GeoJSON whose bounding box defines the Overpass query area.",
)
@click.option(
    "--skip",
    "skip_layers",
    multiple=True,
    type=click.Choice(sorted(osm.LAYERS), case_sensitive=False),
    help="Layers to skip (may be repeated).",
)
def acquire_osm_all(aoi_path: Path, skip_layers: tuple[str, ...]) -> None:
    """Fetch every OSM layer in ``osm.LAYERS`` sequentially."""
    bbox = _bbox_from_aoi(aoi_path)
    failures: list[str] = []
    for layer in sorted(osm.LAYERS):
        if layer in skip_layers:
            click.echo(f"--- skip osm:{layer}")
            continue
        click.echo(f"--- acquire osm:{layer}")
        try:
            spec = osm.LAYERS[layer]
            out = _out_path_for(layer)
            gdf = osm.fetch_layer(layer, bbox)
            _persist_osm_layer(gdf, out, spec=spec, bbox=bbox)
        except click.ClickException as exc:
            logger.warning("osm:%s failed: %s", layer, exc.message)
            failures.append(layer)
    if failures:
        raise click.ClickException(f"acquisitions failed: {', '.join(failures)}")


# --- ISTAT --------------------------------------------------------------

@acquire.group(name="istat")
def acquire_istat() -> None:
    """Download ISTAT national datasets."""


@acquire_istat.command(name="boundaries")
@click.option("--year", type=int, default=2024, show_default=True)
@click.option(
    "--generalized/--detailed",
    default=True,
    show_default=True,
    help="Use the generalized (small, ~3 MB) or detailed (~70 MB) bundle.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination zip path. Defaults to data/raw/istat_admin/<filename>.",
)
def acquire_istat_boundaries(year: int, generalized: bool, out_path: Path | None) -> None:
    """Download ISTAT administrative boundaries (regioni/province/comuni)."""
    spec = istat.IstatBoundariesSpec(year=year, generalized=generalized)
    out = out_path if out_path is not None else DATA_RAW / "istat_admin" / spec.out_filename
    logger.info("Downloading %s -> %s", spec.url, out)
    sha = http.download_file(
        spec.url,
        out,
        headers={"User-Agent": "manfredonia-map/0.0.1 (acquisition pipeline)"},
    )
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="ISTAT",
        dataset=spec.dataset,
        url=spec.url,
        access_method="HTTPS",
        license="CC-BY-3.0",
        accessed_at=base.now_iso_utc(),
        year_data=year,
        sha256=sha,
    )
    stamped = base.stamp_provenance(prov, out)
    base.write_provenance(stamped, out.with_suffix(out.suffix + ".provenance.json"))
    click.echo(f"Wrote {out} ({stamped.byte_count} bytes)")
    click.echo(f"Wrote {out.with_suffix(out.suffix + '.provenance.json')}")


# --- MASE ---------------------------------------------------------------

@acquire.group(name="mase")
def acquire_mase() -> None:
    """Download MASE datasets (Ministero dell'Ambiente e della Sicurezza Energetica)."""


@acquire_mase.command(name="natura2000")
@click.option("--year", type=int, default=2025, show_default=True)
@click.option(
    "--variant",
    type=click.Choice(["daticartografici", "tuttiicampi"]),
    default="tuttiicampi",
    show_default=True,
    help="`tuttiicampi` is the full standard-data-form fields version.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination zip path. Defaults to data/raw/mase_natura2000/<filename>.",
)
def acquire_mase_natura2000(year: int, variant: str, out_path: Path | None) -> None:
    """Download MASE Rete Natura 2000 (SIC/ZSC/ZPS) national bundle."""
    spec = mase.MaseNatura2000Spec(year=year, variant=variant)  # type: ignore[arg-type]
    out = (
        out_path
        if out_path is not None
        else DATA_RAW / "mase_natura2000" / spec.out_filename
    )
    logger.info("Downloading %s -> %s", spec.url, out)
    sha = http.download_file(
        spec.url,
        out,
        headers={"User-Agent": "manfredonia-map/0.0.1 (acquisition pipeline)"},
    )
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="MASE",
        dataset=spec.dataset,
        url=spec.url,
        access_method="HTTPS",
        license="non-commercial, cite source",
        accessed_at=base.now_iso_utc(),
        year_data=year,
        sha256=sha,
    )
    stamped = base.stamp_provenance(prov, out)
    base.write_provenance(stamped, out.with_suffix(out.suffix + ".provenance.json"))
    click.echo(f"Wrote {out} ({stamped.byte_count} bytes)")
    click.echo(f"Wrote {out.with_suffix(out.suffix + '.provenance.json')}")


# --- TINITALY -----------------------------------------------------------

@acquire.group(name="tinitaly")
def acquire_tinitaly() -> None:
    """Download INGV TINITALY DEM tiles."""


@acquire_tinitaly.command(name="tile")
@click.argument("tile_id", type=str)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination zip path. Defaults to data/raw/tinitaly/<tile_id>.zip.",
)
@click.option(
    "--verify-ssl/--no-verify-ssl",
    "verify_ssl",
    default=False,
    show_default=True,
    help="TINITALY ships a self-signed cert chain; default skips "
    "verification. Pair with --expected-sha256 in CI.",
)
@click.option(
    "--expected-sha256",
    "expected_sha256",
    type=str,
    default=None,
    help="Optional SHA-256 of the expected download (verified after stream).",
)
def acquire_tinitaly_tile(
    tile_id: str,
    out_path: Path | None,
    verify_ssl: bool,
    expected_sha256: str | None,
) -> None:
    """Download one TINITALY/1.1 tile (e.g. ``e41005_s10``)."""
    spec = tinitaly.TinitalyTileSpec(tile_id=tile_id)
    out = (
        out_path
        if out_path is not None
        else DATA_RAW / "tinitaly" / spec.out_filename
    )
    if not verify_ssl:
        logger.warning(
            "SSL verification disabled for %s (TINITALY uses a self-signed cert).",
            spec.url,
        )
    logger.info("Downloading %s -> %s", spec.url, out)
    sha = http.download_file(
        spec.url,
        out,
        headers={"User-Agent": "manfredonia-map/0.0.1 (acquisition pipeline)"},
        verify_ssl=verify_ssl,
        expected_sha256=expected_sha256,
    )
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="INGV",
        dataset=spec.dataset,
        url=spec.url,
        access_method="HTTPS",
        license="CC-BY-4.0",
        accessed_at=base.now_iso_utc(),
        sha256=sha,
    )
    stamped = base.stamp_provenance(prov, out)
    base.write_provenance(stamped, out.with_suffix(out.suffix + ".provenance.json"))
    click.echo(f"Wrote {out} ({stamped.byte_count} bytes)")
    click.echo(f"Wrote {out.with_suffix(out.suffix + '.provenance.json')}")


# --- EMODnet -----------------------------------------------------------

@acquire.group(name="emodnet")
def acquire_emodnet() -> None:
    """Download EMODnet datasets."""


@acquire_emodnet.command(name="bathymetry")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi_buffered.geojson",
    show_default=True,
    help="GeoJSON whose bounding box defines the WCS GetCoverage bbox.",
)
@click.option(
    "--res-deg",
    type=float,
    default=emodnet.NATIVE_RES_DEG,
    show_default=True,
    help="Output resolution in degrees (default = 1/16 arc-minute = native).",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination GeoTIFF. Defaults to data/raw/emodnet_bathymetry/<filename>.",
)
def acquire_emodnet_bathymetry(
    aoi_path: Path,
    res_deg: float,
    out_path: Path | None,
) -> None:
    """Download EMODnet Bathymetry DTM 2024 clipped to AOI bbox via WCS."""
    bbox = _bbox_from_aoi(aoi_path)
    spec = emodnet.EmodnetBathymetrySpec(bbox=bbox, res_deg=res_deg)
    out = (
        out_path
        if out_path is not None
        else DATA_RAW / "emodnet_bathymetry" / spec.out_filename
    )
    logger.info("Downloading %s -> %s", spec.url, out)
    sha = http.download_file(
        spec.url,
        out,
        headers={"User-Agent": "manfredonia-map/0.0.1 (acquisition pipeline)"},
        timeout_s=300.0,
    )
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="EMODnet Bathymetry Consortium",
        dataset=spec.dataset,
        url=spec.url,
        access_method="WCS GetCoverage",
        license="CC-BY-4.0",
        accessed_at=base.now_iso_utc(),
        bbox=bbox,
        query={"res_deg": res_deg, "coverage": spec.coverage},
        year_data=2024,
        sha256=sha,
    )
    stamped = base.stamp_provenance(prov, out)
    base.write_provenance(stamped, out.with_suffix(out.suffix + ".provenance.json"))
    click.echo(f"Wrote {out} ({stamped.byte_count} bytes)")
    click.echo(f"Wrote {out.with_suffix(out.suffix + '.provenance.json')}")
