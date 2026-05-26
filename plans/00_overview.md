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
      + `mfd-map acquire osm all`. **9 layers** covered (coastline,
      roads, cycle_paths, cycle_routes, harbours, beaches, wetlands,
      industrial, archaeology).
- [x] **Coastline** — OSM `natural=coastline` (4 LineStrings, ~88 KB, ODbL).
- [x] **Roads** — OSM `highway=*` (2,770 features, ~5.8 MB, ODbL).
- [x] **Cycle paths** — OSM `highway=cycleway` / `bicycle=designated`
      (2 features — sparse in the AOI).
- [~] **Cycle routes (Ciclovia Adriatica)** — registered as
      `osm.LAYERS["cycle_routes"]` (`route=bicycle` relations) but
      **zero matches in our AOI**. Neither OSM, MIT Open Data nor
      Bicitalia exposes the Ciclovia Adriatica geometry programmatically
      for Manfredonia. Tracked as OPEN-CICLOVIA-1.
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
- [x] **MASE Natura 2000 SIC/ZPS** national bundle (transmissione CE
      dicembre 2025), 32 MB zip, EPSG:32632. 2,649 sites total. **7 sites
      intersect the AOI**: IT9110005 *Zone umide della Capitanata* (SIC+ZPS,
      contains Lago Salso), IT9110008 *Valloni e Steppe Pedegarganiche*,
      IT9110009 *Valloni di Mattinata - Monte Sacro*, IT9110014
      *Monte Saraceno*, IT9110038 *Paludi presso il Golfo di Manfredonia*
      (ZPS), IT9110039 *Promontorio del Gargano* (70k ha), IT9110041
      *Aloisa - Carapelle*. Note: "Oasi Laguna del Re" is an informal
      name; the formal Natura 2000 site is IT9110005 or IT9110038.
- [x] **SIN Manfredonia** authoritative perimeter — **Regione Puglia /
      InnovaPuglia** open-data CKAN dataset *Siti di Interesse
      Nazionale (SIN)* at
      <https://dati.puglia.it/ckan/dataset/siti-di-interesse-nazionale-sin>
      (CC-BY-4.0; bundle covers all 4 Puglia SINs; we filter
      `SITO == "MANFREDONIA"`, 5 polygons). Wired in
      `acquisition/regione_puglia.py` for reproducible re-fetch +
      `mfd-map acquire regione-puglia dataset sin`. OPEN-SIN-1 closed.
      OSM `industrial_areas` retained as a separate context layer.
- [~] **Archeology** — MiC Vincoli in Rete authoritative WFS is also
      not publicly exposed (see OPEN-VIR-1). v1 ships with:
      - the OSM `historic=archaeological_site` proxy already in place
        (Grotta Scaloria + Siponto + Parco archeologico + Coppa Nevigata)
      - `mfd-map acquire vir ingest --kml PATH --label LABEL` for the
        user to drop in manually-exported KMLs from the VIR portal UI.
- [x] **DTM** — INGV TINITALY/1.1, tile **`e46005_s10`** (~130 MB,
      CC-BY-4.0). Single tile covers the entire AOI: bbox
      15.57°E–16.40°E × 41.32°N–41.81°N in EPSG:32632, 5010×6510
      float32 cells (10 m resolution).
- [x] **Bathymetry** — EMODnet Bathymetry DTM 2024 via the WCS endpoint
      (`ows.emodnet-bathymetry.eu/wcs`, coverage `emodnet:mean`), clipped
      to the AOI bbox server-side. 393 KB GeoTIFF, EPSG:4326, 199×251
      float32 at 1/16 arc-minute (~115 m). Values are unified land+sea
      elevation (min −16.76 m near coast, max +667 m on Gargano,
      mean +63.93 m). CC-BY-4.0.
- [x] **Surface hydrography** — ISPRA `sdi.isprambiente.it/geoserver/hy`
      WFS, all 4 layers AOI-bbox clipped: `reticolo_idrografico` (27 KB,
      ~34 features incl. Cervaro + Carapelle torrents),
      `bacini_principali` (167 KB), `bacini_secondari` (147 B — none
      intersect AOI), `autorita_bacino` (127 KB). CC-BY-4.0.
- [ ] **Underground hydrography (CII500K)** — ISPRA Carta Idrogeologica
      d'Italia 1:500.000 is on `portalesgi.isprambiente.it` not the
      `hy` workspace; programmatic endpoint not yet wired up. Tracked
      as OPEN-CII500K-1.
- [x] **Admin boundaries** — ISTAT 2024 (generalizzato), 11.88 MB zip
      containing comuni / province / regioni / ripartizioni shapefiles
      in EPSG:32632. Manfredonia (PRO_COM_T=071029) and Monte
      Sant'Angelo (071033) confirmed present.

## Phase 4 — Processing (in flight)

- See `plans/02_data_processing.md`.
- [x] **4a — Scaffolding + first 3 vector normalizers.**
      `src/manfredonia_map/processing/{__init__, base, normalize, cli}.py`
      + `mfd-map process vector <layer_id>` and
      `mfd-map process vectors-all`. Generic pipeline is
      *normalize → to_storage_crs → clip_to_aoi → make_valid → write*;
      the deterministic GeoJSON writer rounds coordinates to 7 decimal
      places and serialises with `sort_keys=True` so outputs are
      byte-stable across runs (matches the AOI writer pattern).
      Three layers wired end-to-end: `coastline` (OSM, 3 features after
      clip), `admin_boundaries` (ISTAT zipped shapefile, 2 features —
      Manfredonia + Monte Sant'Angelo correctly clipped),
      `hydrography_surface` (ISPRA WFS, 14 features incl. Cervaro).
      Caught and fixed a `set_crs(..., allow_override=True)` bug that
      silently relabelled the CRS without reprojecting (would have
      corrupted any UTM source).
- [x] **4b — Remaining vector normalizers.** 9 new normalizers wired
      via a small `_normalize_osm_layer` helper + a richer
      `normalize_natura2000` that filters the MASE national bundle to
      the AOI bbox. All 12 layers run deterministically end-to-end via
      `mfd-map process vectors-all`. Output feature counts after clip
      to `aoi.geojson` (near-coast):
      `admin_boundaries=2` (Manfredonia + Monte Sant'Angelo),
      `archeological_areas=5` (incl. Grotta Scaloria + Siponto +
      Parco archeologico),
      `beaches=17`, `coastline=3`, `cycle_paths=0` (both raw paths sit
      outside near-coast AOI), `cycle_routes=0` (OPEN-CICLOVIA-1),
      `harbours=52`, `hydrography_surface=14` (incl. CERVARO),
      `industrial_areas=5` (incl. *Zona Industriale di
      Manfredonia-Monte Sant'Angelo*),
      `natura2000=5` (incl. *Zone umide della Capitanata*),
      `roads=2,047`, `wetlands=23` (incl. *Lago Salso* x2 +
      *Lago Salso - Prati allagati*). Two consecutive runs produce
      identical SHAs.
- [x] **4c — Raster processing** (DTM + bathymetry).
      `src/manfredonia_map/processing/raster.py`: read GeoTIFF (loose,
      zipped, or directory-pick-single) → reproject to EPSG:32633 →
      clip to AOI → analytical Zarr in `data/interim/` → hand-rolled
      hypsometric tint → 4-band 8-bit RGBA COG in `data/processed/`
      (Mapbox-ready). CLI: `mfd-map process raster <id>` +
      `process rasters-all`; pixi tasks `process-raster` /
      `process-rasters-all`. Real outputs:
      - `tinitaly_dtm_8bit.tif` (278 KB, 2085×1534, overviews [2, 4])
        + `tinitaly_dtm.zarr`
      - `emodnet_bathymetry_8bit.tif` (11.5 KB, 210×155)
        + `emodnet_bathymetry.zarr`
      Caught and fixed three production issues: zarr 3.x consolidated-
      metadata warning (turned off — local stores don't need it),
      rio-cogeo nodata-vs-alpha-band ambiguity (dropped explicit
      nodata since alpha encodes transparency), and the
      ``_block_network`` fixture rejecting asyncio's local socket-pair
      (now allows AF_UNIX while still blocking AF_INET/AF_INET6).
- [x] **4c-2 — DTM hillshade derivation.**
      `src/manfredonia_map/processing/hillshade.py`:
      `compute_hillshade(elevation, cellsize_x, cellsize_y, azimuth_deg,
      altitude_deg, z_factor)` implements the Esri-style lighting model
      via `numpy.gradient` central differences. `grayscale_to_rgba`
      wraps to a 4-band RGBA so it can blend on top of the
      hypsometric COG. CLI: `mfd-map process hillshade <raster_id>`
      + pixi task `process-hillshade`. Real run produces
      `tinitaly_dtm_hillshade_8bit.tif` — 2085×1534 4-band uint8,
      300 KB, internal overviews [2, 4], values 0–230 with mean 65
      (good shadow/highlight distribution).
- [x] **4d — Catalog generator.** `src/manfredonia_map/catalog/`
      (`models.py` pydantic schemas, `builder.py` walks every
      provenance sidecar + processed output, `cli.py` exposes
      `mfd-map catalog build/validate`). `data/catalog.yaml` is the
      tracked artifact (whitelisted in `.gitignore`) and the single
      source of truth Phase 5 publishing + the web app consume.
      Real `catalog-build` produced 18 sources / 13 vector layers /
      3 raster layers (incl. the hillshade derived-from link). Two
      consecutive builds produce byte-identical bytes except for the
      intentional `generated_at` timestamp; round-trip validated via
      pydantic.
- [x] **4e — Mandatory features promotion.**
      `src/manfredonia_map/processing/mandatory.py` lifts already-
      processed layers into `data/processed/mandatory_for_aoi/` for
      the AOI builder. 3 promotions wired:
      - `lago_salso` ← `wetlands.geojson` filter `name_it ~ "lago salso"`
        (2 polygons, area 0.000253 deg² — ~3× tighter than the old
        1.8 km buffered point).
      - `sin_manfredonia` ← whole `sin_manfredonia.geojson` layer
        (4 polygons after AOI clip, area 0.000915 deg²).
      - `grotta_scaloria` ← `archeological_areas.geojson` filter
        `name_it ~ "grotta scaloria"` (1 point buffered 300 m).
      CLI: `mfd-map process mandatory-features` + pixi task
      `process-mandatory-features`. AOI rebuild deterministic; all
      5 sanity points still inside. `config/mandatory_locations.yaml`
      kept as belt-and-suspenders fallback (the unioned polygons
      dominate the AOI shape; the points add a harmless cushion).

## Phase 5 — Mapbox publishing (in flight)

- See `plans/04_mapbox_integration.md`.
- [x] **5a — MBTiles generation + publish manifest.**
      `src/manfredonia_map/publishing/{__init__, settings, tippecanoe,
      manifest, cli}.py`. Pydantic-settings module loads
      `MAPBOX_SECRET_TOKEN` / `MAPBOX_PUBLIC_TOKEN` / `MAPBOX_USERNAME`
      from `.env`. Tippecanoe wrapper pins deterministic flags (no
      `--read-parallel`, which fragmented features in our pretty-
      printed GeoJSON). Manifest module reads the catalog and emits
      `data/publish_manifest.yaml` with one entry per vector / raster
      layer carrying the suggested Mapbox tileset id, input path +
      SHA, description / attribution (CC-BY/ODbL compliant), and a
      direct Mapbox Studio "add tileset" URL. CLI:
      `mfd-map publish prepare-mbtiles` + `publish manifest` +
      `publish prepare` (both). Real run produced 11 MBTiles
      (admin_boundaries, archeological_areas, beaches, coastline,
      harbours, hydrography_surface, industrial_areas, natura2000,
      roads, sin_manfredonia, wetlands — total ~800 KB) and a
      14-entry manifest (11 vector + 3 raster).
- [x] **5b — Programmatic upload to Mapbox.**
      `src/manfredonia_map/publishing/uploads_api.py`
      (`MapboxUploadsClient`) wraps the three-step Uploads API dance
      (POST credentials → boto3 PUT to temp S3 → POST upload spec
      → poll status). Single uniform path for both vector MBTiles
      and raster COGs. `mfd-map publish upload` reads
      `data/publish_manifest.yaml` and runs the dance per entry;
      defaults to `--dry-run` so a re-run cannot accidentally upload
      until the user passes `--no-dry-run`. boto3 added as a
      conda-forge dep for the S3 SigV4 step.
- [x] **5c-1 — Style JSON generator.**
      `src/manfredonia_map/publishing/styles.py` builds a Mapbox GL JS
      style document from `data/publish_manifest.yaml` + the palette in
      `config/color_scheme.yaml`. One `sources` entry per uploaded
      tileset (vector `mapbox://<user>.<id>` or raster `tileSize=256`);
      a deterministic layer stack — `background` → rasters
      (bathymetry, DTM, hillshade) → polygon fills (Natura2000,
      wetlands, industrial, SIN, harbours, beaches) → lines (admin,
      hydrography, roads, coastline) → circles (archeological points).
      Paint props per layer come from `LAYER_COLOR_TOKEN` +
      `LAYER_PAINT_TYPE` mappings, so editing the palette is a
      one-file change. Atomic + `sort_keys=True` write to
      `data/processed/style.json` keeps the diff git-friendly. CLI:
      `mfd-map publish style` (also as `pixi run publish-style`). Real
      run produced 14 sources + 15 layers. To go live: paste the JSON
      into Mapbox Studio (New style → Blank → Editor view) and copy
      back the assigned `mapbox://styles/<user>/<id>` URL for the
      web app config (Phase 6). 18 new unit tests; coverage 96.42%.
- [ ] **5c-2 — Programmatic style upload** (optional follow-up):
      `POST /styles/v1/<user>` so re-deploying the style is a single
      CLI command rather than a Studio paste. Deferred until the web
      app needs faster style iteration.

## Phase 6 — Web app + storymap (in flight)

- See `plans/05_web_app.md` and `plans/06_storymap.md`.
- **Decisions locked 2026-05-26** (closes OPEN-WEB-1):
  - Framework: **Vite + TypeScript** (vanilla, no SPA framework). One
    persistent map; the storymap is one HTML page that scrolls.
  - Storymap engine: **custom** IntersectionObserver-driven (~300 LOC).
  - Layout: **webapp/ subdir** of this repo. Node + pnpm vendored via
    a new pixi `web` feature so a single `pixi install -e web` brings
    up the whole frontend env.
- [x] **6a — Scaffold.** `webapp/` with Vite + TS + Mapbox GL JS.
      Strict tsconfig (noUncheckedIndexedAccess +
      exactOptionalPropertyTypes); jsdom + vitest with a 90/85
      coverage gate. `scripts/sync-config.mjs` copies
      `data/processed/style.json` + `data/catalog.yaml` +
      `config/{basemaps,highlights,color_scheme,layers}.yaml` into
      `webapp/public/` at dev/build time (the synced files are
      gitignored; canonical lives at repo root). `src/main.ts` boots
      the map from the prebuilt style; `src/map/style-loader.ts` +
      `src/map/init.ts` are pure modules with 8 vitest unit tests.
      Build produces ~498 KB gzipped (Mapbox GL JS dominates; our
      code is 1.2 KB). Pixi tasks: `web-install / web-dev / web-build
      / web-preview / web-test / web-typecheck / web-sync`.
- [ ] **6b — Style + basemap switcher.** Wire `config/basemaps.yaml`
      into a UI control that swaps the underlying basemap without
      losing layer state.
- [ ] **6c — Layer panel.** Visibility, opacity, drag-reorder,
      attribution chip showing publisher + year from the catalog.
- [ ] **6d — Highlights + popups.** Markers from
      `config/highlights.yaml`; popups load
      `content/it/locations/<id>.md`.
- [ ] **6e — Slide engine.** IntersectionObserver scroll triggers
      drive `map.flyTo()`; per-slide frontmatter controls camera +
      `layers_visible` + highlights. Markdown lives under
      `content/it/slides/`.
- [ ] **6f — Drag-and-drop overlay.** Ephemeral client-side
      `.geojson` overlay; shapefile / GeoPackage support is a stretch
      goal.
- [ ] **6g — A11y + Lighthouse.** Keyboard nav, focus rings, palette
      contrast checks; Lighthouse ≥ 90 perf / ≥ 95 a11y on a fresh
      load.

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
