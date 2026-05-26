from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from click.testing import CliRunner
from shapely.geometry import Point, Polygon

from manfredonia_map.processing import base, mandatory
from manfredonia_map.processing import cli as proc_cli


def _write_layer(path: Path, gdf: gpd.GeoDataFrame) -> None:
    base.write_layer_geojson(gdf, path)


def test_filter_by_name_returns_empty_when_no_name_col():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
    out = mandatory._filter_by_name(gdf, "anything")
    assert out.empty


def test_filter_by_name_is_case_insensitive_substring():
    gdf = gpd.GeoDataFrame(
        {"name_it": ["Lago Salso", "Foo Bar", None, "LAGO SALSO - Prati"]},
        geometry=[Point(0, 0)] * 4,
        crs="EPSG:4326",
    )
    out = mandatory._filter_by_name(gdf, "lago salso")
    assert out["name_it"].tolist() == ["Lago Salso", "LAGO SALSO - Prati"]


def test_buffer_metric_zero_is_noop():
    gdf = gpd.GeoDataFrame(geometry=[Point(15.9, 41.6)], crs="EPSG:4326")
    out = mandatory._buffer_metric(gdf, 0.0)
    assert out.geometry.iloc[0].equals(gdf.geometry.iloc[0])


def test_buffer_metric_produces_polygon_from_point():
    gdf = gpd.GeoDataFrame(geometry=[Point(15.9, 41.6)], crs="EPSG:4326")
    out = mandatory._buffer_metric(gdf, 300.0)
    assert out.geometry.iloc[0].geom_type in {"Polygon", "MultiPolygon"}
    # ~300 m at lat 41.6° is roughly 0.003°; very rough sanity bound.
    assert out.geometry.iloc[0].area > 0


def test_promote_raises_when_upstream_layer_missing(tmp_path: Path):
    spec = mandatory.MandatoryPromotionSpec(
        feature_id="x",
        layer_id="not_there",
    )
    with pytest.raises(FileNotFoundError, match="not_there"):
        mandatory.promote(spec, processed_dir=tmp_path, out_dir=tmp_path / "out")


def test_promote_raises_when_filter_matches_nothing(tmp_path: Path):
    src = tmp_path / "wetlands.geojson"
    _write_layer(
        src,
        gpd.GeoDataFrame(
            {"name_it": ["Other Lake"]},
            geometry=[Polygon([(15.9, 41.6), (15.91, 41.6), (15.91, 41.61), (15.9, 41.61)])],
            crs="EPSG:4326",
        ),
    )
    spec = mandatory.MandatoryPromotionSpec(
        feature_id="lago_salso",
        layer_id="wetlands",
        name_filter_substring="lago salso",
    )
    with pytest.raises(ValueError, match="no features matched"):
        mandatory.promote(spec, processed_dir=tmp_path, out_dir=tmp_path / "out")


def test_promote_writes_filtered_polygons(tmp_path: Path):
    src = tmp_path / "wetlands.geojson"
    _write_layer(
        src,
        gpd.GeoDataFrame(
            {"name_it": ["Lago Salso", "Other", "Lago Salso - Prati"]},
            geometry=[
                Polygon([(15.91, 41.60), (15.93, 41.60), (15.93, 41.62), (15.91, 41.62)]),
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(15.93, 41.60), (15.95, 41.60), (15.95, 41.62), (15.93, 41.62)]),
            ],
            crs="EPSG:4326",
        ),
    )
    spec = mandatory.MandatoryPromotionSpec(
        feature_id="lago_salso",
        layer_id="wetlands",
        name_filter_substring="lago salso",
    )
    out_dir = tmp_path / "mandatory_for_aoi"
    out = mandatory.promote(spec, processed_dir=tmp_path, out_dir=out_dir)
    assert out == out_dir / "lago_salso.geojson"
    payload = json.loads(out.read_text())
    assert len(payload["features"]) == 2


def test_promote_buffers_when_buffer_m_set(tmp_path: Path):
    src = tmp_path / "archeological_areas.geojson"
    _write_layer(
        src,
        gpd.GeoDataFrame(
            {"name_it": ["Grotta Scaloria"]},
            geometry=[Point(15.907, 41.648)],
            crs="EPSG:4326",
        ),
    )
    spec = mandatory.MandatoryPromotionSpec(
        feature_id="grotta_scaloria",
        layer_id="archeological_areas",
        name_filter_substring="grotta scaloria",
        buffer_m=300.0,
    )
    out_dir = tmp_path / "mandatory_for_aoi"
    out = mandatory.promote(spec, processed_dir=tmp_path, out_dir=out_dir)
    payload = json.loads(out.read_text())
    # Buffered point becomes a polygon.
    assert payload["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_promote_default_out_dir_under_processed(tmp_path: Path):
    src = tmp_path / "sin_manfredonia.geojson"
    _write_layer(
        src,
        gpd.GeoDataFrame(
            {"name_it": ["MANFREDONIA"]},
            geometry=[Polygon([(15.9, 41.6), (15.91, 41.6), (15.91, 41.61), (15.9, 41.61)])],
            crs="EPSG:4326",
        ),
    )
    spec = mandatory.MandatoryPromotionSpec(
        feature_id="sin_manfredonia",
        layer_id="sin_manfredonia",
    )
    out = mandatory.promote(spec, processed_dir=tmp_path)
    assert out == tmp_path / "mandatory_for_aoi" / "sin_manfredonia.geojson"
    assert out.exists()


def test_promotions_registry_has_expected_entries():
    assert {"lago_salso", "sin_manfredonia", "grotta_scaloria"} <= set(mandatory.PROMOTIONS)
    for fid, spec in mandatory.PROMOTIONS.items():
        assert spec.feature_id == fid


# --- CLI -----------------------------------------------------------


def _seed_processed_layers(processed_dir: Path) -> None:
    """Drop minimal processed layers in place for an end-to-end CLI test."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    base.write_layer_geojson(
        gpd.GeoDataFrame(
            {"name_it": ["Lago Salso"]},
            geometry=[Polygon([(15.91, 41.60), (15.93, 41.60), (15.93, 41.62), (15.91, 41.62)])],
            crs="EPSG:4326",
        ),
        processed_dir / "wetlands.geojson",
    )
    base.write_layer_geojson(
        gpd.GeoDataFrame(
            {"name_it": ["MANFREDONIA"]},
            geometry=[Polygon([(15.93, 41.59), (15.95, 41.59), (15.95, 41.61), (15.93, 41.61)])],
            crs="EPSG:4326",
        ),
        processed_dir / "sin_manfredonia.geojson",
    )
    base.write_layer_geojson(
        gpd.GeoDataFrame(
            {"name_it": ["Grotta Scaloria"]},
            geometry=[Point(15.907, 41.648)],
            crs="EPSG:4326",
        ),
        processed_dir / "archeological_areas.geojson",
    )


def test_cli_mandatory_features_writes_all_three(tmp_path: Path):
    processed = tmp_path / "processed"
    _seed_processed_layers(processed)
    result = CliRunner().invoke(
        proc_cli.process_mandatory_features,
        ["--processed-dir", str(processed)],
    )
    assert result.exit_code == 0, result.output
    out_dir = processed / "mandatory_for_aoi"
    for fid in ("lago_salso", "sin_manfredonia", "grotta_scaloria"):
        assert (out_dir / f"{fid}.geojson").exists()


def test_cli_mandatory_features_reports_failures(tmp_path: Path):
    # Seed only the wetlands layer so the other two promotions fail.
    processed = tmp_path / "processed"
    processed.mkdir()
    base.write_layer_geojson(
        gpd.GeoDataFrame(
            {"name_it": ["Lago Salso"]},
            geometry=[Polygon([(15.91, 41.60), (15.93, 41.60), (15.93, 41.62), (15.91, 41.62)])],
            crs="EPSG:4326",
        ),
        processed / "wetlands.geojson",
    )
    result = CliRunner().invoke(
        proc_cli.process_mandatory_features,
        ["--processed-dir", str(processed)],
    )
    assert result.exit_code != 0
    assert "sin_manfredonia" in result.output
    assert "grotta_scaloria" in result.output
    # The one that succeeded is still written.
    assert (processed / "mandatory_for_aoi" / "lago_salso.geojson").exists()
