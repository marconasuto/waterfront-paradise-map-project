# Subplan — Mapbox integration

> Owns `src/manfredonia_map/publishing/`. Research deliverable lives in
> `docs/research/mapbox.md`.

## Research

- [ ] Confirm tileset creation path: **local tippecanoe → MBTiles → Uploads
      API** vs **MTS recipes**. Note free-tier MTS processing limits.
- [ ] Confirm raster path: COG → raster tileset via Uploads; size cap.
- [ ] Style strategy: single style with `setLayoutProperty` toggles vs many
      styles. Default: one style.
- [ ] Storytelling: fork `mapbox/storytelling` template vs custom slide
      engine. Decision sealed in `docs/research/mapbox.md`.
- [ ] Free-tier quotas: monthly map loads, tileset hosting GB, MTS
      processing units. Document the limits we will operate inside.

## Implementation

```
src/manfredonia_map/publishing/
    __init__.py
    mapbox_client.py     ← thin httpx wrapper around the relevant endpoints
    tilesets.py          ← create/replace tilesets from MBTiles
    rasters.py           ← upload COGs as raster tilesets
    styles.py            ← read/write style JSON
    tippecanoe.py        ← subprocess wrapper, deterministic flags
```

## Tasks

- [ ] Pipeline command `mfd-map publish all|<layer>`:
  - For each vector layer with `mapbox.tileset_id` set:
    - tippecanoe → MBTiles with deterministic flags
    - Upload as MBTiles tileset
    - Update style layer source URL
  - For each raster layer:
    - Validate COG with `rio cogeo validate`
    - Upload as raster tileset
  - Update Mapbox Studio style via Styles API.
- [ ] CI publishes only on tag `v*` to avoid waste.

## Acceptance

- [ ] Web app can render every layer from Mapbox-hosted tiles.
- [ ] Re-publishing the same processed data produces no-op API calls
      (idempotent, hash-aware).
