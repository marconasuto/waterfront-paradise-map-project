"""GeoJSON I/O helpers used by the AOI builder.

Writes are atomic (``tempfile`` + ``os.replace``) and deterministic:
coordinates are rounded to a fixed precision and dictionary keys are
sorted before serialization, so the same input geometry produces the
same bytes across runs and platforms — important for git-friendliness.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

COORD_PRECISION = 7


def read_geometry_geojson(path: Path) -> tuple[BaseGeometry, str]:
    """Read a GeoJSON file and return ``(geometry, crs_string)``.

    If the file contains multiple features their geometries are unioned.
    """
    gdf = gpd.read_file(path)
    if len(gdf) == 0:
        raise ValueError(f"{path} contains no features")
    crs = str(gdf.crs) if gdf.crs is not None else "EPSG:4326"
    if len(gdf) == 1:
        return gdf.geometry.iloc[0], crs
    return unary_union(list(gdf.geometry)), crs


def read_polygon_geojson(path: Path) -> tuple[BaseGeometry, str]:
    """Read a GeoJSON file expected to contain a single polygon feature."""
    gdf = gpd.read_file(path)
    if len(gdf) != 1:
        raise ValueError(f"{path} must contain exactly one feature; got {len(gdf)}")
    geom = gdf.geometry.iloc[0]
    crs = str(gdf.crs) if gdf.crs is not None else "EPSG:4326"
    return geom, crs


def _round_coords(obj: Any, ndigits: int) -> Any:
    """Recursively round all floats inside a GeoJSON geometry or coord list."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, list):
        return [_round_coords(x, ndigits) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_round_coords(x, ndigits) for x in obj)
    if isinstance(obj, dict):
        return {k: _round_coords(v, ndigits) for k, v in obj.items()}
    return obj


def write_aoi_geojson(
    geom: BaseGeometry,
    path: Path,
    *,
    name: str,
    properties: dict[str, Any],
    coord_precision: int = COORD_PRECISION,
) -> None:
    """Atomically write a single-feature GeoJSON in EPSG:4326.

    Args:
        geom: Geometry to serialize (already in EPSG:4326).
        path: Destination path. Parent directories are created as needed.
        name: Top-level ``FeatureCollection.name`` value.
        properties: Properties payload for the single feature.
        coord_precision: Number of decimal places to round coordinates
            to; ``7`` is ≈1 cm at the equator and gives byte-stable
            output across platforms.
    """
    feature = {
        "geometry": _round_coords(mapping(geom), coord_precision),
        "properties": dict(properties),
        "type": "Feature",
    }
    fc = {
        "crs": {"properties": {"name": "EPSG:4326"}, "type": "name"},
        "features": [feature],
        "name": name,
        "type": "FeatureCollection",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(fc, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
        os.chmod(path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
