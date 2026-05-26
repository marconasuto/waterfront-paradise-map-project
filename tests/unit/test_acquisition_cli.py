from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from click.testing import CliRunner
from shapely.geometry import LineString, Polygon

from manfredonia_map.acquisition import cli as acq_cli
from manfredonia_map.acquisition import osm


def _write_aoi(tmp_path: Path) -> Path:
    p = tmp_path / "aoi_buffered.geojson"
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
                                    [15.80, 41.49],
                                    [16.05, 41.49],
                                    [16.05, 41.69],
                                    [15.80, 41.69],
                                    [15.80, 41.49],
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


def _patch_layer_fetch(
    monkeypatch: pytest.MonkeyPatch,
    layer_to_gdf: dict[str, gpd.GeoDataFrame],
) -> None:
    """Patch ``osm.fetch_layer`` to return per-layer canned data."""

    def _fake(layer_id: str, bbox: tuple[float, float, float, float], fetcher=None):
        return layer_to_gdf.get(layer_id, gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"))

    monkeypatch.setattr(acq_cli.osm, "fetch_layer", _fake)


def test_acquire_osm_layer_writes_geojson_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_layer_fetch(
        monkeypatch,
        {
            "coastline": gpd.GeoDataFrame(
                geometry=[LineString([(15.92, 41.55), (15.94, 41.65)])], crs="EPSG:4326"
            )
        },
    )
    aoi = _write_aoi(tmp_path)
    out = tmp_path / "raw" / "osm_coastline" / "coastline.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_osm_layer,
        ["coastline", "--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    prov = json.loads(out.with_suffix(".provenance.json").read_text())
    assert prov["source_id"] == "osm_coastline"
    assert prov["license"] == "ODbL-1.0"
    assert prov["bbox"] == [15.8, 41.49, 16.05, 41.69]
    assert prov["sha256"]
    assert prov["byte_count"] > 0


def test_acquire_osm_layer_fails_loud_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_layer_fetch(monkeypatch, {})  # every layer returns empty
    aoi = _write_aoi(tmp_path)
    out = tmp_path / "raw" / "osm_coastline" / "coastline.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_osm_layer,
        ["coastline", "--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code != 0
    assert "0 features" in result.output.lower()


def test_acquire_osm_layer_default_out_path_uses_data_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Redirect the default data/raw to tmp so we don't pollute the real tree.
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    _patch_layer_fetch(
        monkeypatch,
        {
            "roads": gpd.GeoDataFrame(
                {"highway": ["primary"]},
                geometry=[LineString([(15.91, 41.62), (15.92, 41.63)])],
                crs="EPSG:4326",
            )
        },
    )
    aoi = _write_aoi(tmp_path)
    result = CliRunner().invoke(acq_cli.acquire_osm_layer, ["roads", "--aoi", str(aoi)])
    assert result.exit_code == 0, result.output
    expected = tmp_path / "raw" / "osm_roads" / "roads.geojson"
    assert expected.exists()


def test_acquire_osm_layer_writes_nested_type_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # osmnx returns list/dict cells (e.g. `man_made=["pier","breakwater"]`).
    # pyogrio serialises these natively as JSON arrays/objects in the
    # GeoJSON `properties` payload; we just need to confirm we don't
    # explode and we keep the values addressable on read.
    _patch_layer_fetch(
        monkeypatch,
        {
            "harbours": gpd.GeoDataFrame(
                {
                    "name": ["Manfredonia"],
                    "tags_list": [["pier", "breakwater"]],
                    "tags_dict": [{"a": 1}],
                },
                geometry=[Polygon([(15.9, 41.6), (15.91, 41.6), (15.91, 41.61), (15.9, 41.61)])],
                crs="EPSG:4326",
            )
        },
    )
    aoi = _write_aoi(tmp_path)
    out = tmp_path / "harbours.geojson"
    result = CliRunner().invoke(
        acq_cli.acquire_osm_layer,
        ["harbours", "--aoi", str(aoi), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    props = json.loads(out.read_text())["features"][0]["properties"]
    assert props["name"] == "Manfredonia"
    assert props["tags_list"] == ["pier", "breakwater"]
    assert props["tags_dict"] == {"a": 1}


def test_acquire_osm_all_runs_each_layer_and_collects_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    # Two layers return data, one returns empty → that one fails individually
    # but the runner keeps going and reports the failure at the end.
    _patch_layer_fetch(
        monkeypatch,
        {
            "coastline": gpd.GeoDataFrame(
                geometry=[LineString([(15.92, 41.55), (15.94, 41.65)])], crs="EPSG:4326"
            ),
            "roads": gpd.GeoDataFrame(
                geometry=[LineString([(15.91, 41.62), (15.92, 41.63)])], crs="EPSG:4326"
            ),
        },
    )
    aoi = _write_aoi(tmp_path)
    skip_args: list[str] = []
    for lyr in sorted(osm.LAYERS):
        if lyr not in {"coastline", "roads", "wetlands"}:  # leave wetlands → empty → fail
            skip_args.extend(["--skip", lyr])
    result = CliRunner().invoke(
        acq_cli.acquire_osm_all,
        ["--aoi", str(aoi), *skip_args],
    )
    assert result.exit_code != 0
    assert "acquisitions failed: wetlands" in result.output
    assert (tmp_path / "raw" / "osm_coastline" / "coastline.geojson").exists()
    assert (tmp_path / "raw" / "osm_roads" / "roads.geojson").exists()


def test_acquire_osm_all_skips_listed_layers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acq_cli, "DATA_RAW", tmp_path / "raw")
    _patch_layer_fetch(
        monkeypatch,
        {
            "coastline": gpd.GeoDataFrame(
                geometry=[LineString([(15.92, 41.55), (15.94, 41.65)])], crs="EPSG:4326"
            )
        },
    )
    aoi = _write_aoi(tmp_path)
    skip_args: list[str] = []
    for lyr in sorted(osm.LAYERS):
        if lyr != "coastline":
            skip_args.extend(["--skip", lyr])
    result = CliRunner().invoke(
        acq_cli.acquire_osm_all,
        ["--aoi", str(aoi), *skip_args],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "osm_coastline" / "coastline.geojson").exists()
    # Every other layer was skipped, so no other directory was created.
    assert sorted(p.name for p in (tmp_path / "raw").iterdir()) == ["osm_coastline"]
