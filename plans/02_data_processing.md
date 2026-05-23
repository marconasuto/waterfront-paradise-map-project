# Subplan — Data processing

> Owns `src/manfredonia_map/processing/`. Turns `data/raw/` into
> `data/processed/`. Reads `config/layers.yaml` and `config/aoi.geojson`.

## Pipeline stages (per layer)

1. **Read** the raw file with the right driver:
   - Vector → `geopandas.read_file(..., engine="pyogrio")`.
   - Raster → `rioxarray.open_rasterio(...)` returning `xarray.DataArray`,
     chunked via Dask.
   - NetCDF (EMODnet bathymetry) → `xarray.open_dataset(..., engine="netcdf4")`.
2. **Validate** schema: required columns/bands, dtype, value ranges,
   geometry validity. Failure → halt with a precise message; never silently
   skip.
3. **Reproject** to the working CRS (EPSG:32633) for analysis, then to
   EPSG:4326 for storage. Rasters use `.rio.reproject(..., resampling=...)`.
4. **Clip** to `config/aoi.geojson` (`gpd.clip` for vectors,
   `.rio.clip(...)` for rasters).
5. **Normalize**:
   - Vectors: enforce schema (`id`, `name_it`, `category`, `year_data`,
     `source_id`, plus layer-specific fields).
   - Rasters: write **Zarr** to `data/interim/<layer>.zarr` for analysis
     (chunked, lazy). Final **published** raster is built as an 8-bit
     colormapped COG with overviews — Mapbox does not accept 16-bit
     GeoTIFF uploads.
6. **Topology fix** (vectors): `make_valid`, remove empty/degenerate geoms.
7. **Write**:
   - Vectors → `data/processed/manfredonia.gpkg` table + per-layer GeoJSON.
   - Rasters → analytic Zarr in `data/interim/`; 8-bit colormapped COG
     in `data/processed/<layer>_8bit.tif`. Raw 16-bit COG kept in
     `data/interim/<layer>_raw.tif` for future re-processing.
8. **Provenance**: update `data/catalog.yaml` (input hash, processing
   version, output hash, AOI hash).

## Module layout

```
src/manfredonia_map/processing/
    __init__.py
    aoi.py          ← build_aoi(): buffer + coastal clip, generator for §3
    base.py         ← ProcessingStep protocol; deterministic ordering
    schema.py       ← target schemas (pydantic models per layer)
    reproject.py
    clip.py
    normalize.py    ← per-layer normalizers (one fn per layer)
    topology.py
    raster.py       ← xarray/rioxarray open, .rio.reproject, .rio.clip;
                       Zarr write; 8-bit colormap → COG output
    hillshade.py    ← DTM → hillshade + slope via xarray + numpy
    pipeline.py     ← orchestrator (CLI: mfd-map process all|<layer>)
```

## Tasks

- [ ] Implement `scripts/build_aoi.py` (Phase 2). Produces **both**:
  - `config/aoi_buffered.geojson` — source polygon + 1 km buffer in both
    directions, EPSG:32633 metric buffer, output in EPSG:4326.
  - `config/aoi_near_coast.geojson` — `aoi_buffered ∩ (coastal_band ∪
    mandatory_features)` where the coastal band is the coastline buffered by
    2 km both sides and the mandatory features are the SIN polygon, every
    wetland (Natura 2000 + OSM) intersecting `aoi_buffered`, Lago Salso,
    Oasi Laguna del Re, and a 500 m buffer around the Grotta Scaloria
    point.
  - `config/aoi.geojson` — alias of `aoi_near_coast` by default
    (OPEN-AOI-3; flippable in `config/build.yaml`).
  Build is **deterministic** — same input data, identical bytes out.
  Sanity checks (Lago Salso / Oasi / Acqua di Cristo / SIN / Grotta
  Scaloria centroids inside `aoi_near_coast`) hard-fail the script.
- [ ] Define `schema.py` target models for each layer in spec §4.
- [ ] Per-layer normalizers (one Python function each, fully unit-tested).
- [ ] DTM → hillshade and slope COGs derived in `raster.py` for cartographic
      use (raw DTM also published).
- [ ] Determinism check: a `pytest` test that processes the fixture corpus
      twice and asserts identical output hashes.
- [ ] Performance budget: full processing run < 10 minutes on a laptop for
      v1 scale; document if exceeded.

## Acceptance

- [ ] `mfd-map process all` produces `data/processed/manfredonia.gpkg`
      with one table per layer, plus per-layer GeoJSON, plus DTM and
      bathymetry COGs.
- [ ] `data/catalog.yaml` round-trips through the catalog reader.
- [ ] ≥ 95 % coverage on `processing/`, no test marked flaky.
