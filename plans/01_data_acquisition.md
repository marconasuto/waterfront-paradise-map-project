# Subplan — Data acquisition

> Derives from `SPECIFICATIONS.md` §4 and §5. Owns the `acquisition/` module.

## Research (Phase 1 deliverable)

For every layer listed in spec §4, fill `docs/research/data_sources.md` with:

- **Dataset name + publisher**
- **Canonical URL** (landing page) and **download endpoint** (WFS/WMS/WCS/HTTP)
- **Year of data** (and refresh cadence)
- **License** (with SPDX-ish string)
- **CRS** as published, target CRS in our pipeline
- **Format** (GeoPackage, Shapefile, GeoJSON, GeoTIFF, NetCDF, …)
- **Access method**: anonymous HTTP, WFS, Overpass query, account-gated download
- **Identifier for catalog** (the `id` we will use in `config/layers.yaml`)

### Candidate source map (to confirm, fill, or replace)

- [ ] **Hydrography (surface)** — RNDT, SIT Puglia Idrografia, OSM `waterway=*`.
- [ ] **Hydrography (underground)** — ISPRA Carta Idrogeologica d'Italia,
      Autorità di Bacino Distrettuale dell'Appennino Meridionale, Regione
      Puglia Piano di Tutela delle Acque.
- [ ] **DTM** — TINITALY (INGV, Tarquini et al.), PCN MATTM 1m, Copernicus EU-DEM.
- [ ] **Bathymetry** — EMODnet Bathymetry, GEBCO, IIM nautical charts.
- [ ] **SIN Manfredonia** — ISPRA registry of SIN sites, MASE perimetro.
- [ ] **Wetlands / Zone Umide** — RAMSAR sites, Natura 2000 (SIC/ZPS/ZSC),
      Regione Puglia aree protette (Parco Naturale Regionale di Lago Salso),
      Oasi WWF.
- [ ] **Roads** — OSM via Overpass; Strade Provincia Foggia, ANAS, Regione
      Puglia ciclovie e mobilità dolce.
- [ ] **Walkable paths** — OSM (`highway=footway|path|pedestrian|track`,
      `foot=yes`), CAI sentieri (if available for Gargano area).
- [ ] **Cycle paths** — OSM (`highway=cycleway`, `route=bicycle` relations);
      Ciclovia Adriatica (Sistema Nazionale Ciclovie Turistiche, MIT).
- [ ] **Harbours** — OSM `harbour=yes`/`landuse=harbour`; Autorità di Sistema
      Portuale del Mare Adriatico Meridionale; Capitanerie di Porto.
- [ ] **Industrial areas** — ASI Foggia (Consorzio per l'Area di Sviluppo
      Industriale), Comune di Manfredonia PRG; ARPA Puglia inventario.
- [ ] **Archeological** — MiC Vincoli in Rete; SITAP; ICCD; Soprintendenza
      Archeologia Belle Arti Paesaggio Foggia (Grotta Scaloria, Siponto).
- [ ] **Beaches** — OSM (`natural=beach`); Regione Puglia balneazione;
      ISPRA Portale del Mare.
- [ ] **Coastline** — ISTAT confini; OSM coastline; EMODnet Human Activities.
- [ ] **Admin boundaries** — ISTAT confini amministrativi (Comuni 2024+).

## Module design (implementation, Phase 3)

```
src/manfredonia_map/acquisition/
    __init__.py
    base.py          ← abstract `Downloader` protocol (fetch, validate, record)
    http.py          ← generic HTTPS file downloader with retries + hash check
    wfs.py           ← OGC WFS client (GetFeature, bbox by AOI, paginated)
    wms.py           ← optional WMS (rasters where WCS unavailable)
    wcs.py           ← OGC WCS for raster coverages
    overpass.py      ← OSM Overpass queries, deterministic, tagged-by-AOI
    sources/         ← one tiny module per concrete source binding the above
        ispra_sin.py
        ispra_hydrogeology.py
        sit_puglia_*.py
        rndt_*.py
        emodnet_bathymetry.py
        gebco_bathymetry.py
        tinitaly_dtm.py
        mic_vincoli_in_rete.py
        istat_admin.py
        osm_overpass_aoi.py
```

Every concrete source module:
- Reads its config block from `config/layers.yaml` (URL, params).
- Writes the raw response under `data/raw/<source_id>/<accessed-on>/...`.
- Records a `ProvenanceRecord` in the catalog (URL, sha256, license, year,
  accessed-on UTC ISO 8601, source software version).
- Has its own unit test using `respx` to mock HTTP — no network in unit tests.

## Acceptance for Phase 3

- [ ] All sources marked `[ ]` above either downloaded or explicitly marked
      "skipped — see DECISION.md" with reason.
- [ ] `mfd-map acquire all` is idempotent: a second run touches nothing if
      catalog hashes match upstream.
- [ ] Catalog passes `manfredonia_map.catalog.validate()` (json-schema).
- [ ] Unit tests for every downloader (mocked HTTP) at ≥95 % coverage.
- [ ] One integration test per source family, gated by `@pytest.mark.network`.
