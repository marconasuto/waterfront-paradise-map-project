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
- 2026-05-24 — Phase 3g: EMODnet bathymetry (WCS, AOI-clipped).
  - `src/manfredonia_map/acquisition/emodnet.py`:
    `EmodnetBathymetrySpec` builds a WCS 1.0.0 GetCoverage URL against
    `ows.emodnet-bathymetry.eu/wcs` for the `emodnet:mean` coverage.
    Server-side AOI clip + resolution control means we download only
    what we need (390 KB instead of a multi-GB Mediterranean tile).
  - CLI: `mfd-map acquire emodnet bathymetry [--aoi PATH]
    [--res-deg <deg>]` + pixi task `acquire-emodnet-bathymetry`.
  - Real download: 393.6 KB GeoTIFF in EPSG:4326, 199×251 float32 at
    1/16 arc-minute (~115 m, the native EMODnet 2024 resolution).
    Bounds match AOI bbox exactly. CC-BY-4.0.
  - **Note**: EMODnet 2024 `mean` is a unified land+sea DEM, not pure
    bathymetry — values in our AOI range −16.76 m (shallow seabed near
    coast) to +667 m (Gargano hills). Phase 4 processing will mask /
    re-style accordingly.
  - **75 tests passing, 98.41 % coverage**, ruff clean.
- 2026-05-24 — Phase 3f: TINITALY DTM (first raster acquisition).
  - `src/manfredonia_map/acquisition/tinitaly.py` + CLI `mfd-map
    acquire tinitaly tile <id>` + pixi task `acquire-tinitaly-tile`.
  - Decoded the undocumented tile naming scheme empirically by
    downloading a test tile and reading its GeoTIFF bbox. Scheme is
    `<dir><NN><EEE>_s<RR>` (see docstring of `tinitaly.py` for
    details).
  - `http.download_file` gained a `verify_ssl: bool = True` parameter.
    The TINITALY CLI defaults to `--no-verify-ssl` (with a loud WARN)
    because `tinitaly.pi.ingv.it` ships a self-signed cert chain
    Python rejects. Pair with `--expected-sha256` in CI.
  - Real download: `e46005_s10.zip` (130.5 MB, CC-BY-4.0). Contains one
    GeoTIFF in EPSG:32632, **covers the entire AOI** (15.57°E–16.40°E
    × 41.32°N–41.81°N, 5010×6510 float32, 10 m).
  - **70 tests passing, 98.28 % coverage**, ruff clean.
- 2026-05-24 — Phase 3e: MASE Natura 2000 acquisition.
  - `src/manfredonia_map/acquisition/mase.py`: `MaseNatura2000Spec`
    knows the URL pattern for both `daticartografici` (geometry only)
    and `tuttiicampi` (all standard-data-form fields) bundles per year.
  - CLI: `mfd-map acquire mase natura2000 [--year 2025]
    [--variant tuttiicampi|daticartografici]` + pixi task
    `acquire-mase-natura2000`. Uses the existing httpx streaming
    downloader; UTF-encoded `Trasmissione%20CE_<month><year>/` path
    handled in the spec URL.
  - Real download: `sic_zps_ita_32_tuttiicampi_2025.zip` (33.9 MB,
    non-commercial license, EPSG:32632). 2,649 SIC/ZSC/ZPS sites
    nationwide.
  - **7 sites intersect the AOI**: IT9110005 *Zone umide della
    Capitanata* (SIC+ZPS, ~14k ha, **contains Lago Salso**), IT9110008
    *Valloni e Steppe Pedegarganiche*, IT9110009 *Valloni di Mattinata
    - Monte Sacro*, IT9110014 *Monte Saraceno*, IT9110038 *Paludi
    presso il Golfo di Manfredonia* (ZPS, ~14k ha), IT9110039
    *Promontorio del Gargano* (70k ha), IT9110041 *Aloisa - Carapelle*.
  - Note: "Oasi Laguna del Re" (user's informal name) does not match a
    formal Natura 2000 site; it corresponds to IT9110005 or IT9110038
    depending on exact location.
  - **65 tests passing, 98.35 % coverage**, ruff clean.
- 2026-05-24 — Phase 3d: SIN proxy + archeology via OSM
  (SPECIFICATIONS.md **v0.6**).
  - **MASE SIN-5 Manfredonia authoritative perimeter is blocked** —
    not exposed via any public URL (bonifichesiticontaminati.mite.gov.it
    has only a map image; MOSAICO + ReNDiS sit behind catalog UIs;
    `sgi2.isprambiente.it/geoserver` does not host SIN). Documented as
    OPEN-SIN-1 in the spec. Three resolution options recorded for
    later: formal request to MASE/ISPRA, manual digitization from the
    SIN-5 decree maps, or accept the OSM proxy for v1.
  - **OSM proxy added** — new layers in `osm.LAYERS`:
    - `industrial` (`landuse=industrial|brownfield`) → 6 polygons,
      including *Zona Industriale di Manfredonia-Monte Sant'Angelo*
      (covers the ex-Enichem area) and *Idrovora Sette Poste*.
    - `archaeology` (`historic=archaeological_site`) → 5 features:
      *Grotta Scaloria* (Point), *Siponto* + *Parco archeologico di
      Siponto* (Polygons), *Coppa Nevigata*.
  - SPECIFICATIONS.md §4 row 5 updated to point at the OSM proxy with
    a forward reference to OPEN-SIN-1.
  - **60 tests passing, 98.21 % coverage**, ruff clean.
- 2026-05-24 — Phase 3c: generic HTTPS downloader + ISTAT admin boundaries.
  - `src/manfredonia_map/acquisition/http.py`: streaming downloader
    (httpx + tenacity exponential-backoff retries), atomic
    tempfile+rename write, SHA-256 streamed during download, optional
    expected-SHA verification, custom headers, mode 0644 on success.
  - `src/manfredonia_map/acquisition/istat.py`: `IstatBoundariesSpec`
    knows the URL template for both generalizzato (~12 MB) and
    non-generalizzato (~70 MB) bundles per year.
  - CLI: `mfd-map acquire istat boundaries [--year 2024]
    [--generalized/--detailed]` + pixi task `acquire-istat-boundaries`.
  - Real download: `Limiti01012024_g.zip` (11.88 MB, CC-BY-3.0, EPSG:32632).
    Contains Comuni/Province/Regioni/Ripartizioni shapefiles for all of
    Italy (7,899 comuni). Manfredonia (PRO_COM_T=071029) and Monte
    Sant'Angelo (071033) confirmed present.
  - **58 tests passing, 98.21 % coverage**, ruff clean. respx is now
    used to mock httpx in unit tests.
- 2026-05-24 — Phase 3b: OSM bulk acquisition.
  - Refactored `osm.py` around an `OsmLayerSpec` registry; 6 layers
    declared (coastline, roads, cycle_paths, harbours, beaches, wetlands).
  - CLI moved under `acquire osm <layer>` and `acquire osm all`;
    pixi tasks `acquire-osm-coastline`, `acquire-osm-all`.
  - `_persist_osm_layer` is a single shared helper that writes the
    GeoJSON + provenance sidecar for any layer in the registry. pyogrio
    handles nested-type columns (osmnx returns list/dict cells)
    natively — no manual coercion needed.
  - Real bulk fetch produced: 19 beaches, 4 coastline lines, 2 cycle
    paths, 52 harbour features, 2,770 roads, 27 wetlands (incl.
    *Lago Salso* x3 and *Palude Frattarolo*) — total ≈ 6 MB raw.
    Every artifact gets a `*.provenance.json` sidecar.
  - **47 tests passing, 97.81 % coverage**, ruff clean.
- 2026-05-23 — Phase 3a (acquisition foundation, SPECIFICATIONS.md **v0.5**):
  - `src/manfredonia_map/acquisition/{__init__, base, osm, cli}.py` —
    Provenance dataclass + atomic sidecar JSON writer; OSM downloader via
    `osmnx` with injectable fetcher (so unit tests never touch the
    network).
  - New CLI: `mfd-map acquire coastline` (pixi task
    `pixi run acquire-coastline`). First real network call lands
    `data/raw/coastline/coastline.geojson` (4 features, ODbL) and a
    sidecar `coastline.provenance.json` with SHA-256, byte count,
    accessed-at timestamp, bbox, query.
  - `config/mandatory_locations.yaml` — interim mandatory-features list
    (Grotta Scaloria, Lago Salso, Oasi Laguna del Re, SIN Manfredonia,
    Acqua di Cristo) with per-point buffer radii. Replaced once Phase 3
    acquires authoritative perimeters.
  - **Builder semantics change**: `aoi_near_coast` is now
    `(aoi_buffered ∩ coastal_band) ∪ mandatory_features`, i.e.,
    mandatory features extend the AOI rather than being clipped by it.
    The CLI logs a `WARN` when extension actually happens so the user
    can decide whether to revise the source polygon.
  - All 5 sanity points now inside; near-coast = 0.0127 deg² (66% of
    buffered = 0.0192 deg²). Deterministic — identical SHA on two
    consecutive builds.
  - **40 tests passing, 97.79% coverage**, `ruff check` clean.
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
