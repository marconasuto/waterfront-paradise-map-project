from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import (
    LineString,
    MultiLineString,
    Point,
    Polygon,
)

from manfredonia_map.processing import base


def test_to_storage_crs_sets_default_when_missing():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=None)
    out = base.to_storage_crs(gdf)
    assert out.crs is not None
    assert "4326" in str(out.crs)


def test_to_storage_crs_is_noop_when_already_4326():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
    out = base.to_storage_crs(gdf)
    assert out is gdf


def test_to_storage_crs_reprojects_from_other():
    gdf = gpd.GeoDataFrame(geometry=[Point(500000, 4600000)], crs="EPSG:32633")
    out = base.to_storage_crs(gdf)
    assert "4326" in str(out.crs)
    # ~ Italy area: longitudes 12-16, latitudes 40-45
    p = out.geometry.iloc[0]
    assert 14 < p.x < 17
    assert 40 < p.y < 43


def test_to_storage_crs_handles_empty():
    gdf = gpd.GeoDataFrame(geometry=[], crs=None)
    out = base.to_storage_crs(gdf)
    assert out.empty
    assert "4326" in str(out.crs)


def test_make_valid_drops_empty_geoms():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0), Point()], crs="EPSG:4326")
    out = base.make_valid(gdf)
    assert len(out) == 1


def test_make_valid_repairs_self_intersecting_polygon():
    # Classic self-intersecting bow-tie
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame(geometry=[bowtie], crs="EPSG:4326")
    out = base.make_valid(gdf)
    assert len(out) == 1
    assert out.geometry.iloc[0].is_valid


def test_make_valid_returns_input_when_empty():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    assert base.make_valid(gdf).empty


def test_clip_to_aoi_keeps_inside_and_drops_outside():
    aoi = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    gdf = gpd.GeoDataFrame(
        {"k": ["in", "out"]},
        geometry=[Point(5, 5), Point(20, 20)],
        crs="EPSG:4326",
    )
    out = base.clip_to_aoi(gdf, aoi)
    assert out["k"].tolist() == ["in"]


def test_clip_to_aoi_handles_empty():
    aoi = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    out = base.clip_to_aoi(gdf, aoi)
    assert out.empty


def test_conform_to_schema_produces_canonical_columns():
    gdf = gpd.GeoDataFrame(
        {"OSMID": ["a", "b"], "NAME": ["X", "Y"], "extra": [1, 2]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )
    out = base.conform_to_schema(
        gdf,
        layer_id="foo",
        source_id="osm_foo",
        year_data=2024,
        category="bar",
        id_col="OSMID",
        name_col="NAME",
        extra_columns=["extra"],
    )
    assert list(out.columns) == [
        "id",
        "layer_id",
        "name_it",
        "category",
        "year_data",
        "source_id",
        "extra",
        "geometry",
    ]
    assert out["id"].tolist() == ["a", "b"]
    assert out["layer_id"].iloc[0] == "foo"
    assert out["source_id"].iloc[0] == "osm_foo"
    assert out["year_data"].iloc[0] == 2024
    assert out["name_it"].tolist() == ["X", "Y"]
    assert out["extra"].tolist() == [1, 2]


def test_conform_to_schema_synthesizes_id_when_missing():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326")
    out = base.conform_to_schema(
        gdf,
        layer_id="foo",
        source_id="x",
        year_data=None,
        category="bar",
    )
    assert out["id"].tolist() == ["foo_0", "foo_1"]
    assert out["name_it"].isna().all()
    assert out["year_data"].isna().all()


def test_conform_to_schema_preserves_input_crs_for_reprojection_later():
    # Regression: an earlier bug relabelled the output to EPSG:4326
    # without reprojecting, silently corrupting UTM-coordinate sources.
    # Now conform_to_schema must preserve the input CRS so the downstream
    # `to_storage_crs` step can reproject correctly.
    gdf = gpd.GeoDataFrame(
        geometry=[Point(575000, 4607000)],
        crs="EPSG:32633",
    )
    out = base.conform_to_schema(
        gdf,
        layer_id="x",
        source_id="s",
        year_data=2024,
        category="c",
    )
    assert out.crs.to_epsg() == 32633
    # And the coordinates are untouched (still metric).
    assert out.geometry.iloc[0].x == 575000


def test_conform_to_schema_defaults_to_storage_crs_when_input_has_none():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=None)
    out = base.conform_to_schema(
        gdf,
        layer_id="x",
        source_id="s",
        year_data=None,
        category="c",
    )
    assert out.crs.to_epsg() == 4326


def test_conform_to_schema_drops_unknown_extras():
    gdf = gpd.GeoDataFrame({"some_field": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    out = base.conform_to_schema(
        gdf,
        layer_id="foo",
        source_id="x",
        year_data=None,
        category="bar",
        extra_columns=["not_there"],
    )
    # extra_columns that don't exist in the input are silently skipped
    assert "not_there" not in out.columns
    assert "some_field" not in out.columns


def test_write_layer_geojson_round_trip(tmp_path: Path):
    gdf = gpd.GeoDataFrame(
        {"name_it": ["foo"]},
        geometry=[LineString([(15.9, 41.6), (16.0, 41.7)])],
        crs="EPSG:4326",
    )
    out = tmp_path / "x.geojson"
    base.write_layer_geojson(gdf, out)
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["type"] == "FeatureCollection"
    assert payload["features"][0]["properties"]["name_it"] == "foo"
    assert oct(out.stat().st_mode & 0o777) == "0o644"


def test_write_layer_geojson_is_byte_deterministic(tmp_path: Path):
    gdf = gpd.GeoDataFrame(
        {"name_it": ["foo", "bar"], "year_data": [2024, 2025]},
        geometry=[
            LineString([(15.9, 41.6), (16.0, 41.7)]),
            LineString([(15.8, 41.5), (15.9, 41.6)]),
        ],
        crs="EPSG:4326",
    )
    a = tmp_path / "a.geojson"
    b = tmp_path / "b.geojson"
    base.write_layer_geojson(gdf, a)
    base.write_layer_geojson(gdf, b)
    assert a.read_bytes() == b.read_bytes()


def test_write_layer_geojson_rounds_coordinates(tmp_path: Path):
    gdf = gpd.GeoDataFrame(
        geometry=[LineString([(15.900000000001, 41.600000000001), (16.0, 41.7)])],
        crs="EPSG:4326",
    )
    out = tmp_path / "x.geojson"
    base.write_layer_geojson(gdf, out)
    payload = json.loads(out.read_text())
    assert payload["features"][0]["geometry"]["coordinates"][0] == [15.9, 41.6]


def test_write_layer_geojson_reprojects_non_4326(tmp_path: Path):
    # A GeoDataFrame in UTM-33N must be re-projected before serialisation
    # (GeoJSON RFC 7946 only permits EPSG:4326).
    gdf = gpd.GeoDataFrame(
        geometry=[Point(575000, 4607000)],
        crs="EPSG:32633",
    )
    out = tmp_path / "x.geojson"
    base.write_layer_geojson(gdf, out)
    coord = json.loads(out.read_text())["features"][0]["geometry"]["coordinates"]
    assert 15 < coord[0] < 17
    assert 41 < coord[1] < 43


def test_write_layer_geojson_serialises_pandas_na_as_null(tmp_path: Path):
    gdf = gpd.GeoDataFrame(
        {"name_it": ["foo", None], "year_data": [2024, pd.NA]},
        geometry=[Point(15.9, 41.6), Point(16.0, 41.7)],
        crs="EPSG:4326",
    )
    out = tmp_path / "x.geojson"
    base.write_layer_geojson(gdf, out)
    payload = json.loads(out.read_text())
    props = [f["properties"] for f in payload["features"]]
    assert props[1]["name_it"] is None
    assert props[1]["year_data"] is None


def test_write_layer_geojson_overwrites_existing(tmp_path: Path):
    out = tmp_path / "x.geojson"
    out.write_text("garbage")
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
    base.write_layer_geojson(gdf, out)
    payload = json.loads(out.read_text())
    assert payload["type"] == "FeatureCollection"


def test_read_aoi_polygon_returns_first_feature(tmp_path: Path):
    p = tmp_path / "aoi.geojson"
    p.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    geom = base.read_aoi_polygon(p)
    assert geom.area == pytest.approx(1.0)


def test_read_aoi_polygon_raises_on_empty(tmp_path: Path):
    p = tmp_path / "empty.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    with pytest.raises(ValueError, match="no features"):
        base.read_aoi_polygon(p)


def test_summarize_includes_counts_and_types():
    gdf = gpd.GeoDataFrame(
        geometry=[
            LineString([(0, 0), (1, 1)]),
            MultiLineString([[(0, 0), (1, 0)]]),
            Point(0, 0),
        ],
        crs="EPSG:4326",
    )
    s = base.summarize(gdf)
    assert s["features"] == 3
    assert set(s["geom_types"]) == {"LineString", "MultiLineString", "Point"}


def test_summarize_handles_empty():
    s = base.summarize(gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"))
    assert s["features"] == 0
    assert s["geom_types"] == []


def test_summarize_json_is_valid_and_stable():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326")
    s = json.loads(base.summarize_json(gdf))
    assert s["features"] == 2
    assert s["geom_types"] == ["Point"]
