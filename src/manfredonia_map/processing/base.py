"""Common vector-processing utilities used by every normalizer.

Every layer goes through the same pipeline:

    raw → normalize  → to_storage_crs → clip_to_aoi → make_valid → write

This module owns the *generic* steps; ``processing.normalize`` owns the
per-layer reader/normalizer functions.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

#: CRS used at storage time for vectors and Mapbox publishing. Matches
#: the rest of the pipeline (see SPECIFICATIONS.md §7).
STORAGE_CRS = "EPSG:4326"
_STORAGE_EPSG = 4326

#: CRS used for any metric analysis (buffer, area, length, ...).
ANALYSIS_CRS = "EPSG:32633"

#: Canonical column set every layer's processed GeoJSON conforms to.
#: Layer-specific extras follow these columns in the same row.
SCHEMA_COLUMNS: tuple[str, ...] = (
    "id",
    "layer_id",
    "name_it",
    "category",
    "year_data",
    "source_id",
)


def to_storage_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensure ``gdf`` is in :data:`STORAGE_CRS` (re-project if needed)."""
    if gdf.empty:
        return gdf.set_crs(STORAGE_CRS, allow_override=True)
    if gdf.crs is None:
        return gdf.set_crs(STORAGE_CRS, allow_override=True)
    if gdf.crs.to_epsg() == _STORAGE_EPSG:
        return gdf
    return gdf.to_crs(STORAGE_CRS)


def make_valid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Repair invalid geometries and drop empties.

    Returns a new GeoDataFrame; the input is not mutated.
    """
    if gdf.empty:
        return gdf
    out = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    if out.empty:
        return out
    invalid = ~out.geometry.is_valid
    if invalid.any():
        out.loc[invalid, "geometry"] = out.loc[invalid, "geometry"].make_valid()
        # make_valid can yield empty / collection results; drop those too.
        out = out[~out.geometry.is_empty]
    return out


def clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: BaseGeometry) -> gpd.GeoDataFrame:
    """Clip ``gdf`` to ``aoi`` (both in EPSG:4326)."""
    if gdf.empty:
        return gdf
    return gpd.clip(gdf, aoi)


def conform_to_schema(
    gdf: gpd.GeoDataFrame,
    *,
    layer_id: str,
    source_id: str,
    year_data: int | None,
    category: str,
    id_col: str | None = None,
    name_col: str | None = None,
    extra_columns: Iterable[str] = (),
) -> gpd.GeoDataFrame:
    """Force ``gdf`` into the canonical :data:`SCHEMA_COLUMNS` shape.

    Args:
        gdf: Input GeoDataFrame (any columns); geometry must be present.
        layer_id: Stable id of the layer in ``config/layers.yaml``.
        source_id: Stable id matching the provenance sidecar's
            ``source_id`` field.
        year_data: Year the *source data* reflects (publication year),
            from ``config/layers.yaml``.
        category: Short bucket used for styling (e.g. ``"road_primary"``,
            ``"wetland"``).
        id_col: Optional source column to use as ``id``; falls back to a
            ``"<layer_id>_<row_index>"`` synthetic id.
        name_col: Optional source column to use as ``name_it``.
        extra_columns: Source columns to preserve verbatim after the
            canonical schema columns.

    Returns:
        A new GeoDataFrame with exactly
        ``SCHEMA_COLUMNS + extras + ["geometry"]`` columns, in
        :data:`STORAGE_CRS`.
    """
    out = gdf.copy()
    if id_col is not None and id_col in out.columns:
        out["id"] = out[id_col].astype(str)
    else:
        out["id"] = [f"{layer_id}_{i}" for i in range(len(out))]
    out["layer_id"] = layer_id
    out["source_id"] = source_id
    out["category"] = category
    out["year_data"] = year_data
    out["name_it"] = (
        out[name_col].astype("string") if name_col is not None and name_col in out.columns else None
    )

    extras_present = [c for c in extra_columns if c in out.columns and c not in SCHEMA_COLUMNS]
    keep = [*SCHEMA_COLUMNS, *extras_present, "geometry"]
    result = gpd.GeoDataFrame(out[keep], geometry="geometry", crs=out.crs)
    # Preserve the input CRS verbatim — *do not* relabel it. The downstream
    # `to_storage_crs` step is responsible for any reprojection. Relabelling
    # here used to silently corrupt UTM-coordinate sources (e.g. ISTAT
    # ``_WGS84.shp`` files whose .prj is actually EPSG:32632).
    if result.crs is None:
        result = result.set_crs(STORAGE_CRS, allow_override=True)
    return result


#: Coordinate precision used in deterministic GeoJSON writes — 7 decimal
#: degrees is ≈ 1 cm at the equator, far below any source uncertainty
#: while keeping outputs byte-stable across runs.
GEOJSON_COORD_PRECISION = 7


def _round_coords(obj: object, ndigits: int) -> object:
    """Recursively round floats inside a GeoJSON coordinate structure."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, list):
        return [_round_coords(x, ndigits) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_round_coords(x, ndigits) for x in obj)
    if isinstance(obj, dict):
        return {k: _round_coords(v, ndigits) for k, v in obj.items()}
    return obj


def _gdf_to_geojson_dict(gdf: gpd.GeoDataFrame, *, coord_precision: int) -> dict[str, object]:
    """Serialize a GeoDataFrame to a deterministic GeoJSON ``dict``."""
    import pandas as pd  # noqa: PLC0415  # heavy import, scope it
    from shapely.geometry import mapping  # noqa: PLC0415

    # Force EPSG:4326 — the only legal GeoJSON CRS per RFC 7946.
    gs = gdf if gdf.crs is None or gdf.crs.to_epsg() == _STORAGE_EPSG else gdf.to_crs(STORAGE_CRS)
    features: list[dict[str, object]] = []
    for _, row in gs.iterrows():
        geom = row.geometry
        props = {k: row[k] for k in gs.columns if k != "geometry"}
        for k, v in list(props.items()):
            # pandas-flavored NA / NaT / NaN → JSON null. pd.isna handles
            # scalars; lists/arrays would throw, hence the scalar check.
            if v is None or (not isinstance(v, (list, dict, tuple)) and pd.isna(v)):
                props[k] = None
                continue
            if hasattr(v, "item"):
                # numpy scalars → native Python.
                props[k] = v.item()
        feature = {
            "type": "Feature",
            "geometry": _round_coords(mapping(geom), coord_precision) if geom is not None else None,
            "properties": props,
        }
        features.append(feature)
    return {
        "type": "FeatureCollection",
        "features": features,
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
    }


def write_layer_geojson(
    gdf: gpd.GeoDataFrame,
    path: Path,
    *,
    coord_precision: int = GEOJSON_COORD_PRECISION,
) -> None:
    """Atomically write ``gdf`` to ``path`` as a *byte-deterministic* GeoJSON.

    Coordinates are rounded to ``coord_precision`` decimal places and
    properties dicts are serialized with ``sort_keys=True``, so the same
    input geometry + properties always produces identical bytes — useful
    for git diffability and downstream caching. The write goes to a
    sibling temp file first and is renamed atomically.
    """
    payload = _gdf_to_geojson_dict(gdf, coord_precision=coord_precision)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".geojson", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False, default=str)
            f.write("\n")
        os.replace(tmp, path)
        os.chmod(path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_aoi_polygon(aoi_path: Path) -> BaseGeometry:
    """Read a single-feature GeoJSON polygon and return the geometry."""
    gdf = gpd.read_file(aoi_path)
    if len(gdf) == 0:
        raise ValueError(f"{aoi_path} contains no features")
    return gdf.geometry.iloc[0]


def summarize(gdf: gpd.GeoDataFrame) -> dict[str, object]:
    """One-line summary used by CLI echo + tests."""
    geom_types = sorted(set(gdf.geometry.geom_type.tolist())) if not gdf.empty else []
    return {
        "features": len(gdf),
        "geom_types": geom_types,
        "crs": str(gdf.crs) if gdf.crs is not None else None,
    }


def summarize_json(gdf: gpd.GeoDataFrame) -> str:
    """JSON-serialized :func:`summarize` (handy for CLI echo)."""
    return json.dumps(summarize(gdf), sort_keys=True)
