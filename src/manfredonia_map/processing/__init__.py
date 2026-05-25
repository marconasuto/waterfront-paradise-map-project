"""Phase 4 data processing.

Transforms the 15+ raw acquisitions under ``data/raw/`` into the unified,
AOI-clipped, schema-normalized artifacts under ``data/processed/``:

- ``data/processed/<layer_id>.geojson`` — per-layer GeoJSON (EPSG:4326),
  cleaned topology, conformed to the canonical
  :data:`~manfredonia_map.processing.base.SCHEMA_COLUMNS`.
- ``data/processed/manfredonia.gpkg`` — single GeoPackage assembling
  every per-layer GeoJSON into one shippable artifact (later iteration).
- ``data/processed/<raster>.tif`` — colormapped 8-bit COG rasters for
  Mapbox raster tilesets (later iteration).

Phase 4 is intentionally **dispatcher-style**: a small registry in
``processing.normalize.NORMALIZERS`` maps every ``layer_id`` from
``SPECIFICATIONS.md`` §4 to the function that reads its raw input and
returns a clean GeoDataFrame. The CLI then runs reproject → clip →
make-valid → write atomically.
"""

from manfredonia_map.processing import base, normalize

__all__ = ["base", "normalize"]
