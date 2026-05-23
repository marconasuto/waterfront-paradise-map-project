"""OpenStreetMap acquisition via ``osmnx``.

The actual HTTP / Overpass call is performed by a small ``fetcher``
callable that is injected — tests pass a fake fetcher so no real network
call ever happens in the unit suite (the ``_block_network`` fixture in
``tests/conftest.py`` would otherwise raise).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import geopandas as gpd

# osmnx 2.x: bbox is (left, bottom, right, top) = (west, south, east, north).
Bbox = tuple[float, float, float, float]
Tags = dict[str, Any]
Fetcher = Callable[[Bbox, Tags], gpd.GeoDataFrame]


def _default_osmnx_fetcher(bbox: Bbox, tags: Tags) -> gpd.GeoDataFrame:  # pragma: no cover
    """Default fetcher — calls ``osmnx.features_from_bbox`` (network)."""
    import osmnx as ox  # noqa: PLC0415  # lazy: osmnx pulls a heavy dep tree

    return ox.features_from_bbox(bbox=bbox, tags=tags)


def fetch_features(
    bbox: Bbox,
    tags: Tags,
    fetcher: Fetcher | None = None,
) -> gpd.GeoDataFrame:
    """Return the OSM features matching ``tags`` inside ``bbox``."""
    fn = fetcher if fetcher is not None else _default_osmnx_fetcher
    return fn(bbox, tags)


def fetch_coastline(
    bbox: Bbox,
    fetcher: Fetcher | None = None,
) -> gpd.GeoDataFrame:
    """Return OSM ``natural=coastline`` features inside ``bbox``.

    Args:
        bbox: ``(west, south, east, north)`` in EPSG:4326.
        fetcher: Optional injection point for tests.

    Returns:
        A GeoDataFrame (EPSG:4326) containing only LineString /
        MultiLineString features tagged ``natural=coastline``.
    """
    gdf = fetch_features(bbox, {"natural": "coastline"}, fetcher=fetcher)
    if gdf.empty:
        return gdf
    # Defensive: osmnx may include closed-way Polygons (islands tagged as
    # coastline). Keep only line-like geometries for the AOI builder.
    line_types = {"LineString", "MultiLineString"}
    out = gdf[gdf.geometry.geom_type.isin(line_types)].copy()
    if out.crs is None:
        out = out.set_crs("EPSG:4326")
    return out.to_crs("EPSG:4326")
