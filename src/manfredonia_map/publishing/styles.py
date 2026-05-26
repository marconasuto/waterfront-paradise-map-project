"""Generate a Mapbox GL JS style JSON from the publish manifest.

A Mapbox style ties together:

- ``sources``: one per uploaded tileset (vector or raster) — referenced
  by the ``mapbox://`` URL Mapbox returns after a successful upload.
- ``layers``: stack of paint layers; *order matters* (top of the array
  is the bottom of the map). Paint colours are sourced from
  ``config/color_scheme.yaml`` via a small ``layer_id → token`` mapping
  so the palette stays a one-file edit.

The output is a single deterministic JSON file under
``data/processed/style.json``. To use it:

1. Open https://studio.mapbox.com/styles  → *New style* → *Blank* → paste
   the JSON via the "Editor" view → *Save*. Studio assigns you a
   ``mapbox://styles/<user>/<id>`` URL.
2. (Phase 5c-2 — pending) ``mfd-map publish style --upload`` will POST
   to ``/styles/v1/<user>`` instead.

The deterministic write (atomic + ``sort_keys=True``) makes the file
git-friendly so changes to the colour palette show up as clean diffs.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from manfredonia_map.paths import CONFIG_DIR, DATA_PROCESSED
from manfredonia_map.publishing import manifest as manifest_mod

#: Mapbox center for the storymap. Roughly the Manfredonia town centre.
DEFAULT_CENTER = (15.92, 41.62)
DEFAULT_ZOOM = 10.5

#: Maps each known ``layer_id`` to a paint-token in ``color_scheme.yaml``.
#: Anything not listed falls back to ``DEFAULT_COLOR_TOKEN``.
LAYER_COLOR_TOKEN: dict[str, str] = {
    "coastline": "coastline",
    "admin_boundaries": "admin",
    "hydrography_surface": "water",
    "roads": "road_primary",
    "cycle_paths": "cycle",
    "cycle_routes": "cycle",
    "harbours": "harbour",
    "beaches": "beach",
    "wetlands": "wetland",
    "natura2000": "wetland",
    "industrial_areas": "industrial",
    "sin_manfredonia": "sin",
    "archeological_areas": "archeological",
}
DEFAULT_COLOR_TOKEN = "highlight"

#: Mapbox layer-type per ``layer_id`` (vectors only — rasters handled
#: separately). Most vector layers have a "primary" geometry type that
#: dictates the paint type used.
LAYER_PAINT_TYPE: dict[str, str] = {
    "coastline": "line",
    "admin_boundaries": "line",
    "hydrography_surface": "line",
    "roads": "line",
    "cycle_paths": "line",
    "cycle_routes": "line",
    "harbours": "fill",
    "beaches": "fill",
    "wetlands": "fill",
    "natura2000": "fill",
    "industrial_areas": "fill",
    "sin_manfredonia": "fill",
    "archeological_areas": "circle",
}

#: Render order for vector layers (later = on top). Rasters always sit
#: under everything else, ordered: bathymetry, DTM colour, hillshade.
VECTOR_RENDER_ORDER: tuple[str, ...] = (
    # Polygons first (under lines + points)
    "natura2000",
    "wetlands",
    "industrial_areas",
    "sin_manfredonia",
    "harbours",
    "beaches",
    # Lines on top of polygons
    "admin_boundaries",
    "hydrography_surface",
    "roads",
    "cycle_paths",
    "cycle_routes",
    "coastline",
    # Points highest
    "archeological_areas",
)

#: Render order for rasters (first = bottom).
RASTER_RENDER_ORDER: tuple[str, ...] = (
    "emodnet_bathymetry",
    "tinitaly_dtm",
    "tinitaly_dtm_hillshade",
)


def load_color_scheme(path: Path = CONFIG_DIR / "color_scheme.yaml") -> dict[str, dict[str, str]]:
    """Read ``config/color_scheme.yaml`` and return its ``palette`` mapping."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    palette = payload.get("palette")
    if not isinstance(palette, dict):
        raise ValueError(f"{path} has no `palette` mapping")
    return palette


def _color(palette: dict[str, dict[str, str]], token: str, swatch: str = "line") -> str:
    """Return the ``swatch`` colour of ``token`` (line / fill / label)."""
    entry = palette.get(token) or palette.get(DEFAULT_COLOR_TOKEN, {})
    return str(entry.get(swatch, "#888888"))


def _vector_source_id(layer_id: str) -> str:
    """Stable source id for the Mapbox style's ``sources`` map."""
    return f"manfredonia-{layer_id}"


def _raster_source_id(layer_id: str) -> str:
    return f"manfredonia-{layer_id}"


def _vector_source(entry: manifest_mod.ManifestEntry, *, username: str) -> dict[str, Any]:
    return {
        "type": "vector",
        "url": f"mapbox://{username}.{entry.mapbox_tileset_id}",
    }


def _raster_source(entry: manifest_mod.ManifestEntry, *, username: str) -> dict[str, Any]:
    return {
        "type": "raster",
        "url": f"mapbox://{username}.{entry.mapbox_tileset_id}",
        "tileSize": 256,
    }


def _line_layer(layer_id: str, palette: dict[str, dict[str, str]]) -> dict[str, Any]:
    token = LAYER_COLOR_TOKEN.get(layer_id, DEFAULT_COLOR_TOKEN)
    width = {
        "coastline": 1.6,
        "roads": 0.8,
        "cycle_paths": 1.0,
        "cycle_routes": 1.2,
        "hydrography_surface": 1.0,
        "admin_boundaries": 1.2,
    }.get(layer_id, 1.0)
    return {
        "id": f"manfredonia-{layer_id}",
        "type": "line",
        "source": _vector_source_id(layer_id),
        "source-layer": layer_id,
        "paint": {
            "line-color": _color(palette, token, "line"),
            "line-width": width,
        },
    }


def _fill_layer(layer_id: str, palette: dict[str, dict[str, str]]) -> dict[str, Any]:
    token = LAYER_COLOR_TOKEN.get(layer_id, DEFAULT_COLOR_TOKEN)
    opacity = {
        "natura2000": 0.25,
        "wetlands": 0.5,
        "industrial_areas": 0.4,
        "sin_manfredonia": 0.45,
        "harbours": 0.5,
        "beaches": 0.6,
    }.get(layer_id, 0.5)
    return {
        "id": f"manfredonia-{layer_id}",
        "type": "fill",
        "source": _vector_source_id(layer_id),
        "source-layer": layer_id,
        "paint": {
            "fill-color": _color(palette, token, "fill"),
            "fill-opacity": opacity,
            "fill-outline-color": _color(palette, token, "line"),
        },
    }


def _circle_layer(layer_id: str, palette: dict[str, dict[str, str]]) -> dict[str, Any]:
    token = LAYER_COLOR_TOKEN.get(layer_id, DEFAULT_COLOR_TOKEN)
    return {
        "id": f"manfredonia-{layer_id}",
        "type": "circle",
        "source": _vector_source_id(layer_id),
        "source-layer": layer_id,
        "paint": {
            "circle-color": _color(palette, token, "fill"),
            "circle-radius": 5,
            "circle-stroke-color": _color(palette, token, "line"),
            "circle-stroke-width": 1.5,
        },
    }


def _vector_layer(layer_id: str, palette: dict[str, dict[str, str]]) -> dict[str, Any]:
    paint_type = LAYER_PAINT_TYPE.get(layer_id, "line")
    if paint_type == "fill":
        return _fill_layer(layer_id, palette)
    if paint_type == "circle":
        return _circle_layer(layer_id, palette)
    return _line_layer(layer_id, palette)


def _raster_layer(layer_id: str) -> dict[str, Any]:
    opacity = {
        "tinitaly_dtm": 0.6,
        "tinitaly_dtm_hillshade": 0.4,
        "emodnet_bathymetry": 0.7,
    }.get(layer_id, 0.6)
    return {
        "id": f"manfredonia-{layer_id}",
        "type": "raster",
        "source": _raster_source_id(layer_id),
        "paint": {"raster-opacity": opacity},
    }


def _index_entries(
    entries: Iterable[manifest_mod.ManifestEntry],
) -> dict[str, manifest_mod.ManifestEntry]:
    return {e.layer_id: e for e in entries}


def build_style(
    entries: list[manifest_mod.ManifestEntry],
    palette: dict[str, dict[str, str]],
    *,
    username: str,
    name: str = "Manfredonia coastal map",
    center: tuple[float, float] = DEFAULT_CENTER,
    zoom: float = DEFAULT_ZOOM,
) -> dict[str, Any]:
    """Build a complete Mapbox GL JS style document from a manifest."""
    if not username:
        raise ValueError("username is required to build mapbox:// source URLs")

    by_id = _index_entries(entries)

    sources: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.layer_type == "vector":
            sources[_vector_source_id(entry.layer_id)] = _vector_source(entry, username=username)
        elif entry.layer_type == "raster":
            sources[_raster_source_id(entry.layer_id)] = _raster_source(entry, username=username)

    layers: list[dict[str, Any]] = [
        {
            "id": "background",
            "type": "background",
            "paint": {"background-color": palette.get("admin", {}).get("fill", "#f5f5f5")},
        }
    ]
    # Rasters first (under everything).
    for raster_id in RASTER_RENDER_ORDER:
        if raster_id in by_id:
            layers.append(_raster_layer(raster_id))
    # Then vectors, in defined render order.
    for layer_id in VECTOR_RENDER_ORDER:
        if layer_id in by_id:
            layers.append(_vector_layer(layer_id, palette))

    return {
        "version": 8,
        "name": name,
        "metadata": {
            "manfredonia-map:version": "0.0.1",
            "manfredonia-map:owner": username,
        },
        "center": [center[0], center[1]],
        "zoom": zoom,
        "sources": sources,
        "layers": layers,
        "sprite": "mapbox://sprites/mapbox/light-v11",
        "glyphs": "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
    }


def write_style(style: dict[str, Any], out_path: Path) -> None:
    """Atomically write ``style`` as deterministic pretty JSON."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out_path.name + ".", dir=out_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(style, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, out_path)
        os.chmod(out_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def default_style_path(processed_dir: Path = DATA_PROCESSED) -> Path:
    """Return the default location for the generated style JSON."""
    return processed_dir / "style.json"
