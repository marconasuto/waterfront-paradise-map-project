# Plan 10 — 3D basemap

Status:
- Phase 1 (Mapbox Standard + pitch + slots) — **shipped 2026-05-27**
- Phase 2 (LIDAR Terrain-RGB, first attempt) — superseded. The v1
  tileset was uploaded straight from a COG via the Uploads API, which
  recompressed the RGB channels lossily and destroyed the Terrain-RGB
  bit-pack (served tiles decoded to elevations like +131 000 m). Don't
  do this.
- Phase 2b (LIDAR Terrain-RGB via rio-rgbify MBTiles) — built + uploaded
  `marconasuto.manfredonia-terrain-rgb-v3` (PNG-tile MBTiles, fetched via
  `.pngraw`). Tiles decode correctly in isolation.
- **Phase 3 (2026-05-28) — runtime fixes + decision to use the global
  DEM for now.** Three runtime bugs were found and fixed by inspecting
  the live app in a headless browser (`scripts/inspect-map.mjs`):
    1. **Overlay layers vanished under Standard.** Fetch-and-merge of the
       Standard style JSON dropped our `manfredonia-*` sources + layers
       (Standard's `imports` document doesn't survive a naive merge).
       Fix: set the style by URL and `addOverlayLayers()` after
       `style.load` (`src/map/style-merge.ts`). This also restored the
       layer-panel toggles, which had nothing to toggle before.
    2. **`setTerrain` threw `_isValidId`.** The terrain helper
       destructured `map.getSource`/`addSource` and called them bare,
       losing the `this` binding (Mapbox methods read `this._isValidId`).
       Fix: bind to `map` (`src/map/basemap-apply.ts`). The exception was
       swallowed by Mapbox's event emitter, so it silently left the map
       with no overlay terrain.
    3. **The clipped LIDAR DEM reads flat 0 m via `setTerrain`.** Mapbox
       terrain requests a global tile pyramid; our tiny AOI-clipped
       tileset 404s for most of it, and even centred reads 0 m. A
       control test confirmed Mapbox's **global** Terrain-DEM renders the
       Gargano relief perfectly (sea 0 m → hills ~530 m). Decision: the
       3D basemaps use `terrain: true` (global 30 m DEM, exaggeration
       1.6). 30 m vs 10 m is imperceptible at city-scale 3D, and it's
       reliable. The custom-DEM code path + tileset are retained for a
       future non-clipped DEM (set `terrain_url` on a basemap to use it).

## Hard-won lessons (Phase 2b)

- **Never upload a Terrain-RGB *COG* via the Uploads API.** It treats
  the file as ordinary imagery and webp/jpeg-compresses it, which
  corrupts the elevation encoding. Package the data as a **PNG-tile
  MBTiles** (rio-rgbify `--format png`) instead.
- **`rio rgbify` wants a geographic (EPSG:4326) source.** A 3857 input
  triggers `densify_pts must be at least 2` from PROJ.
- **Fill NaN before encoding.** rio-rgbify maps NaN to the base value
  (−10 000 m), so out-of-coverage + sea pixels become a deep abyss and
  put a cliff at the coastline. Fill with 0 m.
- **`webp` tiles from Mapbox are lossy even for raster-dem** — always
  fetch `.pngraw` when verifying elevation decode.
- **Re-uploading to the same tileset id keeps a stale CDN cache.** Bump
  the version suffix (`-v2` → `-v3`) to force fresh tiles.
- **"upload complete" ≠ "tileset queryable".** Poll the TileJSON
  endpoint until it returns `tilejson` before wiring the URL in.
- **GL JS fetches a custom tileset's `.png` (palette-quantised), not
  `.pngraw`.** For a custom raster-dem, pass an explicit `tiles: [".../
  {z}/{x}/{y}.pngraw?access_token=…"]` array, not `url: "mapbox://…"`,
  or the elevation bit-pack is destroyed wherever relief needs >256
  distinct colours.
- **A tiny AOI-clipped raster-dem fights Mapbox terrain.** The terrain
  engine wants a global pyramid; a clip 404s for most of it and reads
  0 m. Either ship a full-extent DEM or use the global Mapbox DEM.
- **Don't destructure Mapbox `Map` methods.** They rely on `this`
  (`this._isValidId(...)`); a bare call throws "Cannot read properties
  of undefined (reading '_isValidId')".
- **Verify in a real (headless) browser, not just by fetching tiles.**
  `scripts/inspect-map.mjs` loads the app, queries `getTerrain()` +
  `queryTerrainElevation()`, toggles a layer, and screenshots — it
  caught all three Phase-3 bugs that unit tests + manual tile fetches
  missed.

## What landed in Phase 1

- `webapp/public/basemaps.yaml` — `standard_3d` entry, marked
  `default: true`, with `pitch: 60`. The flat dark/light entries keep
  `pitch: 0`; outdoors + satellite ship with `pitch: 45` and
  `terrain: true` (Mapbox's global DEM).
- `webapp/src/types.ts` — `BasemapEntry` now carries optional `pitch`
  + `terrain` fields.
- `webapp/src/map/basemap-apply.ts` — new module with
  `applyBasemapCamera`, `applyBasemapTerrain`, `applyBasemap` helpers.
  Tested in `tests/basemap-apply.test.ts`.
- `webapp/src/map/init.ts` — initial `pitch` honoured at map
  construction time.
- `webapp/src/main.ts` — re-applies `applyBasemap(map, currentBasemap)`
  inside the `style.load` callback, so basemap swaps reset the camera +
  terrain.
- `webapp/public/style.json` (and the mirror under
  `data/processed/style.json`) — every `manfredonia-*` overlay layer
  carries `slot: "middle"`. Standard renders them under labels but
  above terrain + water.

## What landed for Phase 2 (encoder only)

- `src/manfredonia_map/processing/terrain_rgb.py` — float-32 → Terrain-RGB
  encoder/decoder (`encode_terrain_rgb`, `decode_terrain_rgb`), DTM+bathy
  merger (`merge_dtm_bathy`), COG writer (`write_cog`), end-to-end
  `build_terrain_rgb`. Round-trip is exact to 0.05 m for elevations in
  ±10 000 m. NaN pixels emit the spec `(1, 134, 160)` no-data triplet.
- CLI: `mfd-map process terrain-rgb [--aoi … --out … --exaggeration …]`.
- Tests: `tests/unit/test_processing_terrain_rgb.py` covers encoder
  math, merge precedence, COG write, and a synthetic end-to-end run.

## What landed in Phase 2 — runtime

- `mfd-map process terrain-rgb` produced `data/processed/terrain_rgb.tif`:
  1547 × 2078 px, EPSG:3857, ~13 m/px, elevations 0 – 459 m for the
  Gargano coast inside the AOI. ~570 KB compressed COG.
- Uploaded to Mapbox via the existing `uploads_api` —
  `mapbox://marconasuto.manfredonia-terrain-rgb-v1`.
- `BasemapEntry.terrain_url` and `BasemapEntry.terrain_exaggeration`
  added to the schema (`webapp/src/types.ts`).
- `applyBasemapTerrain` now prefers `terrain_url` when set: it mounts
  the custom DEM as `custom-dem` and routes `setTerrain` there.
  Mapbox's global `mapbox-dem` stays as the fallback for outdoors +
  satellite. Returns are `"added-custom" | "added-mapbox" | "cleared"
  | "noop"` so callers can tell which path fired.
- `basemaps.yaml` ships `standard_3d` with the LIDAR tileset:

  ```yaml
  - id: standard_3d
    style_url: "mapbox://styles/mapbox/standard"
    pitch: 60
    terrain_url: "mapbox://marconasuto.manfredonia-terrain-rgb-v1"
    terrain_exaggeration: 1.3
    default: true
  ```

## Known gap — submarine bathymetry

The merger keeps DTM values where finite and falls back to bathymetry
where the DTM is NaN. TinItaly's float-32 DTM, however, encodes sea
pixels as `0.0` (not NaN), so the bathymetry currently never overrides
those flat zeros. The encoded raster therefore reads 0 m for the bay
floor instead of the EMODnet -16 m. Future fix: detect "DTM == 0 inside
the EMODnet footprint" and prefer bathymetry there, or write a coastline
mask and split the merge by region.

## Original research (kept for reference)

## Question

The user asked whether we can add a 3D basemap, possibly with LIDAR
elevation, and whether Mapbox Atlas v3 is the right tool.

## Findings (2026-05-27)

### Mapbox Atlas v3 — not what we want

Atlas v3 is Mapbox's *self-hosted, on-prem* stack. It ships the same
maps/search/nav as the cloud product but the customer runs the
containers (or S3-compatible storage). Pricing is sales-quote only,
typically five-figure annual contracts, and it's aimed at government /
enterprise customers with air-gapped or data-sovereignty requirements.

It does **not** add any 3D primitives beyond what Mapbox GL JS already
exposes. Massively overkill for a small public coastal site that
already uses a hosted Mapbox token.

### Mapbox Standard style (`mapbox://styles/mapbox/standard`) — easy win

Default style in Mapbox GL JS v3. Ships with 3D buildings everywhere
(including 3D landmark models), 3D terrain at mid zoom, and realistic
lighting/shadows/fog. Our existing raster + vector overlays drop in via
**slots** (`top` / `middle` / `bottom`) — one extra property per layer.

Free tier covers it: 50 k map loads/month, $5/1 k after.

### Custom LIDAR terrain (TinItaly DTM)

Standard's built-in terrain is Mapbox Terrain-DEM v1 (~30 m global).
For the ~10 m TinItaly DTM we'd:

1. `rio rgbify` the float-32 DTM → Terrain-RGB PNG/WebP MBTiles
   (encoding `elev = -10000 + (R*65536+G*256+B)*0.1`).
2. Upload via Mapbox Tiling Service as a raster-DEM tileset
   (`marconasuto.tinitaly-dem`).
3. In the webapp:

   ```ts
   map.addSource("tinitaly-dem", {
     type: "raster-dem",
     url: "mapbox://marconasuto.tinitaly-dem",
   });
   map.setTerrain({ source: "tinitaly-dem", exaggeration: 1.3 });
   ```

Caveat: re-encode from the **original** float-32 DTM, **not** the
existing 8-bit version under `data/processed/tinitaly_dtm_8bit.tif`.
The 8-bit loses the precision Terrain-RGB needs.

### Bathymetry below sea level

Terrain-RGB can encode negative elevations down to −10 000 m. Practical
path: merge EMODnet bathymetry + TinItaly DTM into a single VRT in the
pixi pipeline, encode them together via `rio rgbify`, upload as one
tileset. Submarine relief renders correctly; keep `exaggeration` modest
so the coast doesn't look jagged.

### Non-Mapbox alternatives (skip unless we hit a hard limit)

| Option                                                       | Cost                                          | Effort                | Preserves UX |
|--------------------------------------------------------------|-----------------------------------------------|-----------------------|--------------|
| MapLibre + Cesium ion (Google Photorealistic 3D Tiles)       | ion Commercial ~$1.2 k+/yr, per-root billing  | **major rewrite**     | no (port)    |
| MapTiler                                                     | ~$25/mo Flex; built-in Terrain-RGB            | drop-in MapLibre swap | mostly yes   |
| deck.gl `TerrainLayer` over the existing GL JS map           | free, we host tiles                           | additive overlay      | yes          |

## Recommendation

1. **First**: switch the basemap to `mapbox://styles/mapbox/standard`,
   set `pitch: 60`, port the raster overlays to use `slot: 'middle'`.
   Should be ~20 lines of code change, no new cost, gives us 3D
   buildings + global Mapbox terrain immediately. Validate the UX
   (story-map, panels, popups) still works.

2. **Then**: build a custom Terrain-RGB tileset from the merged
   float-32 TinItaly DTM + EMODnet bathymetry via `rio rgbify` in the
   pixi pipeline, upload to `marconasuto.tinitaly-dem`, and
   `setTerrain()` it. Gives us 10 m local relief + true submarine
   bathymetry while keeping everything inside the Mapbox GL JS stack
   we already use.

3. **Skip** Atlas v3 (wrong product) and Cesium / Google Photorealistic
   Tiles (rewrite cost not justified for a coastal site — photoreal
   tiles add little value where the relief actually matters: undeveloped
   coastline and seabed).

## References

- Mapbox blog: Introducing Mapbox Atlas v3
- Mapbox Standard style guide — `https://docs.mapbox.com/map-styles/standard/guides/`
- Mapbox style-spec **slots** — `https://docs.mapbox.com/style-spec/reference/slots/`
- Mapbox Terrain-RGB v1 — `https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-rgb-v1/`
- Mapbox Bathymetry v2 — `https://docs.mapbox.com/data/tilesets/reference/mapbox-bathymetry-v2/`
- `rio-rgbify` — `https://github.com/mapbox/rio-rgbify`
- Cesium ion pricing — `https://cesium.com/platform/cesium-ion/pricing/`
