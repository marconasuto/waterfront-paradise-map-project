# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), SemVer.

## [Unreleased]

### Added
- 2026-05-23 — Initial project skeleton, `SPECIFICATIONS.md` v0.1
  (single source of truth), plan + subplan files under `plans/`,
  `.gitignore`, `pyproject.toml`, `.env.example`, AOI source polygon at
  `config/aoi_source.geojson`, research skeleton in `docs/research/`.
- 2026-05-23 — User decisions captured:
  - Repository initialized here with `git init`.
  - MCP server: design hooks now, build later.
  - Deployment target: static site (GH Pages / Netlify / Vercel).
  - Mapbox: secret token to be created with scopes for the pipeline.
- 2026-05-23 — Phase 2 scaffolded:
  - Package skeleton: `src/manfredonia_map/{__init__, paths, cli}.py`.
  - AOI module: `aoi/{builder, io, sanity, cli}.py` + CLI shim
    `scripts/build_aoi.py`. Pure functions, deterministic output (byte-
    identical between runs, coordinates rounded to 7 decimals, JSON keys
    sorted, atomic `mkstemp` + rename).
  - **26/26 tests passing, 97.24% coverage** (95% gate). `ruff check`
    clean. Network is hard-blocked in unit tests via `tests/conftest.py`.
  - Editable configs added: `config/{layers,highlights,color_scheme,
    basemaps,build}.yaml`.
  - `pyproject.toml` now has full pixi configuration; native geo deps
    (gdal, proj, geos, libnetcdf, tippecanoe, geopandas, pyogrio, shapely,
    pyproj, fiona, rioxarray, rasterio, xarray, zarr, dask, netcdf4,
    rio-cogeo, osmnx) come from conda-forge to avoid source builds that
    fail on paths with spaces.
  - First build produced `config/aoi_buffered.geojson` and
    `config/aoi_near_coast.geojson` (currently equal — coastline /
    mandatory features pending Phase 3) plus the `aoi.geojson` alias.
- 2026-05-23 — AOI split into two shapes (SPECIFICATIONS.md **v0.4**):
  - `config/aoi_buffered.geojson` — pure 1 km buffer.
  - `config/aoi_near_coast.geojson` — 2 km coastal band ∪ mandatory
    features (SIN, Lago Salso, Oasi Laguna del Re, wetlands, Grotta
    Scaloria 500 m buffer), intersected back with `aoi_buffered`.
  - `config/aoi.geojson` aliases `near_coast` by default (OPEN-AOI-3).
  - Per-layer `aoi:` selector in `config/layers.yaml` chooses which shape
    a given layer is clipped against.
- 2026-05-23 — User decisions resolve all Phase-1 open questions.
  SPECIFICATIONS.md bumped to **v0.3** ("ready for Phase 2"):
  - **AOI** (OPEN-AOI-1, OPEN-AOI-2): buffer 1 km in both directions,
    then clip to a 2 km landward + 2 km seaward coastal band.
  - **Media** (OPEN-MEDIA-1): images committed to `content/it/media/`;
    videos linked from YouTube (embedded via `youtube-nocookie.com`).
  - **OPEN-LICENSE-1**, **OPEN-OSM-1**: confirmed.
  - **OPEN-STACK-1** (new): raster stack = xarray + zarr + rioxarray +
    dask; vector stack = geopandas; environment via **pixi** (conda-forge
    for native binaries, PyPI for pure-Python deps).
  - Mapbox secret token received and stored in `.env` (gitignored).
    **User instructed to rotate the token** since it was shared in chat.
- 2026-05-23 — Phase 1 research complete. SPECIFICATIONS.md bumped to **v0.2**.
  - `docs/research/data_sources.md` populated: every layer mapped to a
    concrete Italian/EU public source (URL, license, year, CRS).
  - `docs/research/mapbox.md` populated: MTS over Uploads; tippecanoe
    locally; 8-bit raster path; single style + visibility toggles; custom
    slide engine; quotas; token model.
  - `docs/research/mcp_mapbox.md` populated: **official Mapbox MCP
    server discovered** (<https://github.com/mapbox/mcp-server>);
    v1 stubs designed to compose with it; v1.1 effort ≈ 2-3 person-days.
  - Closed: OPEN-CRS-1 (→ EPSG:32633), OPEN-LAYERS-1, OPEN-BATHY-1 (→ EMODnet
    DTM 2024), OPEN-STORY-1 (→ custom slide engine), OPEN-MCP-1.
  - Still open and blocking Phase 2: OPEN-AOI-1, OPEN-AOI-2, OPEN-MEDIA-1,
    OPEN-LICENSE-1, OPEN-OSM-1, OPEN-WEB-1.
