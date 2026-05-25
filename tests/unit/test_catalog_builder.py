from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import yaml
from click.testing import CliRunner
from pydantic import ValidationError
from rasterio.transform import from_bounds
from shapely.geometry import LineString, Polygon

from manfredonia_map.catalog import builder, models
from manfredonia_map.catalog import cli as cat_cli
from manfredonia_map.processing import raster as raster_module

# --- tiny tree fixture -----------------------------------------------

def _write_provenance(path: Path, **fields: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    defaults = {
        "source_id": "src_x",
        "publisher": "Test Publisher",
        "dataset": "Test dataset",
        "url": "https://example.test/data.zip",
        "access_method": "HTTPS",
        "license": "CC-BY-4.0",
        "accessed_at": "2026-05-25T08:00:00+00:00",
        "raw_path": str(path.with_suffix("")),
        "sha256": "0" * 64,
        "byte_count": 1,
        "bbox": None,
        "year_data": None,
        "query": {},
    }
    defaults.update(fields)
    path.write_text(json.dumps(defaults), encoding="utf-8")


def _write_geojson(path: Path, gdf: gpd.GeoDataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")


def _write_aoi(path: Path, polygon: Polygon) -> None:
    gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326").to_file(path, driver="GeoJSON")


def _seed_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a minimal project layout: config/, data/raw/, data/processed/."""
    config_dir = tmp_path / "config"
    raw_dir = tmp_path / "data" / "raw"
    processed_dir = tmp_path / "data" / "processed"
    for d in (config_dir, raw_dir, processed_dir):
        d.mkdir(parents=True, exist_ok=True)

    # AOI shapes
    aoi_poly = Polygon([(15.8, 41.5), (16.05, 41.5), (16.05, 41.7), (15.8, 41.7)])
    for name in (
        "aoi_source.geojson",
        "aoi_buffered.geojson",
        "aoi_near_coast.geojson",
        "aoi.geojson",
    ):
        _write_aoi(config_dir / name, aoi_poly)
    (config_dir / "build.yaml").write_text(
        "version: 1\naoi:\n  buffer_m: 1000\n  coastal_band_m: 2000\n  alias: near_coast\n",
        encoding="utf-8",
    )

    # Two raw provenance sidecars in two source dirs.
    _write_provenance(
        raw_dir / "osm_coastline" / "coastline.provenance.json",
        source_id="osm_coastline",
        publisher="OpenStreetMap contributors",
        dataset="OSM natural=coastline",
        bbox=[15.79, 41.49, 16.06, 41.69],
        raw_path=str(raw_dir / "osm_coastline" / "coastline.geojson"),
    )
    _write_provenance(
        raw_dir / "tinitaly" / "e46005_s10.zip.provenance.json",
        source_id="tinitaly_1_1_e46005_s10",
        publisher="INGV",
        dataset="TINITALY tile",
        raw_path=str(raw_dir / "tinitaly" / "e46005_s10.zip"),
    )

    # Two processed vector GeoJSONs with the schema columns our normalizer emits.
    _write_geojson(
        processed_dir / "coastline.geojson",
        gpd.GeoDataFrame(
            {
                "id": ["w1", "w2"],
                "layer_id": ["coastline", "coastline"],
                "name_it": [None, "Spiaggia"],
                "category": ["coastline", "coastline"],
                "year_data": [2026, 2026],
                "source_id": ["osm_coastline", "osm_coastline"],
            },
            geometry=[
                LineString([(15.9, 41.6), (16.0, 41.65)]),
                LineString([(16.0, 41.65), (16.05, 41.69)]),
            ],
            crs="EPSG:4326",
        ),
    )
    _write_geojson(
        processed_dir / "wetlands.geojson",
        gpd.GeoDataFrame(
            {
                "id": ["1"],
                "layer_id": ["wetlands"],
                "name_it": ["Lago Salso"],
                "category": ["wetland"],
                "year_data": [2026],
                "source_id": ["osm_wetlands"],
            },
            geometry=[Polygon([(15.91, 41.60), (15.93, 41.60), (15.93, 41.62), (15.91, 41.62)])],
            crs="EPSG:4326",
        ),
    )

    # Tiny raster (mimics a published 8-bit COG; we use a plain GTiff here
    # because the discover step only reads metadata).
    raster_path = processed_dir / "fake_dtm_8bit.tif"
    transform = from_bounds(15.85, 41.55, 16.0, 41.65, 50, 40)
    with rasterio.open(
        raster_path, "w", driver="GTiff", count=4, dtype="uint8",
        width=50, height=40, crs="EPSG:32633", transform=transform,
    ) as ds:
        ds.write(np.zeros((4, 40, 50), dtype=np.uint8))

    # Register a synthetic raster spec so source_id resolution finds it.
    raster_module.PROCESSORS["fake_dtm"] = raster_module.RasterProcessorSpec(
        raster_id="fake_dtm", raw_path=raw_dir / "tinitaly" / "e46005_s10.zip",
        source_id="tinitaly_1_1_e46005_s10", year_data=2023,
    )

    return config_dir, raw_dir, processed_dir


# --- builder primitives ---------------------------------------------

def test_sha256_of_file_matches_hashlib(tmp_path: Path):
    p = tmp_path / "x.bin"
    payload = b"hello world\n"
    p.write_bytes(payload)
    assert builder._sha256_of_file(p) == hashlib.sha256(payload).hexdigest()


def test_now_iso_utc_ends_with_offset():
    s = builder._now_iso_utc()
    assert s.endswith("+00:00")
    assert "." not in s.split("+", 1)[0]  # no microseconds


def test_repo_root_finds_pyproject_marker(tmp_path: Path):
    root = tmp_path / "myproj"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("")
    assert builder._repo_root(root / "src") == root.resolve()


def test_repo_root_falls_back_when_no_marker(tmp_path: Path):
    assert builder._repo_root(tmp_path) == tmp_path.resolve()


def test_rel_returns_absolute_when_outside_repo(tmp_path: Path):
    outside = tmp_path / "outside" / "a.tif"
    outside.parent.mkdir()
    outside.write_text("")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert builder._rel(outside, repo_root) == str(outside.resolve())


def test_inspect_vector_returns_empty_when_no_features(tmp_path: Path):
    p = tmp_path / "empty.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    count, geom_types, source_id, category, year = builder._inspect_vector(p)
    assert (count, geom_types, source_id, category, year) == (0, [], None, None, None)


def test_inspect_vector_extracts_first_value_of_each_scalar_column(tmp_path: Path):
    p = tmp_path / "v.geojson"
    gpd.GeoDataFrame(
        {
            "source_id": ["s_one", "s_one"],
            "category": ["cat", "cat"],
            "year_data": [2024, 2024],
        },
        geometry=[
            LineString([(0, 0), (1, 0)]),
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        ],
        crs="EPSG:4326",
    ).to_file(p, driver="GeoJSON")
    count, geom_types, source_id, category, year = builder._inspect_vector(p)
    assert count == 2
    assert set(geom_types) == {"LineString", "Polygon"}
    assert source_id == "s_one"
    assert category == "cat"
    assert year == 2024


def test_raster_source_id_for_uses_processors_registry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(
        raster_module.PROCESSORS, "tinitaly_dtm",
        raster_module.RasterProcessorSpec(
            raster_id="tinitaly_dtm", raw_path=Path("/nope"),
            source_id="tinitaly_1_1_e46005_s10", year_data=2023,
        ),
    )
    assert builder._raster_source_id_for("tinitaly_dtm_8bit") == "tinitaly_1_1_e46005_s10"
    # Hillshade variant resolves to the same source.
    assert builder._raster_source_id_for("tinitaly_dtm_hillshade_8bit") == "tinitaly_1_1_e46005_s10"


def test_raster_source_id_for_returns_none_on_unknown(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(raster_module, "PROCESSORS", {})
    assert builder._raster_source_id_for("anything_8bit") is None


def test_read_build_settings_defaults_when_missing(tmp_path: Path):
    settings = builder._read_build_settings(tmp_path)
    assert settings == (1000.0, 2000.0, "near_coast")


def test_read_build_settings_reads_yaml(tmp_path: Path):
    (tmp_path / "build.yaml").write_text(
        "version: 1\naoi:\n  buffer_m: 500\n  coastal_band_m: 1000\n  alias: buffered\n",
        encoding="utf-8",
    )
    assert builder._read_build_settings(tmp_path) == (500.0, 1000.0, "buffered")


# --- discover_* functions -------------------------------------------

def test_discover_sources_aggregates_all_sidecars(tmp_path: Path):
    _config_dir, raw_dir, _ = _seed_tree(tmp_path)
    sources = builder.discover_sources(raw_dir)
    ids = {s.source_id for s in sources}
    assert {"osm_coastline", "tinitaly_1_1_e46005_s10"} <= ids


def test_discover_vector_layers_lists_each_geojson(tmp_path: Path):
    _config_dir, _, processed_dir = _seed_tree(tmp_path)
    layers = builder.discover_vector_layers(processed_dir, repo_root=tmp_path)
    ids = {lv.layer_id for lv in layers}
    assert {"coastline", "wetlands"} <= ids
    by_id = {lv.layer_id: lv for lv in layers}
    assert by_id["coastline"].feature_count == 2
    assert "LineString" in by_id["coastline"].geom_types
    assert by_id["wetlands"].source_id == "osm_wetlands"


def test_discover_raster_layers_includes_hillshade(tmp_path: Path):
    _, _, processed_dir = _seed_tree(tmp_path)
    # Add a hillshade COG too.
    hs_path = processed_dir / "fake_dtm_hillshade_8bit.tif"
    transform = from_bounds(15.85, 41.55, 16.0, 41.65, 50, 40)
    with rasterio.open(
        hs_path, "w", driver="GTiff", count=4, dtype="uint8",
        width=50, height=40, crs="EPSG:32633", transform=transform,
    ) as ds:
        ds.write(np.zeros((4, 40, 50), dtype=np.uint8))

    layers = builder.discover_raster_layers(processed_dir, repo_root=tmp_path)
    by_id = {lr.layer_id: lr for lr in layers}
    assert "fake_dtm" in by_id
    assert "fake_dtm_hillshade" in by_id
    assert by_id["fake_dtm_hillshade"].derived_from == "fake_dtm"
    assert by_id["fake_dtm"].source_id == "tinitaly_1_1_e46005_s10"


# --- assemble + write + load --------------------------------------

def test_assemble_returns_validated_catalog(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    cat = builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path, now="2026-05-25T10:00:00+00:00",
    )
    assert cat.version == models.SCHEMA_VERSION
    assert cat.generated_at == "2026-05-25T10:00:00+00:00"
    assert {s.source_id for s in cat.sources} >= {"osm_coastline", "tinitaly_1_1_e46005_s10"}
    assert {lv.layer_id for lv in cat.vector_layers} >= {"coastline", "wetlands"}


def test_assemble_raises_when_aoi_missing(tmp_path: Path):
    _, raw_dir, processed_dir = _seed_tree(tmp_path)
    empty_config = tmp_path / "empty_config"
    empty_config.mkdir()
    with pytest.raises(FileNotFoundError, match="aoi"):
        builder.assemble(
            config_dir=empty_config, data_raw=raw_dir, processed_dir=processed_dir,
            repo_root=tmp_path,
        )


def test_write_and_load_roundtrip(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    cat = builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path, now="2026-05-25T10:00:00+00:00",
    )
    out = tmp_path / "data" / "catalog.yaml"
    builder.write(cat, out)
    assert out.exists()
    loaded = builder.load(out)
    assert loaded == cat
    # Permissions are mode 0o644.
    assert oct(out.stat().st_mode & 0o777) == "0o644"


def test_write_is_deterministic_byte_for_byte(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    cat = builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path, now="2026-05-25T10:00:00+00:00",
    )
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    builder.write(cat, a)
    builder.write(cat, b)
    assert a.read_bytes() == b.read_bytes()


def test_load_rejects_invalid_payload(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\n# nothing else\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        builder.load(p)


def test_iter_layer_ids_includes_both_vectors_and_rasters(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    cat = builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    ids = list(builder.iter_layer_ids(cat))
    assert "coastline" in ids
    assert "fake_dtm" in ids


# --- CLI -------------------------------------------------------------

def test_cli_catalog_build_writes_yaml(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    out = tmp_path / "data" / "catalog.yaml"
    result = CliRunner().invoke(
        cat_cli.catalog_build,
        [
            "--config-dir", str(config_dir),
            "--data-raw", str(raw_dir),
            "--processed-dir", str(processed_dir),
            "--out", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(out.read_text())
    assert payload["version"] == models.SCHEMA_VERSION


def test_cli_catalog_validate_succeeds(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_tree(tmp_path)
    out = tmp_path / "data" / "catalog.yaml"
    cat = builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    builder.write(cat, out)
    result = CliRunner().invoke(cat_cli.catalog_validate, [str(out)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_cli_catalog_validate_reports_invalid(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\n", encoding="utf-8")
    result = CliRunner().invoke(cat_cli.catalog_validate, [str(bad)])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower()


def test_cli_catalog_validate_missing_file(tmp_path: Path):
    result = CliRunner().invoke(cat_cli.catalog_validate, [str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0
