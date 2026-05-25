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
- [ ] **4c — Raster processing** (TINITALY DTM → reproject + clip +
      8-bit colormap COG; EMODnet bathymetry same; DTM hillshade).
- [ ] **4d — Catalog generator** (walk `data/raw/**/*.provenance.json`
      + processed outputs into `data/catalog.yaml`).
- [ ] **4e — Mandatory features promotion** (Lago Salso + other
      wetlands from MASE Natura 2000 IT9110005 → `data/processed/
      mandatory_for_aoi/`; rebuild AOI with real perimeters).

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
