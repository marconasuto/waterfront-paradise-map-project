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
- 2026-05-26 — Phase 5a: MBTiles + publish manifest.
  - `src/manfredonia_map/publishing/{__init__, settings, tippecanoe,
    manifest, cli}.py` wired into the top-level CLI as
    `mfd-map publish`.
  - `publishing.settings.MapboxSettings` (pydantic-settings) reads
    `MAPBOX_SECRET_TOKEN`, `MAPBOX_PUBLIC_TOKEN`, `MAPBOX_USERNAME`
    from `.env`.
  - `publishing.tippecanoe`: subprocess wrapper around the conda-forge
    tippecanoe binary. Pinned flags: `-zg --drop-densest-as-needed
    --extend-zooms-if-still-dropping --coalesce-densest-as-needed
    --no-tile-stats --force`. (Intentionally **omitted**
    `--read-parallel` — it splits the input on newlines for parallel
    reads, which fragmented features in our pretty-printed deterministic
    GeoJSON outputs. Single-thread reading is fast enough at our scale.)
  - `publishing.manifest`: reads `data/catalog.yaml` + the
    `data/processed/mbtiles/` directory + the COGs, emits a
    deterministic `data/publish_manifest.yaml`. Each entry pins the
    layer id, source id, suggested Mapbox tileset id (slugified with
    the 32-char limit), input path + SHA-256, description + attribution
    (CC-BY/ODbL-compliant), and a direct Mapbox Studio "add tileset"
    URL for manual upload.
  - CLI: `mfd-map publish prepare-mbtiles` (with `--only` / `--skip`),
    `publish manifest`, `publish prepare` (both, end-to-end). Pixi
    tasks `publish-prepare-mbtiles` / `publish-manifest` /
    `publish-prepare`.
  - Real `publish prepare` produced **11 MBTiles** (admin_boundaries,
    archeological_areas, beaches, coastline, harbours,
    hydrography_surface, industrial_areas, natura2000, roads,
    sin_manfredonia, wetlands — total ~800 KB; cycle_paths +
    cycle_routes correctly skipped because they have no features) and
    a **14-entry manifest** (11 vector + 3 raster).
  - `data/publish_manifest.yaml` whitelisted in `.gitignore` next to
    `data/catalog.yaml`.
  - **234 tests passing, 96.27 % coverage**, ruff clean.
- 2026-05-25 — Phase 4d: catalog generator (data/catalog.yaml).
  - `src/manfredonia_map/catalog/{__init__, models, builder, cli}.py`
    wired into the top-level CLI as `mfd-map catalog`.
  - Pydantic schema (`Catalog`, `AoiInfo`, `Source`, `VectorLayer`,
    `RasterLayer`) — strict, frozen, extra="forbid". Schema version 1.
  - Builder walks: every `data/raw/**/*.provenance.json` (→ `Source`),
    every `data/processed/*.geojson` (→ `VectorLayer` with feature
    count + geom types + per-feature source_id), every
    `data/processed/*_8bit.tif` (→ `RasterLayer` with width / height
    / band count / CRS, source_id resolved via
    `processing.raster.PROCESSORS`, `derived_from` set for hillshade
    siblings), plus all four AOI shapes hashed in `AoiInfo`.
  - CLI: `mfd-map catalog build` + `mfd-map catalog validate`. Pixi
    tasks `catalog-build` / `catalog-validate`.
  - `data/catalog.yaml` is the tracked artifact (already whitelisted
    in `.gitignore`); deterministic YAML (sort_keys=True, atomic
    tempfile+rename); two consecutive builds are byte-identical aside
    from the intentional `generated_at` timestamp.
  - Real `catalog-build` produced **18 sources, 13 vector layers,
    3 raster layers** (incl. the `tinitaly_dtm_hillshade` derived
    entry linked back to `tinitaly_dtm`). `catalog-validate` round-
    trips cleanly through pydantic.
  - **209 tests passing, 97.94 % coverage**, ruff clean.
- 2026-05-25 — Phase 4c-2: DTM hillshade derivation.
  - `src/manfredonia_map/processing/hillshade.py`:
    `compute_hillshade(elevation, cellsize_x, cellsize_y, azimuth_deg,
    altitude_deg, z_factor)` runs the standard Esri-style lighting model
    using `numpy.gradient` central differences (with explicit
    NaN-masking because central diff does not propagate NaN through
    a single masked cell). `grayscale_to_rgba` wraps the result in a
    4-band RGBA so it can blend on top of the hypsometric COG via a
    multiply layer.
  - CLI: `mfd-map process hillshade <raster_id>` (configurable
    `--azimuth-deg`, `--altitude-deg`, `--z-factor`); pixi task
    `process-hillshade`. Re-reads the raw GeoTIFF through the same
    `raster.read_raster` + `reproject_and_clip` so geometry stays
    aligned with the hypsometric COG.
  - Real output: `data/processed/tinitaly_dtm_hillshade_8bit.tif` —
    2085×1534, 4-band uint8, 300 KB, internal overviews [2, 4],
    values 0–230 with mean 65 (good shadow/highlight distribution).
  - **185 tests passing, 98.01 % coverage**, ruff clean.
- 2026-05-25 — Phase 4c: raster processing (DTM + bathymetry → 8-bit COG).
  - `src/manfredonia_map/processing/raster.py`: read raw GeoTIFF
    (loose, zipped, or directory-pick-single) → `rioxarray` →
    reproject to EPSG:32633 → clip to AOI → analytical Zarr under
    `data/interim/` → hand-rolled hypsometric tint (8-stop terrain
    ramp covering deep sea to alpine summit) → 4-band 8-bit RGBA
    COG under `data/processed/` (Mapbox-ready, internal overviews
    via `rio-cogeo` with the `deflate` profile).
  - CLI: `mfd-map process raster <id>` + `mfd-map process
    rasters-all [--skip ...]`. Pixi tasks `process-raster` /
    `process-rasters-all`.
  - Real outputs from `pixi run process-rasters-all`:
    - `tinitaly_dtm_8bit.tif` — 2085×1534, 4-band uint8, 278 KB,
      internal overviews [2, 4] + `tinitaly_dtm.zarr` interim.
    - `emodnet_bathymetry_8bit.tif` — 210×155, 4-band uint8, 11.5 KB
      + `emodnet_bathymetry.zarr` interim.
    Both clipped tightly to the near-coast AOI (~572 km E, 4595 km N
    to ~588 km E, 4616 km N in UTM 33N).
  - Caught and fixed three production issues:
    - zarr 3.x raised `ZarrUserWarning` for consolidated metadata
      (not in v3 spec) — disabled, local stores don't benefit.
    - rio-cogeo warned that nodata + alpha band is ambiguous — dropped
      the explicit nodata since the alpha band already encodes
      transparency.
    - `tests/conftest.py` `_block_network` fixture refused asyncio's
      AF_UNIX socket-pair (zarr 3.x uses async internally) — fixture
      now only blocks AF_INET / AF_INET6, leaving local sockets alone.
  - Hillshade derivation deferred to 4c-2 (the Zarr interim is in
    place ready to feed it).
  - **172 tests passing, 97.97 % coverage**, ruff clean.
- 2026-05-25 — Phase 4e: mandatory features promotion + AOI rebuild.
  - `src/manfredonia_map/processing/mandatory.py`: `PROMOTIONS`
    registry + `promote()` function lift already-processed layers
    into `data/processed/mandatory_for_aoi/` for the AOI builder.
  - 3 promotions wired:
    - `lago_salso` ← `wetlands.geojson` filter (2 polygons, area
      0.000253 deg² — ~3× tighter than the old 1.8 km buffered point).
    - `sin_manfredonia` ← whole `sin_manfredonia.geojson` layer
      (4 polygons after AOI clip, area 0.000915 deg²).
    - `grotta_scaloria` ← `archeological_areas.geojson` filter
      (1 point buffered 300 m, area 0.000031 deg²).
  - CLI: `mfd-map process mandatory-features` + pixi task
    `process-mandatory-features`. Both promotion and AOI rebuild
    deterministic (identical SHAs across consecutive runs).
  - All 5 AOI sanity points still inside; `config/mandatory_locations
    .yaml` kept as a belt-and-suspenders fallback (the real polygons
    dominate the AOI shape; the buffered points add a harmless
    cushion). YAML header updated to document the supersession.
  - **154 tests passing, 98.02 % coverage**, ruff clean.
- 2026-05-25 — SIN Manfredonia authoritative perimeter wired through
  the **Regione Puglia open-data CKAN** dataset (closes OPEN-SIN-1,
  SPECIFICATIONS.md **v0.9**).
  - Source identified by the user:
    <https://dati.puglia.it/ckan/dataset/siti-di-interesse-nazionale-sin>
    — *Siti di Interesse Nazionale (SIN)*, published by InnovaPuglia
    (Servizio Territorio e Ambiente), CC-BY-4.0, dataset last updated
    2025-08-04. Shapefile bundle covers all 4 Puglia SINs (Bari,
    Brindisi, Manfredonia, Taranto) in EPSG:32633.
  - `src/manfredonia_map/acquisition/regione_puglia.py`:
    `RegionePugliaSpec(dataset_id="sin")` knows the canonical CKAN
    download URL (dataset 70c4d257…, resource 7263c82e…).
  - CLI: `mfd-map acquire regione-puglia dataset sin` + pixi task
    `acquire-regione-puglia-sin`. Reuses the existing httpx streaming
    downloader.
  - User-supplied loose `SIN.{shp,dbf,prj,shx}` files re-packaged into
    a single `data/raw/regione_puglia_sin/sin_puglia.zip` matching what
    `acquire` would produce, with a proper provenance sidecar
    (publisher, license, URL all correct).
  - `normalize_sin_manfredonia` now reads `zip://…!sin/SIN.shp`,
    filters to `SITO == "MANFREDONIA"` (5 polygons), `source_id` is
    `regione_puglia_sin` to match the acquisition spec.
  - End-to-end run produces 4 deterministic polygons in
    `data/processed/sin_manfredonia.geojson` after clip to near-coast
    AOI (1 marine sub-polygon falls outside the band).
  - SPECIFICATIONS.md §4 row 5 and §18 OPEN-SIN-1 both updated to
    cite the real source. OSM `industrial_areas` retained as a
    separate context layer.
  - **142 tests passing, 97.88 % coverage**, ruff clean.
- 2026-05-25 — Phase 4b: 9 more vector normalizers (12 total).
  - `processing/normalize.py` gains a small `_normalize_osm_layer`
    helper that DRYs the per-layer OSM normalizers to ~5 lines each.
  - 8 new OSM normalizers: `roads`, `cycle_paths`, `cycle_routes`
    (graceful empty on missing raw), `harbours`, `beaches`,
    `wetlands`, `industrial_areas`, `archeological_areas`.
  - `normalize_natura2000`: reads the MASE Natura 2000 national zip,
    finds the inner shapefile, reprojects to EPSG:4326, pre-filters to
    sites intersecting the AOI bbox (cheap geometry test vs the
    full 2,649-site bundle), then conforms to schema with
    `denominazi` → `name_it` and `site_code` → `id`.
  - Real `mfd-map process vectors-all` produces 12 deterministic
    GeoJSONs under `data/processed/`. Notable counts after AOI clip:
    archeological_areas=5 (Grotta Scaloria + Siponto + Parco
    archeologico + Coppa Nevigata), industrial_areas=5 (incl. *Zona
    Industriale di Manfredonia-Monte Sant'Angelo*, the v1 SIN
    proxy), wetlands=23 (incl. *Lago Salso* x2 + *Lago Salso - Prati
    allagati*), natura2000=5 (incl. *Zone umide della Capitanata*),
    roads=2,047. Two consecutive runs produce identical SHAs.
  - **138 tests passing, 97.78 % coverage**, ruff clean.
- 2026-05-25 — Phase 4a: processing scaffolding + 3 vector normalizers.
  - `src/manfredonia_map/processing/{__init__, base, normalize, cli}.py`.
  - Generic vector pipeline: *normalize → to_storage_crs → clip_to_aoi
    → make_valid → write*. CLI: `mfd-map process vector <layer_id>` +
    `mfd-map process vectors-all [--skip ...]`. Pixi tasks
    `process-vector` / `process-vectors-all`.
  - **Byte-deterministic GeoJSON writer** — coordinates rounded to 7
    decimal places, `sort_keys=True`, atomic `mkstemp`+rename; two
    consecutive runs produce identical SHAs (matches the AOI writer
    pattern).
  - Three normalizers wired end-to-end against real raw data:
    - `coastline` (OSM `coastline.geojson`) → **3 LineStrings** after
      AOI clip.
    - `admin_boundaries` (ISTAT zipped shapefile, filter to
      `PRO_COM_T in {071029, 071033}`) → **2 Polygons** (Manfredonia
      + Monte Sant'Angelo) correctly clipped to the near-coast AOI.
    - `hydrography_surface` (ISPRA WFS GeoJSON) → **14 LineStrings**
      including the **CERVARO** torrent (feeds Lago Salso).
  - **Caught a real bug**: `conform_to_schema` used to end with
    `set_crs(STORAGE_CRS, allow_override=True)` which *relabelled* the
    CRS without reprojecting — silently corrupting UTM-coordinate
    sources (ISTAT `_WGS84.shp` files are actually EPSG:32632 despite
    the suffix). Fixed; regression test added.
  - **129 tests passing, 98.12 % coverage**, ruff clean.
- 2026-05-25 — Phase 3i: ISPRA surface hydrography + OSM cycle_routes
  (SPECIFICATIONS.md **v0.8**).
  - `src/manfredonia_map/acquisition/ispra.py`: `IspraHydrographySpec`
    builds WFS 2.0.0 GetFeature URLs against
    `sdi.isprambiente.it/geoserver/hy/wfs` with our AOI bbox and
    `application/json` output. 4 layers covered
    (`reticolo_idrografico`, `bacini_principali`, `bacini_secondari`,
    `autorita_bacino`).
  - CLI: `mfd-map acquire ispra hydrography <layer>` and
    `mfd-map acquire ispra hydrography-all [--skip ...]`. Pixi task
    `acquire-ispra-hydrography-all`.
  - Real downloads: total 322 KB across 4 GeoJSONs. CC-BY-4.0. The
    `reticolo_idrografico` AOI clip includes the **Cervaro** (feeds
    Lago Salso) and **Carapelle** torrents.
  - **OSM gains `cycle_routes`** (`route=bicycle` relations) — long-
    distance signed routes that complement `cycle_paths`. The default
    osmnx fetcher now catches `InsufficientResponseError` and returns
    an empty GeoDataFrame so "no matching features" is a normal,
    loggable outcome (used by the new `cycle_routes` and any future
    AOI-sparse layer).
  - **Ciclovia Adriatica blocked**: zero `route=bicycle` relations
    intersect our AOI (Ciclovia Adriatica not tagged through
    Manfredonia in OSM); MIT Open Data publishes only a route-name
    CSV; Bicitalia gates GPX behind a routing UI. Documented as
    OPEN-CICLOVIA-1.
  - **Underground hydrography**: ISPRA CII500K (Carta Idrogeologica
    1:500.000, 2025) is on `portalesgi.isprambiente.it`, not the `hy`
    workspace. Documented as OPEN-CII500K-1; v1 ships with surface
    hydrography only.
  - **93 tests passing, 98.68 % coverage**, ruff clean.
- 2026-05-24 — Phase 3h: MiC Vincoli in Rete — manual-ingest CLI
  (SPECIFICATIONS.md **v0.7**, OPEN-VIR-1 recorded).
  - Authoritative VIR archaeological vincoli are not exposed via any
    public WFS / WMS. Internal WFS is institution-gated; the public
    portal only allows per-site KML / CSV / PDF export through manual
    UI navigation. Same gap on GNA and SITAP. Documented as
    OPEN-VIR-1; the OSM `historic=archaeological_site` proxy
    (Grotta Scaloria + Siponto + Parco archeologico + Coppa Nevigata)
    remains the v1 default.
  - `src/manfredonia_map/acquisition/vir.py`: `VirManualExportSpec` +
    `stage_manual_export()` — validates that input looks like KML,
    copies to `data/raw/mic_vincoli_in_rete/` with a deterministic
    filename derived from a kebab-case label, raises clear errors on
    missing / empty / non-KML input.
  - CLI: `mfd-map acquire vir ingest --kml PATH --label LABEL`
    [`--out-dir`]. Pixi task `acquire-vir-ingest`. Writes the standard
    provenance sidecar with `access_method` set to
    "manual KML export from VIR portal UI" so the catalog stays
    honest about how the data was obtained.
  - **84 tests passing, 98.53 % coverage**, ruff clean.
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
