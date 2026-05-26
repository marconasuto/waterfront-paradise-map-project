from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import yaml
from click.testing import CliRunner
from rasterio.transform import from_bounds
from shapely.geometry import LineString, Polygon

from manfredonia_map.catalog import builder as catalog_builder
from manfredonia_map.processing import raster as raster_module
from manfredonia_map.publishing import cli as pub_cli
from manfredonia_map.publishing import manifest, settings, tippecanoe

# --- settings --------------------------------------------------------

def test_settings_loads_values_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.fake")
    monkeypatch.setenv("MAPBOX_PUBLIC_TOKEN", "pk.fake")
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    s = settings.MapboxSettings(_env_file=None)
    assert s.secret_token == "sk.fake"
    assert s.public_token == "pk.fake"
    assert s.username == "tester"


def test_settings_require_username_raises_when_empty():
    s = settings.MapboxSettings(MAPBOX_USERNAME="", _env_file=None)
    with pytest.raises(RuntimeError, match="MAPBOX_USERNAME"):
        s.require_username()


def test_settings_require_secret_token_raises_when_empty():
    s = settings.MapboxSettings(MAPBOX_SECRET_TOKEN="", _env_file=None)
    with pytest.raises(RuntimeError, match="MAPBOX_SECRET_TOKEN"):
        s.require_secret_token()


def test_settings_require_helpers_return_value_when_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "u")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    s = settings.MapboxSettings(_env_file=None)
    assert s.require_username() == "u"
    assert s.require_secret_token() == "sk.x"


def test_settings_load_from_env_file_path(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "MAPBOX_SECRET_TOKEN=sk.from-file\nMAPBOX_USERNAME=from-file\n",
        encoding="utf-8",
    )
    s = settings.load_from_env_file(env)
    assert s.secret_token == "sk.from-file"
    assert s.username == "from-file"


def test_settings_load_from_env_file_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "default-user")
    s = settings.load_from_env_file(None)
    assert s.username == "default-user"


# --- tippecanoe -----------------------------------------------------

def test_find_tippecanoe_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(FileNotFoundError, match="tippecanoe"):
        tippecanoe.find_tippecanoe()


def test_find_tippecanoe_returns_path_when_present(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/tippecanoe")
    assert tippecanoe.find_tippecanoe() == "/usr/local/bin/tippecanoe"


def test_tippecanoe_spec_command_includes_pinned_flags(tmp_path: Path):
    spec = tippecanoe.TippecanoeBuildSpec(
        input_geojson=tmp_path / "in.geojson",
        output_mbtiles=tmp_path / "out.mbtiles",
        layer_name="x",
        name="X",
        description="d",
        attribution="a",
    )
    cmd = spec.command("/bin/tippecanoe")
    assert cmd[0] == "/bin/tippecanoe"
    assert "-zg" in cmd
    assert "--drop-densest-as-needed" in cmd
    assert "--extend-zooms-if-still-dropping" in cmd
    assert "--coalesce-densest-as-needed" in cmd
    assert "--no-tile-stats" in cmd
    # --read-parallel is intentionally omitted (see tippecanoe.py docstring).
    assert "--read-parallel" not in cmd
    assert "--force" in cmd
    assert "--layer=x" in cmd
    assert "--name=X" in cmd
    assert "--description=d" in cmd
    assert "--attribution=a" in cmd
    assert str(tmp_path / "in.geojson") in cmd
    assert str(tmp_path / "out.mbtiles") in cmd


def test_build_mbtiles_raises_when_input_missing(tmp_path: Path):
    spec = tippecanoe.TippecanoeBuildSpec(
        input_geojson=tmp_path / "nope.geojson",
        output_mbtiles=tmp_path / "out.mbtiles",
        layer_name="x", name="x", description="x", attribution="x",
    )
    with pytest.raises(FileNotFoundError, match="input GeoJSON"):
        tippecanoe.build_mbtiles(spec)


def test_build_mbtiles_runs_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    geojson = tmp_path / "in.geojson"
    geojson.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    captured: dict[str, object] = {}

    def _fake_run(cmd: list[str], check: bool) -> subprocess.CompletedProcess[bytes]:
        captured["cmd"] = cmd
        captured["check"] = check
        # Pretend tippecanoe wrote the output.
        Path(cmd[2]).write_bytes(b"PK\x03\x04")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(tippecanoe, "find_tippecanoe", lambda *_: "/fake/tippecanoe")
    monkeypatch.setattr(subprocess, "run", _fake_run)

    out = tmp_path / "out.mbtiles"
    spec = tippecanoe.TippecanoeBuildSpec(
        input_geojson=geojson, output_mbtiles=out,
        layer_name="x", name="X", description="d", attribution="a",
    )
    result = tippecanoe.build_mbtiles(spec)
    assert result == out
    assert out.exists()
    assert captured["check"] is True
    assert captured["cmd"][0] == "/fake/tippecanoe"


# --- manifest -------------------------------------------------------

def test_slugify_tileset_id_strips_disallowed_chars():
    # "Lago Salso (SIC)" lower → "lago salso (sic)", non-[a-z0-9_-] → "-",
    # truncated to the 17-char budget, trailing dashes stripped before
    # the "-v1" suffix.
    out = manifest.slugify_tileset_id("Lago Salso (SIC)")
    assert out == "manfredonia-lago-salso--sic-v1"
    assert len(out) <= 32


def test_slugify_tileset_id_respects_32_char_budget():
    long_name = "x" * 100
    out = manifest.slugify_tileset_id(long_name)
    assert len(out) <= 32
    assert out.startswith("manfredonia-")
    assert out.endswith("-v1")


def test_slugify_tileset_id_lowercases_and_preserves_underscores():
    # "hydrography_surface" is 19 chars; the 17-char budget truncates it
    # to "hydrography_surfa" (no trailing dash to strip).
    out = manifest.slugify_tileset_id("hydrography_surface")
    assert out == "manfredonia-hydrography_surfa-v1"
    assert len(out) <= 32


def _seed_processed_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Mini Phase 4 output: aoi shapes + 1 vector layer + 1 raster."""
    config_dir = tmp_path / "config"
    raw_dir = tmp_path / "data" / "raw"
    processed_dir = tmp_path / "data" / "processed"
    for d in (config_dir, raw_dir, processed_dir):
        d.mkdir(parents=True, exist_ok=True)

    aoi_poly = Polygon([(15.8, 41.5), (16.05, 41.5), (16.05, 41.7), (15.8, 41.7)])
    for name in (
        "aoi_source.geojson", "aoi_buffered.geojson",
        "aoi_near_coast.geojson", "aoi.geojson",
    ):
        gpd.GeoDataFrame(geometry=[aoi_poly], crs="EPSG:4326").to_file(
            config_dir / name, driver="GeoJSON",
        )

    # One provenance sidecar matching the vector layer.
    sidecar = raw_dir / "osm_coastline" / "coastline.provenance.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(
        json.dumps({
            "source_id": "osm_coastline",
            "publisher": "OpenStreetMap contributors",
            "dataset": "OSM natural=coastline",
            "url": "https://example.test",
            "access_method": "Overpass",
            "license": "ODbL-1.0",
            "accessed_at": "2026-05-26T08:00:00+00:00",
            "raw_path": str(raw_dir / "osm_coastline" / "coastline.geojson"),
            "sha256": "0" * 64,
            "byte_count": 1,
            "bbox": None,
            "year_data": 2026,
            "query": {},
        }),
        encoding="utf-8",
    )

    # Processed vector layer.
    coastline_path = processed_dir / "coastline.geojson"
    gpd.GeoDataFrame(
        {
            "id": ["w1"],
            "layer_id": ["coastline"],
            "name_it": [None],
            "category": ["coastline"],
            "year_data": [2026],
            "source_id": ["osm_coastline"],
        },
        geometry=[LineString([(15.9, 41.6), (16.0, 41.65)])],
        crs="EPSG:4326",
    ).to_file(coastline_path, driver="GeoJSON")

    # Pre-built MBTiles for the manifest test.
    (processed_dir / "mbtiles").mkdir()
    (processed_dir / "mbtiles" / "coastline.mbtiles").write_bytes(b"fake-mbtiles")

    # Processed raster.
    raster_path = processed_dir / "tinitaly_dtm_8bit.tif"
    transform = from_bounds(15.85, 41.55, 16.0, 41.65, 50, 40)
    with rasterio.open(
        raster_path, "w", driver="GTiff", count=4, dtype="uint8",
        width=50, height=40, crs="EPSG:32633", transform=transform,
    ) as ds:
        ds.write(np.zeros((4, 40, 50), dtype=np.uint8))

    # Register the raster's source spec so the catalog resolves source_id.
    raster_module.PROCESSORS["tinitaly_dtm"] = raster_module.RasterProcessorSpec(
        raster_id="tinitaly_dtm",
        raw_path=raw_dir / "tinitaly" / "e46005_s10.zip",
        source_id="tinitaly_1_1_e46005_s10",
        year_data=2023,
    )
    # And a matching sidecar so the source is present in the catalog.
    sidecar_t = raw_dir / "tinitaly" / "e46005_s10.zip.provenance.json"
    sidecar_t.parent.mkdir()
    sidecar_t.write_text(
        json.dumps({
            "source_id": "tinitaly_1_1_e46005_s10",
            "publisher": "INGV",
            "dataset": "TINITALY/1.1 tile",
            "url": "https://example.test/tinitaly.zip",
            "access_method": "HTTPS",
            "license": "CC-BY-4.0",
            "accessed_at": "2026-05-26T08:00:00+00:00",
            "raw_path": str(raw_dir / "tinitaly" / "e46005_s10.zip"),
            "sha256": "0" * 64,
            "byte_count": 1,
            "bbox": None,
            "year_data": 2023,
            "query": {},
        }),
        encoding="utf-8",
    )
    return config_dir, raw_dir, processed_dir


def test_build_entries_skips_empty_vector_layers(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    # Override the coastline GeoJSON to be empty.
    gpd.GeoDataFrame(
        {"layer_id": [], "source_id": [], "category": [], "year_data": []},
        geometry=[], crs="EPSG:4326",
    ).to_file(processed_dir / "coastline.geojson", driver="GeoJSON")
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="tester",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    # The vector coastline is skipped (empty); the raster still lands.
    assert {e.layer_id for e in entries if e.layer_type == "vector"} == set()
    assert {e.layer_id for e in entries if e.layer_type == "raster"} == {"tinitaly_dtm"}


def test_build_entries_skips_vectors_without_mbtiles(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    # Remove the pre-built MBTiles.
    (processed_dir / "mbtiles" / "coastline.mbtiles").unlink()
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="tester",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    assert {e.layer_id for e in entries if e.layer_type == "vector"} == set()


def test_build_entries_produces_well_formed_vector_entry(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="tester",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    vec = next(e for e in entries if e.layer_type == "vector" and e.layer_id == "coastline")
    assert vec.mapbox_tileset_id == "manfredonia-coastline-v1"
    assert vec.mapbox_tileset_url == "mapbox://tileset/tester.manfredonia-coastline-v1"
    assert vec.input_sha256 == hashlib.sha256(b"fake-mbtiles").hexdigest()
    assert "OpenStreetMap contributors" in vec.attribution
    assert "ODbL-1.0" in vec.attribution
    assert "OSM natural=coastline" in vec.description
    assert vec.mapbox_studio_url.startswith("https://studio.mapbox.com/tilesets/tester.")


def test_build_entries_handles_unknown_username(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    vec = next(e for e in entries if e.layer_type == "vector")
    assert vec.mapbox_tileset_url == "mapbox://tileset/<MAPBOX_USERNAME>.manfredonia-coastline-v1"
    assert "MAPBOX_USERNAME unset" in vec.mapbox_studio_url


def test_manifest_write_round_trip(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="tester",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    out = tmp_path / "manifest.yaml"
    manifest.write(entries, out)
    assert out.exists()
    loaded = manifest.load(out)
    assert loaded == entries


def test_manifest_write_is_byte_deterministic(tmp_path: Path):
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    cat = catalog_builder.assemble(
        config_dir=config_dir, data_raw=raw_dir, processed_dir=processed_dir,
        repo_root=tmp_path,
    )
    entries = manifest.build_entries(
        cat, username="tester",
        mbtiles_dir=processed_dir / "mbtiles",
        processed_dir=processed_dir, repo_root=tmp_path,
    )
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    manifest.write(entries, a)
    manifest.write(entries, b)
    assert a.read_bytes() == b.read_bytes()


def test_manifest_load_rejects_garbage(tmp_path: Path):
    p = tmp_path / "bogus.yaml"
    p.write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid publish manifest"):
        manifest.load(p)


def test_manifest_default_paths_use_expected_subdirs(tmp_path: Path):
    mb = manifest.default_mbtiles_dir(tmp_path)
    assert mb == tmp_path / "mbtiles"


# --- CLI ------------------------------------------------------------

def test_cli_publish_manifest_writes_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    out = tmp_path / "publish_manifest.yaml"
    # Point both the catalog builder and the manifest module at our
    # synthetic tmp tree (otherwise REPO_ROOT defaults to the real
    # repo and the manifest's relative_to() blows up).
    monkeypatch.setattr("manfredonia_map.catalog.builder.DATA_RAW", raw_dir)
    monkeypatch.setattr("manfredonia_map.catalog.builder.CONFIG_DIR", config_dir)
    monkeypatch.setattr("manfredonia_map.catalog.builder.DATA_PROCESSED", processed_dir)
    monkeypatch.setattr("manfredonia_map.publishing.manifest.REPO_ROOT", tmp_path)

    result = CliRunner().invoke(
        pub_cli.publish_manifest,
        [
            "--processed-dir", str(processed_dir),
            "--mbtiles-dir", str(processed_dir / "mbtiles"),
            "--out", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(out.read_text())
    assert payload["version"] == 1
    assert any(e["layer_type"] == "vector" for e in payload["entries"])
    assert any(e["layer_type"] == "raster" for e in payload["entries"])


def test_cli_publish_prepare_mbtiles_skips_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    # Replace the seeded coastline with an empty layer; this means
    # the CLI should skip it without running tippecanoe.
    gpd.GeoDataFrame(
        {"layer_id": [], "source_id": [], "category": [], "year_data": []},
        geometry=[], crs="EPSG:4326",
    ).to_file(processed_dir / "coastline.geojson", driver="GeoJSON")
    monkeypatch.setattr(
        "manfredonia_map.catalog.builder.DATA_RAW", raw_dir,
    )
    monkeypatch.setattr(
        "manfredonia_map.catalog.builder.CONFIG_DIR", config_dir,
    )

    # Track that tippecanoe was *not* called.
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("tippecanoe should not be called for empty layers")

    monkeypatch.setattr(tippecanoe, "build_mbtiles", _boom)
    result = CliRunner().invoke(
        pub_cli.publish_prepare_mbtiles,
        ["--processed-dir", str(processed_dir),
         "--mbtiles-dir", str(processed_dir / "mbtiles")],
    )
    assert result.exit_code == 0, result.output
    assert "(no features)" in result.output


def test_cli_publish_prepare_mbtiles_only_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir, raw_dir, processed_dir = _seed_processed_tree(tmp_path)
    monkeypatch.setattr(
        "manfredonia_map.catalog.builder.DATA_RAW", raw_dir,
    )
    monkeypatch.setattr(
        "manfredonia_map.catalog.builder.CONFIG_DIR", config_dir,
    )
    captured: list[str] = []
    monkeypatch.setattr(
        tippecanoe, "build_mbtiles",
        lambda spec, *_, **__: (captured.append(spec.layer_name) or spec.output_mbtiles),
    )

    result = CliRunner().invoke(
        pub_cli.publish_prepare_mbtiles,
        ["--processed-dir", str(processed_dir),
         "--mbtiles-dir", str(processed_dir / "mbtiles"),
         "--only", "nothing-matches"],
    )
    assert result.exit_code == 0, result.output
    assert captured == []  # filter excluded the only candidate
