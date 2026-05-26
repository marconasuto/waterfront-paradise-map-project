"""Phase 5 — Mapbox publishing.

Phase 5 turns the artifacts under ``data/processed/`` into Mapbox-ready
tilesets. It is split into two slices:

- **5a (this module set)** — local preparation:
  - :mod:`tippecanoe` shells out to the ``tippecanoe`` binary (vendored
    via conda-forge) to turn each per-layer GeoJSON into an MBTiles.
  - :mod:`manifest` reads ``data/catalog.yaml`` and emits a
    ``data/publish_manifest.yaml`` with the suggested ``tileset_id``,
    description, attribution, source path, and a Mapbox Studio
    "add tileset" URL for every vector and raster layer.
  - :mod:`cli` exposes ``mfd-map publish prepare``.

- **5b (future)** — actual uploads via the MTS API + the Uploads API
  (raster). Will reuse the same manifest as its input.
"""

from manfredonia_map.publishing import manifest, settings, tippecanoe, uploads_api

__all__ = ["manifest", "settings", "tippecanoe", "uploads_api"]
