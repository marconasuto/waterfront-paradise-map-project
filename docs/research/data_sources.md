# Research — Data sources

> Findings from web research, 2026-05-23. Every URL was returned by a search
> against the publisher's domain. Mark `(unverified)` if a URL was not seen
> in a primary source. Conclusions fold back into `SPECIFICATIONS.md` §4 and
> `plans/01_data_acquisition.md`.

## Source-preference order (recap)

1. Italian state (ISPRA, MASE, MiC, ISTAT, INGV, IIM)
2. Regione Puglia (SIT Puglia, ARPA Puglia)
3. Provincia di Foggia, Comune di Manfredonia
4. EU (EMODnet, Copernicus, EEA, INSPIRE)
5. OSM as secondary / validation

## Big-picture findings (read first)

- **CRS in Italian sources is mixed**: SIT Puglia ships WGS84-UTM33N
  (EPSG:32633), Natura 2000 MASE ships WGS84-UTM32 (EPSG:32632), PCN IGM has
  zone-32 and zone-33 variants, ISPRA INSPIRE datasets ship ETRS89 / LAEA or
  ETRS89 / UTM. **Lock our pipeline working CRS to EPSG:32633** (matches the
  regional authority for our AOI), reproject on ingest from whatever a given
  source publishes. Final storage CRS stays EPSG:4326 for Mapbox.
- **For underground hydrography**, the canonical source is ISPRA's new
  Carta Idrogeologica d'Italia 1:500.000 (CII500K, published 2025), with
  legacy 1:50.000 sheets per area. The 1:100.000 hydrogeologic series is
  only sheet-by-sheet (no national mosaic). Augment with Regione Puglia
  Piano di Tutela delle Acque and the Autorità di Bacino Distrettuale
  dell'Appennino Meridionale for aquifer detail.
- **For DTM**, TINITALY 1.1 (INGV) at 10 m is the best free national source,
  CC BY 4.0 — far better than the PCN 20 m DTM. Use TINITALY as primary;
  PCN only as a fallback for tiles TINITALY does not cover.
- **For bathymetry**, EMODnet Bathymetry DTM 2024 (≈115 m at this latitude,
  GeoTIFF/NetCDF) is the right free choice. IIM charts are paywalled and ENC
  format requires ECDIS — not usable in our pipeline. We will **cite IIM as
  the authoritative national reference** but ingest EMODnet.
- **For SIN Manfredonia**, the perimeter is published by MASE on the
  Bonifiche Siti Contaminati portal; ISPRA also redistributes it via the
  Geoportale and ReNDiS-web (with shapefile + WFS).
- **For Vincoli in Rete (MiC)**, the portal exposes a WFS layer that SITAP
  itself consumes. For Grotta Scaloria specifically the entry exists in
  Vincoli in Rete (archaeological constraint).
- **There is an official Mapbox MCP server** with location-intelligence
  tools (geocoding, search, directions, matrix, static maps, isochrone) —
  this materially changes the post-v1 MCP plan; see `mcp_mapbox.md`.

---

## Per-layer findings

### 1. Hydrography — surface

- **Canonical (national):** ISPRA — *Reticolo Idrografico Nazionale 1:250.000*.
  - Landing: <https://geodati.gov.it/resource/id/ispra_rm:01Idro250N_DT>
  - INSPIRE: <https://inspire-geoportal.ec.europa.eu/srv/api/records/ispra_rm:001Idrografia250N_SVD>
  - WFS: see the dataset's download service ("SERVIZIO DI SCARICAMENTO WFS",
    [Geoportale MASE](https://gn.mase.gov.it/portale/en/wfs)).
  - Format: shapefile + WFS; CC BY 4.0; CRS in dataset metadata
    (typically EPSG:4326 / WGS84 for INSPIRE).
- **Regional:** SIT Puglia — *Idrografia / reticolo idrografico regionale*.
  - Landing: <https://pugliacon.regione.puglia.it/web/sit-puglia-sit/download>
  - Format: shapefile, WGS84-UTM33N (EPSG:32633); license per SIT terms.
- **OSM (validation / detail):** Overpass query for `waterway=*` in AOI bbox.

### 2. Hydrography — underground (user explicit ask)

- **Canonical (national):** ISPRA — *Carta Idrogeologica d'Italia 1:500.000
  (CII500K)* (released 2025).
  - Landing: <https://www.isprambiente.gov.it/it/attivita/suolo-e-territorio/idrogeologia/carta-idrogeologica-ditalia-alla-scala-1-500.000>
  - Service portal: <https://portalesgi.isprambiente.it/> (Geomapviewer +
    OGC services; raster + vector products).
- **Detail (where available):** ISPRA — *Carta Idrogeologica 1:50.000* per
  sheet (legacy CARG-IDRO).
  - Catalogue: <https://www.isprambiente.gov.it/en/publications/technical-periodicals/booklets-series-iii-of-sgi/hydrogeological-map-of-italy-at-1-50.000-scale>
- **Regional:** Regione Puglia — *Piano di Tutela delle Acque (PTA) Puglia*
  layers (corpi idrici sotterranei, vulnerabilità acquiferi); access via
  SIT Puglia download portal.
- **Distrettuale:** Autorità di Bacino Distrettuale dell'Appennino
  Meridionale — *Piano di Gestione delle Acque (PGA)*.

### 3. Topography (DTM)

- **Canonical (national):** INGV — *TINITALY 1.1* (10 m, raster).
  - Landing: <https://tinitaly.pi.ingv.it/>
  - Download tiles: <https://tinitaly.pi.ingv.it/Download_Area1_1.html>
  - WMS GetCapabilities:
    <https://tinitaly.pi.ingv.it/TINItaly/wms?service=WMS&request=getCapabilities>
  - License: **CC BY 4.0** (cite Tarquini et al., INGV).
  - CRS: EPSG:32633 in source (UTM33N).
- **Fallback (national, lower resolution):** Geoportale Nazionale (PCN) —
  *DTM 20 m IGM-derived*.
  - Viewer: <http://www.pcn.minambiente.it/viewer/>
- **EU-wide (reference):** Copernicus EU-DEM v1.1 (25 m, EEA).

### 4. Bathymetry / seabed

- **Canonical (free):** EMODnet — *Digital Bathymetry (DTM 2024)*.
  - Landing: <https://emodnet.ec.europa.eu/en/emodnet-bathymetry-dtm-2024-release>
  - Map Viewer (per-tile download): <https://emodnet.ec.europa.eu/geoviewer/>
  - WMTS: <https://tiles.emodnet-bathymetry.eu/>
  - Adriatic / Central Mediterranean tile (covers Manfredonia): tile **F4
    or F5** of the 2024 grid — confirm at download time.
  - Resolution: 1/16′ × 1/16′ (≈ 115 m at lat 41°N).
  - Formats: ESRI ASCII, XYZ, EMODnet CSV, NetCDF, **GeoTIFF**, SD.
  - License: CC BY 4.0 (EMODnet terms).
- **National (paywalled, cite only):** IIM — *Carte nautiche / ENC*.
  - Landing: <https://www.istitutoidrografico.it/it/index.html>
  - Catalog (free PDF): <https://www.marina.difesa.it/noi-siamo-la-marina/pilastro-logistico/scientifici/idrografico/Documents/catalogo_2020/Catalogo_Generale_2020.pdf>
  - ENC requires ECDIS; not usable in our pipeline. Cite as authoritative.
- **Reference:** GEBCO 2024 — global, coarser than EMODnet but fully open.

### 5. SIN Manfredonia (ex-Enichem)

- **Canonical (national, MASE):**
  - Landing: <https://bonifichesiticontaminati.mite.gov.it/sin-5/>
  - Initial decree: 10/01/2000 (G.U. 47 del 26/02/2000); perimeter
    modification: 02/12/2024 (G.U. 294 del 16/12/2024).
- **Cartography (ISPRA / MASE):** ReNDiS-web — shapefile + WFS/WMS.
  - <http://www.rendis.isprambiente.it/rendisweb/vistepub.jsp>
- **Geoportale ISPRA:** <http://geoportale.isprambiente.it/>
- **Regional (ARPA Puglia):** Anagrafe siti contaminati Puglia + indicators.
  - <https://www.arpa.puglia.it/pagina3239_siti-potenzialmente-contaminati.html>
  - <https://www.arpa.puglia.it/pagina3240_siti-di-interesse-nazionale-da-bonificare.html>
- **License:** ISPRA CC BY 4.0 IT (cite ISPRA / MASE).

### 6. Wetlands / Zone Umide

- **Canonical (national):** MASE — *Rete Natura 2000 (SIC/ZSC e ZPS)*,
  Italian transmission to the European Commission.
  - Landing: <https://www.mase.gov.it/portale/sic-zsc-e-zps-in-italia>
  - Cartographic page: <https://www.mase.gov.it/portale/cartografie-rete-natura-2000-e-aree-protette-progetto-natura->
  - Download bundle (Dec 2025 transmission):
    `https://download.mase.gov.it/Natura2000/` (shapefiles + xlsx).
  - **CRS:** UTM zone 32, WGS84 (EPSG:32632) — reproject on ingest to 32633.
  - License: non-commercial, cite the source.
- **Banca dati Natura 2000 (ISPRA):**
  <https://www.nnb.isprambiente.it/it/banca-dati-rete-natura-2000>
- **Specific Manfredonia sites (already identified):**
  - **Lago Salso** — SIC `IT9110005`, ZPS `IT9110038` (filter on these codes
    when extracting from the national dump).
  - Oasi Laguna del Re: check SIC/ZPS code list inside the dump for AOI.
- **Park-level (managed area):** Parco Nazionale del Gargano — perimeter
  available from MASE *Aree Protette EUAP* dataset.
- **RAMSAR:** wider RAMSAR layer redistributed by MASE within Aree Protette.

### 7. Road network

- **Canonical (open):** OpenStreetMap via Overpass — primary because it is
  the most complete and includes pedestrian / cycling tagging.
  - Endpoint (any of):
    <https://overpass-api.de/api/interpreter>,
    <https://overpass.kumi.systems/api/interpreter>.
  - License: ODbL — must be cited and any derivative shared under ODbL.
  - Overpass QL template (AOI bbox 41.49,15.80,41.69,16.05):
    ```overpassql
    [out:json][timeout:120];
    (
      way["highway"](41.49,15.80,41.69,16.05);
    );
    out body;
    >;
    out skel qt;
    ```
- **National (validation):** ANAS — *grafo stradale ANAS* (concession network
  only). Useful as ground truth on classified roads.
- **Regional:** Strade Provincia Foggia / Comune di Manfredonia (graf
  stradale comunale) via SIT Puglia.
- **Walkable paths**: OSM tags `highway=footway|path|pedestrian|track|steps`
  and `foot=yes|designated`. CAI sentieri are partially in OSM with
  `route=hiking` relations; for the Gargano area there is good CAI coverage.

### 8. Cycle paths (ciclovie)

- **Canonical (national):** Ministero delle Infrastrutture e dei Trasporti —
  *Sistema Nazionale Ciclovie Turistiche*.
  - Open data: <https://dati.mit.gov.it/catalog/dataset/ciclovie-turistiche-nazionali>
  - **Ciclovia Adriatica** is part of this system and traverses the Gargano
    (Venice → Gargano, ~700 km).
- **Crowdsourced:** Bicitalia / FIAB at <https://www.bicitalia.org/>.
- **OSM:** Overpass `highway=cycleway` ways and `route=bicycle` relations
  for the same AOI bbox. Best level of detail for local paths.

### 9. Harbours

- **Canonical (authority):** Autorità di Sistema Portuale del Mare Adriatico
  Meridionale (AdSP MAM).
  - Porto di Manfredonia: <https://www.adspmam.it/i-porti/porto-di-manfredonia/>
  - Cartografia (port plan PDFs): <https://www.adspmam.it/i-porti/porto-di-manfredonia/cartografia/>
  - Note: PDF plans only; we will digitize the perimeter once or use OSM.
- **MIT open data — Autorità portuali:**
  <https://dati.mit.gov.it/catalog/organization/about/autorita-portuali>
- **OSM:** `landuse=industrial`+`industrial=port`, `harbour=yes`,
  `waterway=dock`, `man_made=pier`, `seamark:*` tagging.

### 10. Industrial areas

- **Canonical (national):** MASE / ISPRA Bonifiche & Suoli (overlaps with
  SIN dataset for ex-Enichem area).
- **Regional:** Consorzio per l'Area di Sviluppo Industriale (ASI) di
  Foggia — agglomerati industriali (perimeters available as PDF + on regional
  PRG; digitize if no shapefile is published).
- **Local:** Comune di Manfredonia — PRG (zone D = industriale) via SIT
  Puglia comunale.
- **Validation:** OSM `landuse=industrial`.

### 11. Archeological areas

- **Canonical (national):** Ministero della Cultura — *Vincoli in Rete (VIR)*.
  - Landing: <https://cultura.gov.it/vincoli-in-rete-ricerca-sia-di-tipo-alfanumerico-che-cartografico>
  - Portal: <https://vincoliinrete.beniculturali.it/vir/vir/vir.html>
  - WFS is available (consumed internally by SITAP); export formats from
    the public portal: PDF, CSV, XML, KML.
- **National geoportal for archaeology:** MiC — *GNA (Geoportale Nazionale
  per l'Archeologia)*: <https://gna.cultura.gov.it/index.html>
- **SITAP:** <https://sitap.cultura.gov.it/APAR_guida%20vers%202_0_0.pdf>
  (Sistema Informativo Territoriale Ambiente e Paesaggio).
- **Specific items in AOI:**
  - **Grotta Scaloria** — Contrada Scaloria, periferia nord di Manfredonia,
    near the Palazzetto dello Sport, ≈ 45 m a.s.l.
    Refs: <https://www.preistoriainitalia.it/scheda/grotta-scaloria-manfredonia-fg/>;
    UNESCO candidacy 2026 (<https://cultura.gov.it/evento/la-memoria-dellacqua-a-manfredonia-grotta-scaloria-racconta>).
  - **Siponto** (basilica + parco archeologico) — separate point/perimeter,
    also in VIR.
  - Soprintendenza Foggia (SABAP-FG) for local provenance / vincoli.

### 12. Beaches

- **Canonical (open):** OSM `natural=beach`.
- **Regional (regulated):** Regione Puglia — *Balneazione* (qualità acque)
  via ARPA Puglia and SIT Puglia; bathing-area perimeters published yearly.
- **National reporting:** ISPRA — Portale del Mare (qualità).
- **Specific items in AOI:**
  - **Acqua di Cristo** (Manfredonia nord) — approx **41.6307, 15.9238**,
    ≈ 2.2 km north of the town centre, rocky coast with karst springs.
    Refs: <https://www.tripadvisor.com/Attraction_Review-g194808-d13296704-Reviews-Sorgente_Acqua_di_Cristo-Manfredonia_Province_of_Foggia_Puglia.html>,
    <https://www.visitmanfredonia.com/spiagge/>.
    Add as a `highlight` in `config/highlights.yaml`.

### 13. Coastline

- **Canonical (national):** ISTAT *confini comunali* + EMODnet *Human
  Activities* coastline; OSM `natural=coastline` for daily-updated detail.
- For our AOI we will use ISTAT comunale boundary (sea-side only) clipped
  against OSM coastline to get a consistent line.

### 14. Administrative boundaries

- **Canonical (national):** ISTAT — *Confini delle unità amministrative a
  fini statistici al 1 gennaio 2024* (and the rolling annual release).
  - Landing: <https://www.istat.it/it/archivio/222527>
  - Includes regions, provinces, comuni — shapefile + WGS84, generalized
    and detailed versions, released annually.
  - License: CC BY 3.0 (per ISTAT terms) — verify on the dataset page.
- **Companion mirror:** OnData — <https://www.confini-amministrativi.it/>
  (re-distributes ISTAT in additional formats; useful for older years).

---

## Other geoportals worth knowing

- **RNDT (national catalog):**
  - Geoportal: <https://geodati.gov.it/geoportale/13-sito>
  - CSW endpoint: `http://geodati.gov.it/RNDT/csw`
  - REST find: `https://geodati.gov.it/RNDT/rest/find/document?`
- **PCN (Geoportale Nazionale, MASE):**
  - Viewer: <http://www.pcn.minambiente.it/viewer/>
  - WFS index (Geoportale MASE): <https://gn.mase.gov.it/portale/en/wfs>
- **SIT Puglia (Regione Puglia):**
  - Cartography landing: <https://pugliacon.regione.puglia.it/web/sit-puglia-sit/cartografia-template-web-gis>
  - Download portal: <https://pugliacon.regione.puglia.it/web/sit-puglia-sit/download>
  - WMS: <https://pugliacon.regione.puglia.it/web/sit-puglia-sit/web-map-service3>
  - Note: regional downloads are in EPSG:32633 (WGS84-UTM33N).

---

## CRS recommendation (resolves OPEN-CRS-1)

Mixed evidence:
- **EPSG:32633 (WGS84/UTM33N)** is what SIT Puglia ships its downloads in
  and what TINITALY uses natively.
- **EPSG:32632 (WGS84/UTM32N)** is what MASE Natura 2000 ships for nationwide
  consistency.
- **EPSG:25833 (ETRS89/UTM33N)** is what fully-INSPIRE-compliant releases use,
  but that is a minority of our actual sources today.

**Decision:** working analysis CRS = **EPSG:32633** (WGS84 / UTM 33N).
Rationale: matches the regional authority (SIT Puglia) and TINITALY (highest-
priority raster source). We reproject every other source on ingest. Storage
CRS for vectors remains EPSG:4326 (Mapbox-friendly).

Fold this back into `SPECIFICATIONS.md` §7 and close OPEN-CRS-1.

---

## Open questions to bounce back to the user (NEW or reinforced)

- **OPEN-AOI-1** (coastal-part definition): still open; proposed default is
  *buffered polygon ∩ coastal band of width W around the OSM/ISTAT
  coastline*. W to be set after we see the bathymetry resolution and the
  Lago Salso / Acqua di Cristo positions.
- **OPEN-AOI-2** (buffer direction): still open; recommend buffering equally
  both seaward and landward.
- **OPEN-MEDIA-1** (image / video hosting): still open.
- New **OPEN-LICENSE-1**: MASE Natura 2000 license is "non-commercial".
  If the project becomes a museum/urban-planning kiosk (use cases in spec
  §15), confirm this is still permitted — likely yes since non-commercial,
  but explicit citation is required.
- New **OPEN-OSM-1**: confirm we are happy to redistribute OSM-derived
  layers under **ODbL** (this binds the storymap to ODbL attribution).
