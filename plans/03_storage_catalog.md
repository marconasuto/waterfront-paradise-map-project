# Subplan — Storage & catalog

> Owns `src/manfredonia_map/catalog/` and the file layout under `data/`.

## Catalog format (draft, to validate during implementation)

```yaml
# data/catalog.yaml — generated, do not hand-edit
version: 1
generated_at: "2026-05-23T12:00:00Z"
aoi:
  source_path: config/aoi_source.geojson
  buffered_path: config/aoi.geojson
  buffer_km: 1.0
  source_sha256: "…"
  built_sha256: "…"
layers:
  - id: sin_manfredonia
    title_it: "SIN Manfredonia (ex Enichem)"
    layer_type: vector            # vector | raster
    geometry_type: Polygon
    storage:
      gpkg_table: sin_manfredonia
      geojson_path: data/processed/sin_manfredonia.geojson
    source:
      publisher: "ISPRA"
      url: "https://…"
      access_method: "WFS"
      license: "CC BY 4.0"        # SPDX-ish
      year_data: 2023
      accessed_at: "2026-05-23T11:42:00Z"
      raw_sha256: "…"
    crs:
      source: "EPSG:4326"
      processed: "EPSG:4326"
    processing:
      version: "0.0.1"
      steps: [reproject, clip, normalize, topology_fix]
      output_sha256: "…"
    mapbox:
      tileset_id: "marconasuto.manfredonia-sin-2026"
      style_layer_ids: ["sin-fill", "sin-line"]
    style_hint:
      color_token: "industrial"
```

## Tasks

- [ ] `content/schema/catalog.schema.json` (and `layer.schema.json`,
      `source.schema.json`) — JSON Schema for validation.
- [ ] `src/manfredonia_map/catalog/`:
  - `models.py` — pydantic models mirroring the schema.
  - `loader.py` — read/validate `config/layers.yaml` and `data/catalog.yaml`.
  - `writer.py` — atomic catalog updates (write to tmp, fsync, rename).
  - `validate.py` — `mfd-map catalog validate` CLI.
- [ ] Stable public API used by web app build + MCP hooks:
      `list_layers()`, `get_layer(id)`, `get_feature_by_id(layer, id)`.
- [ ] Webapp build step: copy `data/catalog.yaml` → `webapp/public/catalog.json`.

## Acceptance

- [ ] `mfd-map catalog validate` passes for the v1 set.
- [ ] Catalog reader has 100 % branch coverage on its public API.
