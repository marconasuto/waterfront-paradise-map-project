from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from manfredonia_map.publishing import cli as pub_cli
from manfredonia_map.publishing import manifest as manifest_mod
from manfredonia_map.publishing import styles

# --- helpers --------------------------------------------------------


def _entry(layer_id: str, layer_type: str = "vector") -> manifest_mod.ManifestEntry:
    return manifest_mod.ManifestEntry(
        layer_id=layer_id,
        layer_type=layer_type,
        source_id="src",
        mapbox_tileset_id=f"manfredonia-{layer_id}-v1",
        mapbox_tileset_url=f"mapbox://tileset/tester.manfredonia-{layer_id}-v1",
        input_path=f"data/processed/{layer_id}.x",
        input_sha256="0" * 64,
        description="d",
        attribution="a",
        mapbox_studio_url="https://studio.mapbox.com/x",
    )


_PALETTE = {
    "water": {"fill": "#1e7fb3", "line": "#0e5e8a", "label": "#ffffff"},
    "coastline": {"fill": "transparent", "line": "#0e3a5a", "label": "#0e3a5a"},
    "wetland": {"fill": "#3aa860", "line": "#22713f", "label": "#ffffff"},
    "beach": {"fill": "#f4d488", "line": "#c8a85e", "label": "#3a2e10"},
    "archeological": {"fill": "#a33b3b", "line": "#702424", "label": "#ffffff"},
    "industrial": {"fill": "#6b6b6b", "line": "#3d3d3d", "label": "#ffffff"},
    "sin": {"fill": "#c45c1a", "line": "#8a3f10", "label": "#ffffff"},
    "harbour": {"fill": "#2c3e50", "line": "#1a2733", "label": "#ffffff"},
    "road_primary": {"fill": "#222222", "line": "#000000", "label": "#ffffff"},
    "cycle": {"fill": "#8b1cb3", "line": "#5e0f7e", "label": "#ffffff"},
    "admin": {"fill": "transparent", "line": "#999999", "label": "#444444"},
    "highlight": {"fill": "#f8d030", "line": "#b09c10", "label": "#3a2e10"},
}


# --- load_color_scheme + _color -------------------------------------


def test_load_color_scheme_round_trip(tmp_path: Path):
    p = tmp_path / "cs.yaml"
    p.write_text(yaml.safe_dump({"palette": _PALETTE}), encoding="utf-8")
    out = styles.load_color_scheme(p)
    assert out == _PALETTE


def test_load_color_scheme_raises_when_no_palette(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="palette"):
        styles.load_color_scheme(p)


def test_color_helper_falls_back_to_default_token():
    assert styles._color(_PALETTE, "no-such-token", "line") == _PALETTE["highlight"]["line"]


def test_color_helper_falls_back_to_grey_when_swatch_missing():
    palette: dict[str, dict[str, str]] = {"weird": {"foo": "#abcdef"}}
    assert styles._color(palette, "weird", "fill") == "#888888"


# --- build_style ----------------------------------------------------


def test_build_style_requires_username():
    with pytest.raises(ValueError, match="username"):
        styles.build_style([], _PALETTE, username="")


def test_build_style_sources_one_per_entry():
    entries = [
        _entry("coastline"),
        _entry("hydrography_surface"),
        _entry("tinitaly_dtm", "raster"),
    ]
    style = styles.build_style(entries, _PALETTE, username="tester")
    assert set(style["sources"]) == {
        "manfredonia-coastline",
        "manfredonia-hydrography_surface",
        "manfredonia-tinitaly_dtm",
    }
    assert style["sources"]["manfredonia-tinitaly_dtm"]["type"] == "raster"
    assert style["sources"]["manfredonia-tinitaly_dtm"]["tileSize"] == 256
    assert style["sources"]["manfredonia-coastline"]["url"].startswith(
        "mapbox://tester.manfredonia-coastline"
    )


def test_build_style_layer_order_rasters_under_vectors():
    entries = [
        _entry("tinitaly_dtm", "raster"),
        _entry("coastline"),
        _entry("wetlands"),
    ]
    style = styles.build_style(entries, _PALETTE, username="tester")
    ids = [lyr["id"] for lyr in style["layers"]]
    assert ids[0] == "background"
    assert ids.index("manfredonia-tinitaly_dtm") < ids.index("manfredonia-wetlands")
    # wetland fill sits below coastline line
    assert ids.index("manfredonia-wetlands") < ids.index("manfredonia-coastline")


def test_build_style_paint_types_match_geometry():
    entries = [
        _entry("hydrography_surface"),  # line
        _entry("wetlands"),  # fill
        _entry("archeological_areas"),  # circle
    ]
    style = styles.build_style(entries, _PALETTE, username="tester")
    by_id = {lyr["id"]: lyr for lyr in style["layers"]}
    assert by_id["manfredonia-hydrography_surface"]["type"] == "line"
    assert by_id["manfredonia-wetlands"]["type"] == "fill"
    assert by_id["manfredonia-archeological_areas"]["type"] == "circle"


def test_build_style_uses_palette_colors():
    entries = [_entry("hydrography_surface"), _entry("wetlands")]
    style = styles.build_style(entries, _PALETTE, username="tester")
    by_id = {lyr["id"]: lyr for lyr in style["layers"]}
    hydro_color = by_id["manfredonia-hydrography_surface"]["paint"]["line-color"]
    wet_color = by_id["manfredonia-wetlands"]["paint"]["fill-color"]
    assert hydro_color == _PALETTE["water"]["line"]
    assert wet_color == _PALETTE["wetland"]["fill"]


def test_build_style_unknown_layer_falls_back_to_line_and_highlight():
    style = styles.build_style([_entry("brand-new")], _PALETTE, username="tester")
    layer = [lyr for lyr in style["layers"] if lyr["id"] == "manfredonia-brand-new"]
    # Unknown layer is not in VECTOR_RENDER_ORDER so it is omitted.
    assert layer == []


def test_build_style_carries_metadata_and_basemap_refs():
    style = styles.build_style([], _PALETTE, username="tester")
    assert style["version"] == 8
    assert style["metadata"]["manfredonia-map:owner"] == "tester"
    assert style["sprite"].startswith("mapbox://sprites/")
    assert style["glyphs"].startswith("mapbox://fonts/")


def test_build_style_default_center_is_manfredonia():
    style = styles.build_style([], _PALETTE, username="tester")
    assert style["center"] == [15.92, 41.62]
    assert style["zoom"] == 10.5


def test_build_style_accepts_custom_center_and_zoom():
    style = styles.build_style(
        [],
        _PALETTE,
        username="tester",
        center=(15.85, 41.6),
        zoom=12.0,
    )
    assert style["center"] == [15.85, 41.6]
    assert style["zoom"] == 12.0


# --- write_style ---------------------------------------------------


def test_write_style_round_trip(tmp_path: Path):
    style = styles.build_style(
        [_entry("coastline")],
        _PALETTE,
        username="tester",
    )
    out = tmp_path / "style.json"
    styles.write_style(style, out)
    assert out.exists()
    assert json.loads(out.read_text()) == style
    assert oct(out.stat().st_mode & 0o777) == "0o644"


def test_write_style_is_deterministic(tmp_path: Path):
    style = styles.build_style(
        [_entry("coastline"), _entry("wetlands")],
        _PALETTE,
        username="tester",
    )
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    styles.write_style(style, a)
    styles.write_style(style, b)
    assert a.read_bytes() == b.read_bytes()


# --- CLI -----------------------------------------------------------


def _seed_manifest(tmp_path: Path) -> Path:
    entries = [
        _entry("coastline"),
        _entry("wetlands"),
        _entry("tinitaly_dtm", "raster"),
    ]
    out = tmp_path / "manifest.yaml"
    manifest_mod.write(entries, out)
    return out


def _seed_palette(tmp_path: Path) -> Path:
    p = tmp_path / "color_scheme.yaml"
    p.write_text(yaml.safe_dump({"palette": _PALETTE}), encoding="utf-8")
    return p


def test_cli_publish_style_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest(tmp_path)
    palette_path = _seed_palette(tmp_path)
    out = tmp_path / "style.json"

    result = CliRunner().invoke(
        pub_cli.publish_style,
        [
            "--manifest",
            str(manifest_path),
            "--color-scheme",
            str(palette_path),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["version"] == 8
    # 3 sources from the manifest.
    assert len(payload["sources"]) == 3
    # background + raster + 2 vector layers.
    assert len(payload["layers"]) >= 4
    assert "Studio" in result.output  # operator guidance is printed


def test_cli_publish_style_passes_name_and_center(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest(tmp_path)
    palette_path = _seed_palette(tmp_path)
    out = tmp_path / "style.json"

    result = CliRunner().invoke(
        pub_cli.publish_style,
        [
            "--manifest",
            str(manifest_path),
            "--color-scheme",
            str(palette_path),
            "--out",
            str(out),
            "--name",
            "Custom map name",
            "--center-lon",
            "15.85",
            "--center-lat",
            "41.60",
            "--zoom",
            "12.0",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["name"] == "Custom map name"
    assert payload["center"] == [15.85, 41.60]
    assert payload["zoom"] == 12.0


def test_cli_publish_style_uses_default_color_scheme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MAPBOX_USERNAME", "tester")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "sk.x")
    manifest_path = _seed_manifest(tmp_path)
    out = tmp_path / "style.json"

    result = CliRunner().invoke(
        pub_cli.publish_style,
        [
            "--manifest",
            str(manifest_path),
            "--out",
            str(out),
        ],
    )
    # Uses repo's config/color_scheme.yaml — should succeed cleanly.
    assert result.exit_code == 0, result.output
    assert out.exists()
