# Master plan — Manfredonia coastal map

> Derived from `SPECIFICATIONS.md`. Do not introduce scope here that is not
> in the spec; update the spec first. Each item below is a living checkbox —
> tick only when actually done and verified.

## Phase 0 — Foundation (in flight)

- [x] Confirm foundational decisions with user (project root, Mapbox token,
      MCP scope, deployment) — 2026-05-23.
- [x] Initialize git repo and directory skeleton.
- [x] Write `SPECIFICATIONS.md` v0.1 (single source of truth).
- [x] Write plan + subplans (this file and `plans/01..09_*.md`).
- [ ] `.env.example`, `pyproject.toml`, `.gitignore` — drafted, verify after
      research adjusts dependencies.
- [ ] First commit on `main` once foundation is sane.

## Phase 1 — Research (must complete before any data code)

- [x] **Data sources** — `docs/research/data_sources.md` complete.
  - [x] Every layer in spec §4 mapped to a concrete dataset (URL, license,
        year, format, CRS). Italian-first preference held.
  - [x] OSM decided primary for road / cycle / harbour detail; ISPRA / MASE /
        SIT Puglia primary for hydrography, wetlands, SIN, archeology.
- [x] **Mapbox** — `docs/research/mapbox.md` complete.
  - [x] Local tippecanoe → MBTiles → MTS for vectors; Uploads API for
        rasters (8-bit GeoTIFF input).
  - [x] Custom slide engine (not the storytelling template fork).
  - [x] Free-tier quotas: 50k loads/mo + 1.5 B km²/mo MTS processing.
- [x] **MCP** — `docs/research/mcp_mapbox.md` complete.
  - [x] Inventory done. Official Mapbox MCP server exists: <https://github.com/mapbox/mcp-server>.
  - [x] v1 interface stubs designed (dataclasses + bridges, no MCP lib import).
- [ ] **AOI clarification** with user (OPEN-AOI-1, OPEN-AOI-2 in spec) —
      **carried into Phase 2**.
- [x] Update `SPECIFICATIONS.md` open-questions table and §7 / §10 / §15
      with research conclusions (v0.2).

**All Phase-1 user decisions resolved 2026-05-23** (see spec §18):
- [x] OPEN-AOI-1 — coastal part = 2 km landward + 2 km seaward of coastline.
- [x] OPEN-AOI-2 — buffer in both directions.
- [x] OPEN-MEDIA-1 — images in repo, videos as YouTube embeds.
- [x] OPEN-LICENSE-1 — Natura 2000 non-commercial use confirmed.
- [x] OPEN-OSM-1 — ODbL attribution accepted.
- [x] New OPEN-STACK-1 — raster libs locked to xarray + zarr + rioxarray +
      dask; environment via **pixi**.

Phase 2 is unblocked.

## Phase 2 — AOI & catalog

- [x] `scripts/build_aoi.py` + `src/manfredonia_map/aoi/` (builder, io,
      sanity, cli) — deterministic, 26/26 tests, 97% coverage. Produces
      `config/aoi_buffered.geojson`, `config/aoi_near_coast.geojson`,
      `config/aoi.geojson` (alias). The near-coast shape falls back to
      `aoi_buffered` with warnings until coastline + mandatory features
      are acquired in Phase 3 (this is expected and logged).
- [x] `config/layers.yaml`, `config/highlights.yaml`,
      `config/color_scheme.yaml`, `config/basemaps.yaml`,
      `config/build.yaml` — editable scaffolding for the registry, the
      palette, basemaps, highlights, and build parameters.
- [ ] `data/catalog.yaml` schema + generator (deferred to Phase 3 — needs
      real acquisition outputs to write against).
- [ ] `config/layers.yaml` — one entry per layer (id, source, year, license,
      CRS, processing recipe, mapbox tileset id, style hints).
- [ ] `config/highlights.yaml`, `config/color_scheme.yaml`,
      `config/basemaps.yaml` — initial editable values.
- [ ] `data/catalog.yaml` schema + generator.

## Phase 3 — Acquisition (in flight)

- See `plans/01_data_acquisition.md`.
- [x] **OSM layer registry** — `osm.LAYERS` + `mfd-map acquire osm <layer>`
      + `mfd-map acquire osm all`. 6 layers covered.
- [x] **Coastline** — OSM `natural=coastline` (4 LineStrings, ~88 KB, ODbL).
- [x] **Roads** — OSM `highway=*` (2,770 features, ~5.8 MB, ODbL).
- [x] **Cycle paths** — OSM `highway=cycleway` / `bicycle=designated`
      (2 features — sparse in the AOI, will augment with MIT Ciclovia
      Adriatica later).
- [x] **Harbours** — OSM `harbour=*` / `landuse=harbour` /
      `man_made=pier|breakwater` (52 features).
- [x] **Beaches** — OSM `natural=beach` (19 features).
- [x] **Wetlands** — OSM `natural=wetland` (27 polygons; includes
      *Lago Salso* — 3 features — and *Palude Frattarolo*).
- [x] **Mandatory points loader** — `config/mandatory_locations.yaml`
      drives buffered-point inclusions for the AOI builder until
      authoritative perimeters arrive.
- [ ] **Promote OSM wetlands → mandatory features** for the AOI builder
      (Phase 4 — filter Lago Salso polygons and write them under
      `data/processed/mandatory_for_aoi/`).
- [ ] **MASE Natura 2000 SIC/ZPS** perimeters (filter to IT9110005 /
      IT9110038 / Oasi Laguna del Re).
- [ ] **SIN Manfredonia** perimeter — MASE / ISPRA.
- [ ] **Archeology** — MiC Vincoli in Rete (Grotta Scaloria + Siponto).
- [ ] **DTM** — TINITALY tile(s) covering the AOI.
- [ ] **Bathymetry** — EMODnet 2024 tile(s) covering the AOI.
- [ ] **Admin boundaries** — ISTAT 2024.

## Phase 4 — Processing

- See `plans/02_data_processing.md`.

## Phase 5 — Mapbox publishing

- See `plans/04_mapbox_integration.md`.

## Phase 6 — Web app + storymap

- See `plans/05_web_app.md` and `plans/06_storymap.md`.

## Phase 7 — Content authoring

- See `plans/05_web_app.md` §content.

## Phase 8 — Testing & CI

- See `plans/08_testing.md`.

## Phase 9 — Deployment

- See `plans/09_deployment.md`.

## Phase 10 — Optional: MCP server (post-v1)

- See `plans/07_mcp_hooks.md`.

---

## Definition of done (v1)

- All layers in spec §4 ingested, processed, and visible on the map.
- Storymap with N≥6 slides covering: intro, SIN, wetlands (Lago Salso),
  archeology (Grotta Scaloria), beaches (Acqua di Cristo), harbours,
  industry & cycle paths.
- Italian content editable without touching code; English-ready scaffold.
- Coverage ≥ 95 %, `ruff check` clean, `mypy --strict` clean.
- Public storymap URL live.
- `SPECIFICATIONS.md` matches reality.
