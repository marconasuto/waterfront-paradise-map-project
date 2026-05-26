from __future__ import annotations

from collections.abc import Callable

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from manfredonia_map.acquisition import osm


def _fake_fetcher(rows: list[tuple[str, object]]) -> Callable:
    def _fn(bbox: tuple[float, float, float, float], tags: dict[str, object]) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {"kind": [k for k, _ in rows]},
            geometry=[g for _, g in rows],
            crs="EPSG:4326",
        )

    return _fn


def test_layers_registry_has_expected_ids():
    expected = {
        "coastline",
        "roads",
        "cycle_paths",
        "cycle_routes",
        "harbours",
        "beaches",
        "wetlands",
        "industrial",
        "archaeology",
    }
    assert expected <= set(osm.LAYERS)


def test_cycle_routes_layer_keeps_lines_only():
    fetcher = _fake_fetcher(
        [
            ("pt", Point(15.92, 41.62)),
            ("ln", LineString([(15.9, 41.6), (15.95, 41.65)])),
            ("pg", Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])),
        ]
    )
    out = osm.fetch_layer("cycle_routes", (15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    assert set(out["kind"]) == {"ln"}


def test_industrial_layer_keeps_polygons_only():
    fetcher = _fake_fetcher(
        [
            ("pt", Point(15.92, 41.62)),
            ("pg", Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])),
        ]
    )
    out = osm.fetch_layer("industrial", (15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    assert set(out["kind"]) == {"pg"}


def test_archaeology_layer_keeps_points_lines_polygons():
    fetcher = _fake_fetcher(
        [
            ("pt", Point(15.92, 41.62)),
            ("ln", LineString([(15.9, 41.6), (15.95, 41.65)])),
            ("pg", Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])),
        ]
    )
    out = osm.fetch_layer("archaeology", (15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    assert set(out["kind"]) == {"pt", "ln", "pg"}


def test_fetch_features_passes_bbox_and_tags_through():
    captured: dict[str, object] = {}

    def fake(bbox: tuple[float, float, float, float], tags: dict[str, object]) -> gpd.GeoDataFrame:
        captured["bbox"] = bbox
        captured["tags"] = tags
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    osm.fetch_features((1.0, 2.0, 3.0, 4.0), {"foo": "bar"}, fetcher=fake)
    assert captured == {"bbox": (1.0, 2.0, 3.0, 4.0), "tags": {"foo": "bar"}}


def test_fetch_layer_filters_to_allowed_geom_types():
    fetcher = _fake_fetcher(
        [
            ("line1", LineString([(15.9, 41.6), (15.95, 41.65)])),
            ("poly1", Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])),
            ("line2", LineString([(16.0, 41.6), (16.05, 41.6)])),
        ]
    )
    out = osm.fetch_layer("coastline", (15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    # coastline allows only lines → polygon is dropped
    assert set(out["kind"]) == {"line1", "line2"}
    assert "4326" in str(out.crs)


def test_fetch_layer_wetlands_keeps_polygons_only():
    fetcher = _fake_fetcher(
        [
            ("pt", Point(15.92, 41.62)),
            ("ln", LineString([(15.9, 41.6), (15.95, 41.65)])),
            ("pg", Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])),
        ]
    )
    out = osm.fetch_layer("wetlands", (15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    assert set(out["kind"]) == {"pg"}


def test_fetch_layer_returns_empty_when_no_features():
    def fake(bbox, tags):
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    out = osm.fetch_layer("roads", (15.8, 41.49, 16.05, 41.69), fetcher=fake)
    assert out.empty


def test_fetch_layer_sets_crs_when_missing():
    def fake(bbox, tags):
        return gpd.GeoDataFrame(geometry=[LineString([(15, 41), (16, 42)])], crs=None)

    out = osm.fetch_layer("coastline", (15.8, 41.49, 16.05, 41.69), fetcher=fake)
    assert "4326" in str(out.crs)


def test_fetch_coastline_is_an_alias_for_layer():
    fetcher = _fake_fetcher([("line1", LineString([(15.9, 41.6), (15.95, 41.65)]))])
    out = osm.fetch_coastline((15.8, 41.49, 16.05, 41.69), fetcher=fetcher)
    assert len(out) == 1


def test_default_fetcher_is_used_when_none_passed(monkeypatch: pytest.MonkeyPatch):
    sentinel = gpd.GeoDataFrame(geometry=[LineString([(15, 41), (16, 42)])], crs="EPSG:4326")
    monkeypatch.setattr(osm, "_default_osmnx_fetcher", lambda bbox, tags: sentinel)
    out = osm.fetch_layer("coastline", (15.8, 41.49, 16.05, 41.69))
    assert len(out) == 1
