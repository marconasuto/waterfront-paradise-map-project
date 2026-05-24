# Manfredonia Coastal Map — Specifications

**Status:** DRAFT — ready for Phase 2 (v0.4)
**Authoritative document.** This file is the single source of truth for scope,
architecture, layer catalog, content model, and integration points. Anything
that contradicts this file is wrong and must be reconciled here first.

> **How to use this document**
> - Every change to scope, architecture, sources, layers, or content model is
>   reflected here **before** code changes.
> - Plans in `plans/` are living checklists derived from this spec. They never
>   introduce new scope on their own.
> - When you read a section and notice it is out of date, fix it in the same
>   commit as the code change.
> - Sections marked **⏳ RESEARCH** are pending the research phase; do **not**
>   start implementation that depends on them until resolved.
> - Sections marked **❓ OPEN** require a decision from the user.

---

## 0. Document control

| Field           | Value                                |
|-----------------|--------------------------------------|
| Version         | 0.7                                  |
| Created         | 2026-05-23                           |
| Last updated    | 2026-05-24 (Phase 3g + 3h: EMODnet bathymetry via WCS; VIR manual-ingest CLI documented; OPEN-VIR-1 recorded) |
| Owner           | Marco Nasuto                         |
| Change log      | See `CHANGELOG.md` (root)            |
| Related plans   | `plans/00_overview.md` and subplans  |

---

## 1. Vision

Build a publicly shareable, interactive multi-layer map of the **Manfredonia
coastal area** (Province of Foggia, Puglia, Italy) — including the SIN site
(former Enichem), wetlands, archeological landmarks, harbours, beaches, and
mobility networks — and present it as a **Mapbox-hosted storymap** with
editable Italian content.

The project is designed so the same data + content layer can later power:
- a museum kiosk,
- urban-planning consultations,
- citizen-science campaigns,
- an MCP server exposing the map to AI agents (Claude, etc.).

## 2. Goals & non-goals

**Goals**
- Reproducible data pipeline from public source → processed GeoPackage/COG →
  Mapbox tilesets / styles → web app.
- Authoritative provenance: every layer carries source, year, license, CRS,
  acquisition date, processing version.
- Editable Italian content separated from code; future-proofed for English and
  for image/video embeds.
- Storymap with a defined slide / flow model.
- Interactivity: clickable features, opacity, layer order, basemap switch,
  optional drag-and-drop of user shapefiles/GeoPackage/GeoJSON.
- Test coverage ≥ 95 % on the Python pipeline; deterministic, non-flaky tests.
- Architecture hooks for a future MCP server (no MCP code yet).

**Non-goals (v1)**
- Real-time data streaming (sensors, AIS, etc.).
- Multi-tenant authoring UI (content is edited in files; CMS can come later).
- 3D terrain rendering beyond Mapbox's built-in DEM (custom 3D is out of scope).
- Public write APIs.

## 3. Area of Interest (AOI)

**Source polygon:** `config/aoi_source.geojson` — 10 vertices, WGS 84
(EPSG:4326), provided by the user.

**The build produces TWO AOI shapes (locked, v0.4):**

| File                              | Definition                                                                                                                                                                                                                                | Default use                                              |
|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| `config/aoi_buffered.geojson`     | Source polygon **buffered by 1 km in both directions** (seaward + landward). Buffer computed in EPSG:32633 for true metres; output in EPSG:4326. Closes OPEN-AOI-2.                                                                       | Maximum extent. Used for "free-roam" map view and for layers we want at full reach (admin boundaries, road network, etc.). |
| `config/aoi_near_coast.geojson`   | `(aoi_buffered ∩ coastal_band) ∪ mandatory_features`. The coastal band is a **2 km landward + 2 km seaward** buffer of the coastline (ISTAT comunale sea side ∪ OSM `natural=coastline`). Mandatory features are guaranteed inclusions and may extend the AOI beyond `aoi_buffered` when the source polygon is concave; the builder logs a `WARN` in that case so the user can decide whether to revise the polygon. | "Near-coast" focused view. Used for narrative slides and storymap-default layer set. |

**Mandatory features for the near-coast shape** (unioned on top of
`aoi_buffered ∩ coastal_band`, so they are always included even if they
fall outside the 2 km coastal band *or* outside `aoi_buffered` itself —
the latter triggers a logged warning):
- **SIN Manfredonia** perimeter (MASE polygon).
- **Lago Salso** (SIC IT9110005 / ZPS IT9110038) full perimeter.
- **Oasi Laguna del Re** full perimeter (resolved from MASE Natura 2000 dump
  by name + AOI bbox at build time; if not present in the dump, fall back
  to OSM `natural=wetland` + `name~"Laguna del Re"` and log a `WARN`).
- **All other wetlands** intersecting `aoi_buffered`: MASE Natura 2000
  habitats `1150*`, `1410*`, `1420*`, `1310*` (coastal/saline wetlands)
  and OSM `natural=wetland`.
- **Grotta Scaloria** — point at Contrada Scaloria buffered by 500 m so it
  appears as a small inclusion even if it sits outside the 2 km band.

**Sanity checks** the build pipeline enforces on `aoi_near_coast.geojson`:
- Lago Salso centroid inside.
- Oasi Laguna del Re centroid inside.
- Acqua di Cristo (≈ 41.6307°N, 15.9238°E) inside.
- SIN Manfredonia centroid inside.
- Grotta Scaloria point (Contrada Scaloria, ≈ 45 m a.s.l.) inside.
- Failure of any check → pipeline aborts with a precise diagnostic.

Both files are regenerated deterministically by `scripts/build_aoi.py`.
Per-layer config in `config/layers.yaml` chooses which AOI a given layer
uses (`aoi: buffered | near_coast`); the default is `near_coast` for
narrative layers and `buffered` for context layers.

Closes OPEN-AOI-1 (definition) and OPEN-AOI-2 (buffer direction) and
introduces **OPEN-AOI-3** (the optional decision: should `config/aoi.geojson`
— the historical "the one AOI" filename — alias `near_coast` or `buffered`?
Default: alias `near_coast` to preserve the v0.3 contract.).

## 4. Layer catalog (target layers)

Authoritative machine-readable catalog: `config/layers.yaml` (to be generated
from this section during implementation). The table below is the human-readable
spec; the YAML adds source URLs, download params, processing recipes, style
hints, and Mapbox tileset IDs.

Sources resolved during the Phase 1 research; details in
`docs/research/data_sources.md`.

| # | Layer                       | Type   | Primary source                                                                  | Year         | License (≈SPDX)             |
|---|-----------------------------|--------|---------------------------------------------------------------------------------|--------------|-----------------------------|
| 1 | Hydrography — surface       | vector | ISPRA *Reticolo Idrografico Nazionale 1:250.000* (national) + SIT Puglia (detail) | 2020+ rolling | CC BY 4.0 (ISPRA)           |
| 2 | Hydrography — underground   | vector | ISPRA *Carta Idrogeologica d'Italia 1:500.000* (CII500K) + Regione Puglia PTA   | 2025 (CII500K) | CC BY 4.0 (ISPRA)           |
| 3 | Topography (DTM)            | raster | **INGV TINITALY 1.1** (10 m)                                                    | 2023         | CC BY 4.0                   |
| 4 | Bathymetry / seabed         | raster | **EMODnet Digital Bathymetry DTM 2024** (≈115 m)                                | 2024         | CC BY 4.0 (EMODnet terms)   |
| 5 | SIN Manfredonia (ex-Enichem)| vector | **v1 proxy**: OSM `landuse=industrial` ("Zona Industriale di Manfredonia-Monte Sant'Angelo") — see OPEN-SIN-1. Authoritative MASE perimeter blocked (see §18). | 2024+ (OSM) | ODbL (OSM proxy); MASE perimeter pending |
| 6 | Wetlands (Zone Umide)       | vector | MASE *Rete Natura 2000* (SIC/ZSC/ZPS Dec 2025 transmission); Lago Salso = SIC IT9110005 / ZPS IT9110038 | 2025 | non-commercial, cite source |
| 7 | Road network                | vector | OpenStreetMap (Overpass, pinned by date) — primary; ANAS + SIT Puglia validation | rolling     | ODbL (OSM)                  |
| 8 | Cycle paths (ciclovie)      | vector | MIT *Sistema Nazionale Ciclovie Turistiche* (Ciclovia Adriatica); OSM detail    | 2024+        | open per MIT terms; ODbL (OSM) |
| 9 | Harbours                    | vector | AdSP Mare Adriatico Meridionale (cartografia portuale) — perimeter digitized; OSM `harbour=*` | 2024+ | per AdSP terms; ODbL (OSM)   |
| 10 | Industrial areas           | vector | ARPA Puglia anagrafe + Comune di Manfredonia PRG (zone D); OSM `landuse=industrial` | 2024+    | per source                  |
| 11 | Archeological areas        | vector | MiC *Vincoli in Rete* + GNA; explicit point for Grotta Scaloria                | rolling      | CC BY 4.0 (MiC, verify per asset) |
| 12 | Beaches                    | vector | OSM `natural=beach` + ARPA Puglia balneazione perimeters; explicit Acqua di Cristo highlight | rolling | ODbL / per ARPA terms     |
| 13 | Coastline                  | vector | ISTAT comunale (sea side) clipped against OSM `natural=coastline`               | 2024 / rolling | CC BY 3.0 (ISTAT); ODbL (OSM) |
| 14 | Administrative boundaries  | vector | ISTAT *Confini amministrativi al 1 gennaio* (annual)                            | 2024+        | CC BY 3.0 (ISTAT)           |

Highlight overrides (placed via `config/highlights.yaml`):
- **Grotta Scaloria** — Contrada Scaloria, periferia nord di Manfredonia
  (≈ 45 m a.s.l.). Source: Vincoli in Rete + Soprintendenza Foggia.
- **Acqua di Cristo** — approx **41.6307, 15.9238**, rocky karst-spring
  coast ≈ 2.2 km N of Manfredonia centre.

Notes:
- Every dataset retains a **provenance record** (source URL, accessed-on date,
  publisher, year of data, license SPDX-ish string, processing version, hash
  of raw input) inside `data/catalog.yaml`.
- Where multiple sources exist, the **canonical** one is the Italian public
  authority (ISPRA / Regione Puglia / MiC). OSM is used as a **secondary**
  source for completeness (especially mobility) and is always tagged as such.

## 5. Architecture & data flow

```
                 ┌─────────────────────────────────────────────────┐
                 │  config/  (layers.yaml, aoi*, color_scheme.yaml)│
                 │  content/it/ (slides, locations, layers)        │
                 └─────────────────────────────────────────────────┘
                                         │
                                         ▼
        acquisition         processing            publishing
   ┌──────────────┐     ┌──────────────────┐   ┌────────────────────┐
   │ WFS / HTTP / │  →  │ clip to AOI,     │ → │ tippecanoe / MTS,  │ → Mapbox Studio
   │ WMS / WCS /  │     │ reproject,       │   │ Uploads API, COGs  │   (tilesets, styles)
   │ overpass /   │     │ schema cleanup,  │   │                    │
   │ direct files │     │ topology fix     │   └────────────────────┘
   └──────────────┘     └──────────────────┘            │
          │                       │                     ▼
          ▼                       ▼               ┌───────────────────┐
     data/raw/             data/processed/        │   webapp/         │
   (immutable copy,        (GeoPackage, COG,      │   Mapbox GL JS    │
    gitignored)            GeoJSON, MBTiles)      │   storymap +      │
                                                   │   UI controls    │
                                                   └───────────────────┘
                                                            │
                                                            ▼
                                                     static host
                                                  (GH Pages / Vercel)

   parallel:                            future:
   tests/  ←  fixtures from data/       src/manfredonia_map/mcp/
            (sampled, tiny)             (interface only in v1)
```

Key principle: **idempotency**. Re-running `mfd-map run all` from a clean
checkout (given valid `.env` + working internet) reproduces every artifact
byte-for-byte where the upstream source is stable. Sources that change over
time (OSM, Mapbox) are pinned by date.

## 6. Storage & catalog

- **Raw layer (`data/raw/`)** — exactly what we downloaded, never modified.
  One subdirectory per source. Gitignored. SHA-256 recorded in catalog.
- **Interim (`data/interim/`)** — reprojection / clipping outputs. Gitignored.
- **Processed (`data/processed/`)** — final, AOI-clipped, schema-normalized:
  - Vectors → one `manfredonia.gpkg` GeoPackage with one layer per dataset
    (and a per-layer GeoJSON for the web app + diffability).
  - Rasters → Cloud-Optimized GeoTIFFs (COGs) with overviews.
  - Mobile-friendly tiles → MBTiles / PMTiles per layer for offline / fallback.
- **Catalog (`data/catalog.yaml`)** — machine-readable provenance & schema for
  every artifact. Generated by the pipeline; read by web app and tests.
- **STAC** (optional, ⏳): wrap the catalog in a minimal STAC collection so the
  data can be consumed by external tools.

## 7. Coordinate reference systems

- **Storage CRS for vectors:** **EPSG:4326** (WGS 84). Mapbox-native; avoids
  reprojection in the browser.
- **Working CRS for analysis** (buffering, area, length, distance): **EPSG:32633**
  (WGS 84 / UTM 33N). Closes OPEN-CRS-1. Rationale: matches the regional
  authority (SIT Puglia downloads ship in 32633) and the primary raster
  source TINITALY 1.1. The MASE Natura 2000 national dump is in EPSG:32632
  (WGS 84 / UTM 32N) — reproject on ingest. Fully-INSPIRE ETRS89 datasets
  (25833) are a minority of our actual sources today; reproject on ingest
  where present.
- **Storage CRS for rasters:** EPSG:3857 (Web Mercator) for COGs that will be
  served as Mapbox raster tiles; EPSG:4326 for COGs we publish via tilejson.

## 8. Stack

**Environment manager**: **pixi** (`pyproject.toml` → `[tool.pixi.*]`).
- `pixi install` produces the locked environment in `.pixi/envs/default`.
- Native binaries (`gdal`, `proj`, `geos`, `tippecanoe`, `libnetcdf`) come
  from **conda-forge** for deterministic cross-platform builds.
- Pure-Python dependencies (declared in `[project.dependencies]`) are
  installed from PyPI on top of the conda layer.
- Tasks (`pixi run lint`, `…test-cov`, `…build-aoi`, `…acquire`, …) are
  declared in `[tool.pixi.tasks]` — replaces the need for a Makefile.

**Python pipeline** (3.11):
- **Vector I/O**: `geopandas`, `pyogrio` (preferred fast driver),
  `shapely`, `pyproj`, `fiona` (fallback).
- **Raster I/O & processing**: **`xarray` + `zarr`** as the primary stack;
  chunked, lazy, Dask-backed. `rioxarray` provides the `.rio` accessor for
  reading/writing GeoTIFF / COG / NetCDF. `dask[array]` for parallel
  computation. `netCDF4` because EMODnet bathymetry ships NetCDF.
  `rio-cogeo` for COG validation/output. Intermediate raster storage is
  **Zarr** under `data/interim/`; final published rasters are **COG**
  (8-bit colormapped) under `data/processed/`.
- **OSM**: `osmnx` for high-level extracts; raw Overpass via `httpx` for
  reproducibility (we pin query + endpoint + accessed-at).
- **HTTP**: `httpx` + `tenacity` (retries with jitter).
- **Config / validation**: `pydantic` (v2), `pydantic-settings`, `pyyaml`,
  `jsonschema`.
- **CLI**: `click` (entry point `mfd-map`).
- **Tiling**: `tippecanoe` (conda-forge binary) → MBTiles; Mapbox MTS for
  hosted publish.
- **Quality**: `ruff` (lint + format), `mypy --strict`, `pytest` +
  `pytest-cov` (fail-under 95), `respx` (mock HTTP), `hypothesis`
  (property tests), `pytest-randomly` (non-flaky enforcement).

**Web app** (`webapp/`):
- `mapbox-gl-js` (v3+) + a thin app shell. Framework: still **OPEN-WEB-1**
  (default lean = Vanilla TS + Vite — minimal lock-in; content-first
  alternatives Astro / SvelteKit kept in `plans/05_web_app.md`).
- Content rendered from `content/it/**` markdown/YAML at build time.

## 9. Repository layout

```
.
├── SPECIFICATIONS.md          ← this file (source of truth)
├── CHANGELOG.md
├── README.md                  ← short, points to this spec
├── plans/                     ← living checklists (see plans/00_overview.md)
├── docs/
│   ├── research/              ← raw research notes (data sources, MCP, Mapbox)
│   ├── architecture.md
│   └── glossary.md
├── config/
│   ├── aoi_source.geojson     ← user polygon (input)
│   ├── aoi.geojson            ← buffered + coastal-clipped AOI (generated)
│   ├── layers.yaml            ← layer registry (one entry per layer)
│   ├── highlights.yaml        ← highlighted locations (editable list)
│   ├── color_scheme.yaml      ← editable color palette
│   └── basemaps.yaml          ← available basemap styles
├── content/
│   ├── it/                    ← Italian content (text, captions, slides)
│   │   ├── slides/
│   │   ├── locations/
│   │   └── layers/
│   └── schema/                ← JSON Schemas for content validation
├── data/
│   ├── raw/                   ← downloaded files (gitignored)
│   ├── interim/               ← intermediate (gitignored)
│   ├── processed/             ← final artifacts (gitignored except catalog)
│   └── catalog.yaml           ← generated catalog
├── src/manfredonia_map/
│   ├── catalog/               ← data catalog model + reader
│   ├── acquisition/           ← downloaders (one module per source kind)
│   ├── processing/            ← clip, reproject, normalize, validate
│   ├── publishing/            ← Mapbox uploads, tilesets, styles
│   ├── content/               ← content loader + schema enforcement
│   ├── mcp/                   ← interface stubs only in v1 (see §15)
│   └── cli.py                 ← `mfd-map` Click app
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── webapp/                    ← static Mapbox GL JS storymap
├── scripts/                   ← thin CLI wrappers, ad-hoc tools
├── pyproject.toml
├── .env.example
└── .gitignore
```

## 10. Mapbox integration

Decisions locked during research (`docs/research/mapbox.md`):

| Decision                  | Lock                                                  |
|---------------------------|-------------------------------------------------------|
| Vector tileset path       | Local **`felt/tippecanoe` → MBTiles** in dev; publish via **Mapbox Tiling Service (MTS)**. Uploads API is the wrong tool per Mapbox guidance. |
| Raster tileset path       | Uploads API with **8-bit GeoTIFF** input (Mapbox does not accept 16-bit). Raw COGs kept locally for analysis; published artifacts are colormapped hillshade / hypsometric tint. |
| Tile size                 | **512×512** for MBTiles uploads.                       |
| Style strategy            | **One custom style** declaring every layer; runtime visibility via `setLayoutProperty('visibility', 'visible'|'none')`. |
| Storytelling engine       | **Custom slide engine** (~300 LOC TS) driving a single GL JS map via `flyTo`. Markdown+YAML slide files; data shape kept template-compatible. |
| Token strategy            | Two tokens. Pipeline = `sk.*` with `TILESETS:READ/WRITE/LIST`, `UPLOADS:READ/WRITE/LIST`, `STYLES:WRITE/LIST` + default public scopes. Web app = `pk.*` with default public scopes, URL-restricted after deploy. Secret scopes cannot live on a `pk.*` token (Mapbox-enforced). |
| Free-tier budget          | 50,000 GL JS map loads/month, 1.5 B km²/month MTS processing free — v1 fits comfortably. |
| MapLibre fallback         | Not used in v1; choices above are compatible with a future MapLibre swap if needed. |

## 11. Web app & storymap design

- **App entry**: a single page with two views toggled by URL hash:
  - `#/map` — free-roam map with all controls (opacity, order, basemap,
    drag-and-drop overlays).
  - `#/story` — storymap: ordered slides; each slide pins camera, layers,
    legend, and content panel.
- **Slide model** (`content/it/slides/NN_<slug>.md`):
  ```yaml
  ---
  id: 03_sin_enichem
  title: "La SIN di Manfredonia"
  camera:
    center: [15.91, 41.62]
    zoom: 13.5
    bearing: 0
    pitch: 30
  layers_visible: [sin_manfredonia, hydrography_underground, coastline]
  highlights: [grotta_scaloria, acqua_di_cristo]
  media:
    - type: image
      src: media/sin_aerial_2023.jpg
      alt: "Vista aerea dell'area SIN"
  ---
  Markdown content here in Italian…
  ```
- **Layer controls** (always available, even in story view):
  - Opacity slider per layer (0–100).
  - Reorderable layer stack (drag).
  - Basemap switcher (from `config/basemaps.yaml`).
  - Drag-and-drop overlay: accept `.geojson`, `.gpkg`, `.zip` (shapefile);
    rendered as ephemeral client-side layers (never uploaded).
- **Highlighted locations** (`config/highlights.yaml`): list of named places
  (Grotta Scaloria, Acqua di Cristo, Lago Salso, …) with marker icon,
  category, color override, optional popup content reference.

## 12. Content model

- **Language**: Italian. Schema allows future locales (`content/<locale>/`).
- **Structure**:
  ```
  content/it/
    slides/        ← one file per story slide (frontmatter + Markdown)
    locations/     ← one file per highlighted location
    layers/        ← one file per layer with title, legend, attribution,
                     short description shown in the layer panel
  content/schema/
    slide.schema.json
    location.schema.json
    layer.schema.json
  ```
- **Media** (closes OPEN-MEDIA-1):
  - **Images** are committed to `content/it/media/<slug>/` (JPEG / PNG /
    WebP). Keep individual files ≤ 500 KB; larger originals stay out of
    git. Frontmatter references them as relative paths.
  - **Videos** are linked from **YouTube**. Slide frontmatter takes a
    `youtube_id` (or full URL); the web app embeds via the privacy-enhanced
    `youtube-nocookie.com` player. No raw video files in the repo.
  - Schema for `media:` entries:
    ```yaml
    media:
      - type: image
        src: media/sin_enichem/aerial_2023.jpg
        alt: "Vista aerea dell'area SIN"
        credit: "ARPA Puglia, 2023"
      - type: youtube
        id: "dQw4w9WgXcQ"             # or url: "https://youtu.be/..."
        title: "Documentario Grotta Scaloria"
        credit: "Soprintendenza Foggia"
    ```
- **Editing UX**: every file is plain text + frontmatter; a non-technical
  editor can change wording without touching code.

## 13. Color scheme

- File: `config/color_scheme.yaml`.
- One palette with named tokens (e.g., `sea`, `wetland`, `industrial`,
  `archeological`, `road_primary`, `cycle`). Each token has a hex value and
  an accessibility-tested contrast pair for labels.
- Map styles reference tokens, not raw hex values; changing the palette is a
  one-file edit.

## 14. Interactivity

- **Click on a feature**: opens a popup driven by a small template; data
  fields come from the feature, narrative text from `content/it/layers/`
  or `content/it/locations/` keyed by feature ID.
- **Hover**: cursor change + outline highlight (no popup) on interactive layers.
- **Layer panel**: visibility toggle, opacity slider, drag-handle for order,
  source attribution (year + publisher) shown inline.
- **Basemap panel**: list from `config/basemaps.yaml`; default plus at least
  one satellite, one terrain, one minimal.
- **User overlay drop zone**: accepts `.geojson`, `.gpkg`, `.zip` (shapefile),
  parses client-side, adds as ephemeral layer with default style.

## 15. MCP integration hooks (design now, build later)

Major finding from research (`docs/research/mcp_mapbox.md`): **an official
Mapbox MCP server already exists** (<https://github.com/mapbox/mcp-server>),
exposing geocoding, search, directions, matrix, static maps and isochrone.
There is also an official **Mapbox DevKit MCP** for AI coding agents
(tokens / styles / tilesets) and a **mapbox/mcp-docs-server** for docs Q&A.

This means our MCP design changes posture: we are *not* designing for a
hypothetical future server — we are designing **to compose with the
official Mapbox MCP server**. Our MCP layer must contribute the
project-specific tools the Mapbox server cannot provide (our catalog, our
Italian content, AOI-clipped queries).

We still do **not** ship an MCP server in v1. We do define:

- `src/manfredonia_map/catalog/` — stable Python API `list_layers()`,
  `get_layer(id)`, `get_feature_at(lat, lon)`, `clip_to_polygon(layer, geojson)`,
  `summarize_layer_in_polygon(layer, geojson)`.
- `src/manfredonia_map/content/` — `get_slide(id)`, `get_location(id)`,
  `list_locations()`, `get_layer_content(id)`.
- `src/manfredonia_map/mcp/` — v1 contains only:
  - `protocol.py` — typed dataclasses for each tool's input/output, shaped
    to be MCP-compatible (see `docs/research/mcp_mapbox.md` §4 for the
    concrete sketch).
  - `bridges.py` — pure functions adapting catalog/content to those shapes.
  - `README.md` — wiring guide for the future server module.
- **No** MCP library dependency in v1.

Post-v1 (v1.1) cost estimate from the research: **~2–3 person-days** for a
senior engineer to add a `server.py` using the official Python MCP SDK
(FastMCP-style), wiring our bridges to MCP tools and shipping a Claude
Desktop config that composes our server alongside the official Mapbox
server.

Use cases (for design pressure today, ship target post-v1):
- **Museum kiosk**: Claude answers visitor questions citing layer features.
- **Urban planning**: Claude proposes scenarios using AOI + layer overlays
  (`clip_to_polygon`, `summarize_layer_in_polygon`).
- **Citizen science**: Claude ingests user reports as new GeoJSON layers
  via a moderation queue.

## 16. Quality

- **Lint/format**: `ruff` (config in `pyproject.toml`). CI fails on any lint
  warning.
- **Types**: `mypy --strict`.
- **Docstrings**: required on every public method/function (Google style),
  enforced by `ruff` rule set `D`.
- **Tests**: `pytest` with `--cov-fail-under=95`. Network access blocked by
  default; integration tests requiring network are marked `@pytest.mark.network`
  and only run in dedicated CI jobs.
- **Determinism**: tests use `pytest-randomly` (run order randomized;
  any order-dependence is a bug). HTTP is mocked with `respx`. Time is
  controlled by `freezegun`-style fixtures. File system writes use
  `tmp_path`. The pipeline never writes outside `data/` and `.env`.
- **Test data**: tiny snapshots in `tests/fixtures/`, not the full datasets.

## 17. Deployment

- **Web app**: static build, deployed to GitHub Pages (default) or Vercel /
  Netlify. CI: GitHub Actions workflow `deploy.yml` builds `webapp/dist/`
  and pushes to `gh-pages` branch.
- **Data pipeline**: not a service; runs locally or in a manual GitHub Action
  on schedule (e.g. monthly OSM refresh). Outputs are pushed to Mapbox Studio
  via the secret token (in CI secrets, never committed).
- **Versioning**: semver on the pipeline; storymap content versioned by git.

## 18. Open questions

| ID            | Question                                                                  | Owner | Status |
|---------------|---------------------------------------------------------------------------|-------|--------|
| OPEN-AOI-1    | Definition of "coastal part" of the buffered polygon (see §3)             | user  | closed — **2 km landward + 2 km seaward of coastline**, plus mandatory inclusions (SIN, Lago Salso, Oasi Laguna del Re, wetlands, Grotta Scaloria) |
| OPEN-AOI-2    | Should the AOI buffer extend into the sea, onto land, or both             | user  | closed — **both** |
| OPEN-AOI-3    | What does `config/aoi.geojson` alias — buffered or near-coast?            | spec  | open — default **near_coast** to preserve v0.3 contract; flip if downstream insists |
| OPEN-CRS-1    | UTM 33N (32633) vs ETRS89/UTM 33N (25833) as working CRS                  | spec  | closed — **EPSG:32633** (research) |
| OPEN-LAYERS-1 | Which OSM tag families count as "walkable paths" beyond `highway=footway` | spec  | closed — `footway|path|pedestrian|track|steps`, plus `foot=yes|designated`; CAI hiking relations included |
| OPEN-BATHY-1  | EMODnet (license CC BY) vs IIM (national) for nearshore bathymetry        | spec  | closed — **EMODnet DTM 2024** (IIM is paywalled / ENC-only; cited as authoritative) |
| OPEN-WEB-1    | Vanilla TS vs SvelteKit vs Astro for `webapp/`                            | spec  | open — default lean **Vanilla TS + Vite**; revisit when building the web app |
| OPEN-STORY-1  | Fork Mapbox Storytelling template vs build a custom slide engine          | spec  | closed — **custom slide engine** |
| OPEN-MEDIA-1  | Where to host images/video — repo, S3, Mapbox, other                      | user  | closed — **images in repo** under `content/it/media/`; **videos as YouTube embeds** |
| OPEN-MCP-1    | Which official Mapbox MCP server (if any) to target                        | spec  | closed — official **<https://github.com/mapbox/mcp-server>** + DevKit MCP composed alongside our future server |
| OPEN-LICENSE-1 | MASE Natura 2000 is "non-commercial" — confirm museum/urban-planning use is OK | user | closed — **confirmed** by user 2026-05-23; cite source on every layer use |
| OPEN-OSM-1    | Confirm we accept ODbL attribution for OSM-derived layers in the storymap | user  | closed — **confirmed** by user 2026-05-23; ODbL attribution shown in legend + footer |
| OPEN-STACK-1  | Raster library choice (added v0.3)                                        | user  | closed — **xarray + zarr + rioxarray + dask**; pixi for environment management |
| OPEN-VIR-1    | Authoritative MiC *Vincoli in Rete* archaeological vincoli are not exposed via a public, programmatic WFS / WMS URL. The portal at `vincoliinrete.beniculturali.it` only allows per-site KML / CSV / PDF export through manual UI navigation; the internal WFS layer is gated by institutional auth. Same gap on GNA (`gna.cultura.gov.it`) and SITAP (`sitap.cultura.gov.it`). Options: (a) formal MiC data request, (b) per-site manual KML export via `mfd-map acquire vir ingest --kml`, (c) keep OSM `historic=archaeological_site` (Grotta Scaloria + Siponto + Parco archeologico + Coppa Nevigata) as the v1 proxy. | user | **open — v1 ships with OSM proxy + manual-ingest CLI** |
| OPEN-SIN-1    | Authoritative MASE SIN-5 Manfredonia perimeter is not exposed via a public, programmatic URL. The SIN page on `bonifichesiticontaminati.mite.gov.it/sin-5/` shows a map image but no shapefile/GeoJSON/WFS link; MOSAICO/ReNDiS expose WFS only behind the ISPRA metadata catalog UI; `sgi2.isprambiente.it/geoserver` does not host SIN. Options: (a) formal data request to MASE/ISPRA, (b) manual digitization from the SIN-5 decree maps, (c) keep OSM `landuse=industrial` ("Zona Industriale di Manfredonia-Monte Sant'Angelo") as the v1 proxy. | user | **open — v1 ships with the OSM proxy** |

## 19. Glossary (short)

- **SIN** — *Sito di Interesse Nazionale*: nationally designated contaminated
  site, here the former Enichem plant near Manfredonia / Monte Sant'Angelo.
- **Zone umide** — wetlands; here Lago Salso, Oasi Laguna del Re, etc.
- **AOI** — Area of Interest.
- **RNDT** — *Repertorio Nazionale dei Dati Territoriali*.
- **PCN** — *Portale Cartografico Nazionale*.
- **MiC / MiBACT** — Italian Ministry of Culture (heritage data).
- **ISPRA** — *Istituto Superiore per la Protezione e la Ricerca Ambientale*.
- **IIM** — *Istituto Idrografico della Marina*.
- **MTS** — Mapbox Tiling Service.
- **COG** — Cloud-Optimized GeoTIFF.
- **MBTiles / PMTiles** — packaged tile formats.
- **MCP** — Model Context Protocol; standardizes tools exposed to AI clients.

## 20. References

Curated during research and stored in `docs/research/`:
- `docs/research/data_sources.md` — Italian geoportals and dataset inventory.
- `docs/research/mapbox.md` — Mapbox APIs, tiling, storytelling.
- `docs/research/mcp_mapbox.md` — MCP server landscape for Mapbox.
- `docs/research/crs_choices.md` — CRS rationale.
