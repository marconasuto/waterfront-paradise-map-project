"""OpenStreetMap acquisition via ``osmnx``.

Every supported layer is described by an :class:`OsmLayerSpec` entry in
:data:`LAYERS`. The CLI command ``mfd-map acquire osm <layer>`` looks up
the spec and runs a single generic pipeline (fetch → filter geometry
types → re-project to EPSG:4326). The actual HTTP / Overpass call is
performed by a small ``fetcher`` callable that tests override — no real
network call ever happens in the unit suite (``tests/conftest.py``
blocks ``socket.socket`` outside the ``@pytest.mark.network`` opt-in).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import geopandas as gpd

# osmnx 2.x: bbox is (left, bottom, right, top) = (west, south, east, north).
Bbox = tuple[float, float, float, float]
Tags = dict[str, Any]
Fetcher = Callable[[Bbox, Tags], gpd.GeoDataFrame]


@dataclass(frozen=True)
class OsmLayerSpec:
    """Static description of one OSM layer the pipeline knows about."""

    source_id: str
    dataset: str
    tags: Tags
    allowed_geom_types: frozenset[str]


LAYERS: dict[str, OsmLayerSpec] = {
    "coastline": OsmLayerSpec(
        source_id="osm_coastline",
        dataset="OSM natural=coastline",
        tags={"natural": "coastline"},
        allowed_geom_types=frozenset({"LineString", "MultiLineString"}),
    ),
    "roads": OsmLayerSpec(
        source_id="osm_roads",
        dataset="OSM highway=*",
        tags={"highway": True},
        allowed_geom_types=frozenset({"LineString", "MultiLineString"}),
    ),
    "cycle_paths": OsmLayerSpec(
        source_id="osm_cycle_paths",
        dataset="OSM highway=cycleway / bicycle=designated",
        tags={"highway": "cycleway", "bicycle": "designated"},
        allowed_geom_types=frozenset({"LineString", "MultiLineString"}),
    ),
    "harbours": OsmLayerSpec(
        source_id="osm_harbours",
        dataset="OSM harbour / landuse=harbour / man_made=pier|breakwater",
        tags={
            "harbour": True,
            "landuse": "harbour",
            "man_made": ["pier", "breakwater"],
        },
        allowed_geom_types=frozenset(
            {"LineString", "MultiLineString", "Polygon", "MultiPolygon", "Point"}
        ),
    ),
    "beaches": OsmLayerSpec(
        source_id="osm_beaches",
        dataset="OSM natural=beach",
        tags={"natural": "beach"},
        allowed_geom_types=frozenset(
            {"Polygon", "MultiPolygon", "LineString", "MultiLineString", "Point"}
        ),
    ),
    "wetlands": OsmLayerSpec(
        source_id="osm_wetlands",
        dataset="OSM natural=wetland",
        tags={"natural": "wetland"},
        allowed_geom_types=frozenset({"Polygon", "MultiPolygon"}),
    ),
    # Industrial areas — serves as the interim proxy for the SIN Manfredonia
    # perimeter since the MASE-authoritative shapefile is not programmatically
    # accessible (see OPEN-SIN-1 in SPECIFICATIONS.md).
    "industrial": OsmLayerSpec(
        source_id="osm_industrial",
        dataset="OSM landuse=industrial / landuse=brownfield",
        tags={"landuse": ["industrial", "brownfield"]},
        allowed_geom_types=frozenset({"Polygon", "MultiPolygon"}),
    ),
    # Archaeological sites — proxy for MiC Vincoli in Rete (only fills the
    # gap that VIR cannot fill once we acquire it).
    "archaeology": OsmLayerSpec(
        source_id="osm_archaeology",
        dataset="OSM historic=archaeological_site",
        tags={"historic": "archaeological_site"},
        allowed_geom_types=frozenset(
            {"Polygon", "MultiPolygon", "Point", "LineString", "MultiLineString"}
        ),
    ),
}


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


def _filter_to_layer(gdf: gpd.GeoDataFrame, spec: OsmLayerSpec) -> gpd.GeoDataFrame:
    """Filter ``gdf`` to ``spec.allowed_geom_types`` and force EPSG:4326."""
    if gdf.empty:
        return gdf
    out = gdf[gdf.geometry.geom_type.isin(spec.allowed_geom_types)].copy()
    if out.crs is None:
        out = out.set_crs("EPSG:4326")
    return out.to_crs("EPSG:4326")


def fetch_layer(
    layer_id: str,
    bbox: Bbox,
    fetcher: Fetcher | None = None,
) -> gpd.GeoDataFrame:
    """Fetch one configured layer (e.g. ``"coastline"``, ``"roads"``)."""
    spec = LAYERS[layer_id]
    gdf = fetch_features(bbox, spec.tags, fetcher=fetcher)
    return _filter_to_layer(gdf, spec)


def fetch_coastline(bbox: Bbox, fetcher: Fetcher | None = None) -> gpd.GeoDataFrame:
    """Fetch OSM ``natural=coastline`` (alias for ``fetch_layer("coastline", ...)``)."""
    return fetch_layer("coastline", bbox, fetcher=fetcher)
