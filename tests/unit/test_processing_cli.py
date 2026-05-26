from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from click.testing import CliRunner
from shapely.geometry import LineString, Point, Polygon

from manfredonia_map.processing import cli as proc_cli
from manfredonia_map.processing import normalize


def _aoi_4326(tmp_path: Path) -> Path:
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
                            "coordinates": [
                                [
                                    [15.85, 41.55],
                                    [16.05, 41.55],
                                    [16.05, 41.70],
                                    [15.85, 41.70],
                                    [15.85, 41.55],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return p


def _stub_normalizer(value: gpd.GeoDataFrame) -> normalize.NormalizerSpec:
    return normalize.NormalizerSpec(layer_id="stub", fn=lambda: value)


def test_process_vector_unknown_layer_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aoi = _aoi_4326(tmp_path)
    result = CliRunner().invoke(
        proc_cli.process_vector,
        ["nonexistent", "--aoi", str(aoi), "--out-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
    assert "unknown layer_id" in result.output


def test_process_vector_runs_pipeline_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub normalizer returns features both inside and outside the AOI.
    stub_gdf = gpd.GeoDataFrame(
        {
            "id": ["a", "b"],
            "layer_id": ["stub", "stub"],
            "name_it": ["IN", "OUT"],
            "category": ["x", "x"],
            "year_data": [2024, 2024],
            "source_id": ["fake", "fake"],
        },
        geometry=[
            LineString([(15.9, 41.6), (15.95, 41.65)]),  # inside AOI
            LineString([(0.0, 0.0), (0.1, 0.1)]),  # far outside
        ],
        crs="EPSG:4326",
    )
    monkeypatch.setitem(
        normalize.NORMALIZERS,
        "stub",
        _stub_normalizer(stub_gdf),
    )

    aoi = _aoi_4326(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        proc_cli.process_vector,
        ["stub", "--aoi", str(aoi), "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0, result.output

    out_file = out_dir / "stub.geojson"
    assert out_file.exists()
    payload = json.loads(out_file.read_text())
    names = [f["properties"]["name_it"] for f in payload["features"]]
    assert "IN" in names
    assert "OUT" not in names


def test_process_vector_reprojects_input_to_4326(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A normalizer returning UTM coordinates should be re-projected to 4326
    # before clipping; otherwise the AOI clip would silently produce zero.
    utm_polygon = Polygon(
        [
            (570000, 4605000),
            (580000, 4605000),
            (580000, 4615000),
            (570000, 4615000),
            (570000, 4605000),
        ]
    )
    stub_gdf = gpd.GeoDataFrame(
        {
            "id": ["p"],
            "layer_id": ["stub"],
            "name_it": ["polygon"],
            "category": ["x"],
            "year_data": [2024],
            "source_id": ["fake"],
        },
        geometry=[utm_polygon],
        crs="EPSG:32633",
    )
    monkeypatch.setitem(
        normalize.NORMALIZERS,
        "stub",
        _stub_normalizer(stub_gdf),
    )

    aoi = _aoi_4326(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        proc_cli.process_vector,
        ["stub", "--aoi", str(aoi), "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0, result.output
    out_file = out_dir / "stub.geojson"
    payload = json.loads(out_file.read_text())
    assert payload["features"]  # survived the clip
    # And the geometry is now in WGS 84 (degrees), not metres.
    coord = payload["features"][0]["geometry"]["coordinates"][0][0]
    assert 15 < coord[0] < 17
    assert 41 < coord[1] < 43


def test_process_vectors_all_runs_each_and_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub_a = gpd.GeoDataFrame(
        {
            "id": ["a"],
            "layer_id": ["a"],
            "name_it": ["A"],
            "category": ["x"],
            "year_data": [2024],
            "source_id": ["s"],
        },
        geometry=[Point(15.9, 41.6)],
        crs="EPSG:4326",
    )
    stub_b = gpd.GeoDataFrame(
        {
            "id": ["b"],
            "layer_id": ["b"],
            "name_it": ["B"],
            "category": ["x"],
            "year_data": [2024],
            "source_id": ["s"],
        },
        geometry=[Point(15.95, 41.65)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(
        normalize,
        "NORMALIZERS",
        {
            "stub_a": normalize.NormalizerSpec(layer_id="stub_a", fn=lambda: stub_a),
            "stub_b": normalize.NormalizerSpec(layer_id="stub_b", fn=lambda: stub_b),
        },
    )

    aoi = _aoi_4326(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        proc_cli.process_vectors_all,
        ["--aoi", str(aoi), "--out-dir", str(out_dir), "--skip", "stub_b"],
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "stub_a.geojson").exists()
    assert not (out_dir / "stub_b.geojson").exists()


def test_process_vectors_all_collects_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom() -> gpd.GeoDataFrame:
        raise RuntimeError("kaboom")

    good_gdf = gpd.GeoDataFrame(
        {
            "id": ["a"],
            "layer_id": ["a"],
            "name_it": ["A"],
            "category": ["x"],
            "year_data": [2024],
            "source_id": ["s"],
        },
        geometry=[Point(15.9, 41.6)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(
        normalize,
        "NORMALIZERS",
        {
            "good": normalize.NormalizerSpec(layer_id="good", fn=lambda: good_gdf),
            "bad": normalize.NormalizerSpec(layer_id="bad", fn=_boom),
        },
    )

    aoi = _aoi_4326(tmp_path)
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        proc_cli.process_vectors_all,
        ["--aoi", str(aoi), "--out-dir", str(out_dir)],
    )
    assert result.exit_code != 0
    assert "bad" in result.output
    assert (out_dir / "good.geojson").exists()
