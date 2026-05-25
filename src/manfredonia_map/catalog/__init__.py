"""Data catalog — the single source of truth for downstream consumers.

The catalog is a YAML file at ``data/catalog.yaml`` (deterministic write,
``sort_keys=True``) assembled from:

- every ``data/raw/**/*.provenance.json`` sidecar (one ``Source`` entry per
  raw artifact, with URL / publisher / license / SHA-256 / accessed-at /
  bbox / query as recorded at acquisition time);
- every ``data/processed/*.geojson`` (one ``VectorLayer`` entry per file,
  with feature count + geometry types + SHA-256, plus a back-reference to
  the ``Source.source_id`` taken from the layer's first feature so the
  catalog stays in sync with whatever the normalizer wrote);
- every ``data/processed/*_8bit.tif`` (one ``RasterLayer`` entry per file,
  with width / height / band count / CRS / SHA-256, plus the
  ``source_id`` looked up via ``processing.raster.PROCESSORS``);
- the three AOI shapes from ``config/`` (source polygon → buffered →
  near-coast) with their SHA-256 hashes pinning what the catalog was
  generated against.

This is what Phase 5 (Mapbox publishing) and the web app consume.
"""

from manfredonia_map.catalog import builder, models

__all__ = ["builder", "models"]
