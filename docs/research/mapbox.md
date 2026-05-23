# Research — Mapbox

> Findings from docs.mapbox.com and Mapbox-published material, 2026-05-23.
> Conclusions fold back into `SPECIFICATIONS.md` §10, §11 and
> `plans/04_mapbox_integration.md`, `plans/05_web_app.md`, `plans/06_storymap.md`.

## TL;DR (Recommended choices for v1)

| Decision                | Pick                                                   | Rationale                                                         |
|-------------------------|--------------------------------------------------------|-------------------------------------------------------------------|
| Vector tileset path     | **MTS (Mapbox Tiling Service)**                        | Official guidance; recipe-controlled, replaceable, deterministic. |
| Local fallback / debug  | **`tippecanoe` → MBTiles**                             | Identical engine; offline iteration; same output.                 |
| Raster tileset path     | **Uploads API** (with **8-bit GeoTIFF** input)         | MTS is vector-first; Uploads is the supported raster path.        |
| Style strategy          | **Single style + `setLayoutProperty` toggles**         | Official pattern in GL JS v3; backwards-compatible.               |
| Storytelling engine     | **Custom slide engine** (≤ 300 lines TS)               | Mapbox template still exists but is dated; we own layer controls. |
| Token strategy          | Two tokens: **secret (sk.)** for pipeline, **public (pk.)** for web app | Mapbox enforces: secret scopes can only live on sk tokens.        |
| Tippecanoe vs. fork     | Use **felt/tippecanoe** (community-maintained)         | mapbox/tippecanoe is archived since 2022; felt is the active fork.|

---

## 1. Vector tileset creation path — MTS vs Uploads vs local tippecanoe

**Mapbox's own guidance:** *"Mapbox recommends you use the Mapbox Tiling
Service (MTS) to create tilesets instead of the Uploads API."* MTS gives
control over zoom levels, simplification, attribute handling, and other
processing options that the Uploads API doesn't expose ([MTS guides](https://docs.mapbox.com/mapbox-tiling-service/guides/), [Uploads API](https://docs.mapbox.com/api/maps/uploads/)).

**Important constraint:** *"You can only replace tilesets created with the
Uploads API; you cannot replace an MTS tileset via Uploads."* — once you
choose a path per tileset, you are committed for that tileset's lifetime.

**Practical pattern for v1:**

```
local: GeoPackage → GeoJSON → tippecanoe → MBTiles  (deterministic, offline)
                                       │
                          (optional)   ▼
                         publish:  POST /tilesets/v1/<user>.<id>/recipe
                                   POST /tilesets/v1/<user>.<id>  (publish)
                                   POST /tilesets/v1/<user>.<id>/source
```

We will start the v1 pipeline with **local tippecanoe** to iterate offline,
then upload the resulting MBTiles via **MTS** (not the legacy Uploads API)
so we keep the ability to re-publish with recipes later. The
[`felt/tippecanoe`](https://github.com/felt/tippecanoe) fork is the
actively maintained successor to the archived `mapbox/tippecanoe`.

**Deterministic tippecanoe flags** for our scale (recommended):
- `-zg` (auto-pick maxzoom) or fixed `-z14` for production stability
- `--drop-densest-as-needed` (keep tiles under the 500 KB Mapbox limit)
- `--extend-zooms-if-still-dropping`
- `--coalesce-densest-as-needed` (for the road network)
- `--no-tile-stats` (smaller MBTiles, OK because we ship metadata in
  `catalog.yaml`)
- `--read-parallel` for speed
- `--name`, `--description`, `--attribution` (provenance baked into the
  tileset header)

## 2. Raster tileset path

- Mapbox raster uploads accept **only 8-bit GeoTIFFs**, georeferenced
  ([Upload data troubleshooting](https://docs.mapbox.com/help/troubleshooting/uploads/)).
- 16-bit DTMs (TINITALY, EMODnet) must be **downcast to 8-bit** via a
  hypsometric tint / colormap before upload, OR served as MBTiles built
  with `rio mbtiles` (or `tippecanoe` for vector-encoded contours instead).
- When packing MBTiles for Studio, use **512×512** tile size, not 256×256.
- COG is the right *intermediate* format on our side (deterministic, fast
  reprojection, easy validation with `rio cogeo validate`); Mapbox doesn't
  serve COGs natively — we upload the 8-bit raster tileset that MTS
  produces from our preprocessed GeoTIFF.

For our v1, the bathymetry and DTM will be **published as a colored
hillshade / hypsometric tint** GeoTIFF (8-bit) instead of raw elevation,
to fit Mapbox's raster pipeline. Raw COGs remain available locally
(`data/processed/`).

## 3. Style strategy

Single style with runtime visibility toggles is the canonical Mapbox GL JS
pattern, still recommended in v3:

```ts
const v = map.getLayoutProperty(layerId, "visibility");
map.setLayoutProperty(layerId, "visibility", v === "visible" ? "none" : "visible");
```

Source: [Show and hide layers](https://docs.mapbox.com/mapbox-gl-js/example/toggle-layers/),
[Migrate to v3](https://docs.mapbox.com/mapbox-gl-js/guides/migrate-to-v3/).

Use one custom style (forked from a Mapbox default like Light or Outdoors)
that **declares every layer**, even those hidden by default. Per-layer
opacity (`*-opacity` paint props) is also runtime-mutable. Storymap slides
declare their `layers_visible` list and the engine flips visibility
accordingly.

## 4. Storytelling / scrollytelling

- The official template at <https://github.com/mapbox/storytelling> is
  still on GitHub and the demo runs (<https://labs.mapbox.com/storytelling/>),
  but it is opinionated about HTML structure and does not naturally host
  our layer-controls UI. The MapLibre fork by digidem
  (<https://github.com/digidem/maplibre-storymap>) is a useful reference.
- We will **build a custom slide engine** (~300 LOC TS) using
  `IntersectionObserver` on slide containers and a single GL JS map driven
  by `flyTo` / `easeTo`. Slides are markdown files with YAML frontmatter
  exactly as drafted in `SPECIFICATIONS.md` §11 — we keep the data model
  Mapbox-template-compatible so we could later swap the engine without
  rewriting content.

## 5. Free-tier quotas (2026)

From <https://www.mapbox.com/pricing> and <https://docs.mapbox.com/accounts/guides/pricing/>:

- **Map loads (Mapbox GL JS):** 50,000 / month free; overage \$5/1k below
  200k, dropping to \$3/1k above.
- **A "map load" = one initialization of GL JS on a page.** Includes
  unlimited Vector & Raster Tile API requests for that load.
- **MTS processing:** *"up to 1,500,000,000 monthly square kilometers free"*
  for tileset processing. Tilesets created in Studio (UI) are exempt.
- **Other relevant free quotas (if we add features later):** 100k Directions
  requests/month, 50k Static Images/month.

**v1 budget check:** our storymap is one page; even with 50k visitors we
fit comfortably. MTS processing for ~15 layers covering a ~600 km² AOI is
nowhere near the 1.5B km²·month free tier.

## 6. Token strategy (confirms spec §10)

- **Public token (`pk.…`)** for the web app. Default public scopes only
  (`STYLES:TILES`, `STYLES:READ`, `FONTS:READ`, `DATASETS:READ`,
  `VISION:READ`). URL-restrict to the deploy domain.
- **Secret token (`sk.…`)** for the Python pipeline.
  Secret scopes we need:
  - `TILESETS:READ`, `TILESETS:WRITE`, `TILESETS:LIST` (MTS lifecycle)
  - `UPLOADS:READ`, `UPLOADS:WRITE`, `UPLOADS:LIST` (raster path)
  - `STYLES:WRITE`, `STYLES:LIST` (publishing style updates)
  - Plus default public scopes (auto-included)
- Mapbox **enforces** that secret scopes cannot be added to a `pk` token
  ([Access Tokens](https://docs.mapbox.com/help/dive-deeper/access-tokens/),
  [How to use Mapbox securely](https://docs.mapbox.com/help/dive-deeper/how-to-use-mapbox-securely/)).
- Secret tokens are shown **only once** at creation — pipeline token lands
  in `.env` immediately and is rotated via a script.

## 7. Mapbox MCP server (relevant to spec §15)

Major finding — there is an **official Mapbox MCP server**:
- Repo: <https://github.com/mapbox/mcp-server>
- Hub: <https://mcpservers.org/servers/mapbox/mcp-server>
- Tools: geocoding (v6), Search Box (text + category), Directions, Matrix,
  Static Maps, Isochrone.
- Transport: **stdio** (Node.js), configured in Claude Desktop / Claude
  Code via standard `mcpServers` config block. Hosted variant also exists.
- There is also a separate **mapbox/mcp-docs-server** for Mapbox docs Q&A
  and a **DevKit MCP server** for coding agents managing tokens, styles,
  tilesets.

This is covered in depth in `docs/research/mcp_mapbox.md`. The relevant
implication for *Mapbox integration* is: we are no longer designing to a
hypothetical MCP server — there is one we can wire up immediately when we
move past v1. Our `src/manfredonia_map/mcp/` stubs should therefore look
compatible with **official Mapbox MCP tool shapes** (so an MCP host can
mix our data tools with Mapbox's location tools coherently).

## 8. Mapbox vs MapLibre (note, not a switch)

If we ever needed to drop Mapbox SaaS, MapLibre GL JS (open-source fork of
mapbox-gl-js 1.13) is the obvious destination. We would lose:
- 3D Atmosphere / globe rendering polish
- Mapbox-hosted styles, fonts, sprites
- Mapbox Studio editor
- MTS hosted tileset processing

For v1 we stay on Mapbox; the storymap and webapp choices we are making
(single style, runtime visibility toggles, COG → 8-bit tileset) are also
compatible with MapLibre + a self-hosted tile server, so this is not a
one-way door.

## 9. Risks / gotchas

- **MTS vs Uploads is sticky per tileset** — choose once.
- **Raster only 8-bit** — bake the colormap before upload, store raw COGs
  locally for analytical use.
- **Tippecanoe upstream is archived** — use `felt/tippecanoe`.
- **Storytelling template repo updates are infrequent** — fine if we fork,
  better if we don't depend on it.
- **Token shown once** — secret token rotation needs a runbook in
  `README.md` (we will add this when we set up CI secrets).
- **Map loads counter** — counts every GL JS init; if we put both `#/map`
  and `#/story` on the same page, share the same `Map` instance.

---

## Folded-back updates to `SPECIFICATIONS.md`

- §7 — close OPEN-CRS-1: working CRS = **EPSG:32633**.
- §10 — replace placeholder decisions with the table above.
- §11 — keep custom slide engine; confirm Markdown+YAML format.
- §15 — note that an *official Mapbox MCP server exists* and adjust the
  MCP design to align with its tool shapes.
- §18 — close OPEN-CRS-1; carry OPEN-WEB-1 forward (still need final pick
  for the JS framework — Vanilla TS + Vite remains the leanest default).
