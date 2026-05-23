from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from manfredonia_map.aoi import io


def _write_fc(path: Path, polygons: list[Polygon]) -> None:
    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [list(p.exterior.coords)],
                },
            }
            for p in polygons
        ],
    }
    path.write_text(json.dumps(fc), encoding="utf-8")


def test_read_polygon_geojson_round_trip(tmp_path: Path):
    src = Polygon([(15.9, 41.6), (15.91, 41.6), (15.91, 41.61), (15.9, 41.61), (15.9, 41.6)])
    p = tmp_path / "src.geojson"
    _write_fc(p, [src])
    geom, crs = io.read_polygon_geojson(p)
    assert geom.equals(src)
    assert "4326" in crs


def test_read_polygon_geojson_rejects_multi_feature(tmp_path: Path):
    p = tmp_path / "multi.geojson"
    _write_fc(
        p,
        [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)]),
        ],
    )
    with pytest.raises(ValueError, match="exactly one feature"):
        io.read_polygon_geojson(p)


def test_read_geometry_geojson_unions_multi_feature(tmp_path: Path):
    p = tmp_path / "multi.geojson"
    a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    b = Polygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)])
    _write_fc(p, [a, b])
    union, _ = io.read_geometry_geojson(p)
    assert union.contains(a.centroid)
    assert union.contains(b.centroid)


def test_read_geometry_geojson_rejects_empty(tmp_path: Path):
    p = tmp_path / "empty.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no features"):
        io.read_geometry_geojson(p)


def test_write_aoi_geojson_is_byte_deterministic(tmp_path: Path):
    g = Polygon([(15.9, 41.6), (15.91, 41.6), (15.91, 41.61), (15.9, 41.61), (15.9, 41.6)])
    a = tmp_path / "a.geojson"
    b = tmp_path / "b.geojson"
    io.write_aoi_geojson(g, a, name="x", properties={"k": 1})
    io.write_aoi_geojson(g, b, name="x", properties={"k": 1})
    assert a.read_bytes() == b.read_bytes()


def test_write_aoi_geojson_rounds_coordinates(tmp_path: Path):
    # A polygon with a 12-decimal value: after writing, only 7 decimals remain.
    g = Polygon(
        [
            (15.900000000001, 41.600000000001),
            (15.910000000001, 41.600000000001),
            (15.910000000001, 41.610000000001),
            (15.900000000001, 41.610000000001),
            (15.900000000001, 41.600000000001),
        ]
    )
    p = tmp_path / "p.geojson"
    io.write_aoi_geojson(g, p, name="r", properties={})
    raw = json.loads(p.read_text())
    coord = raw["features"][0]["geometry"]["coordinates"][0][0]
    assert coord == [15.9, 41.6]


def test_round_coords_handles_tuples():
    assert io._round_coords((1.123456789, 2.987654321), 3) == (1.123, 2.988)


def test_round_coords_passes_through_unknown_types():
    assert io._round_coords("hello", 3) == "hello"
    assert io._round_coords(42, 3) == 42
