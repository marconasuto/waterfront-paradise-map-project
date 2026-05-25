from __future__ import annotations

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from manfredonia_map.processing import base, normalize

# --- coastline --------------------------------------------------------

def _write_osm_coastline(path: Path) -> None:
    # osmnx 2.x writes the OSM id as a column named ``id`` (not ``osmid``).
    gdf = gpd.GeoDataFrame(
        {
            "id": ["w1", "w2"],
            "name": [None, "Spiaggia di X"],
            "natural": ["coastline", "coastline"],
        },
        geometry=[
            LineString([(15.9, 41.6), (16.0, 41.65)]),
            LineString([(16.0, 41.65), (16.05, 41.69)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(path, driver="GeoJSON")


def test_normalize_coastline_conforms_to_schema(tmp_path: Path):
    raw = tmp_path / "coastline.geojson"
    _write_osm_coastline(raw)
    out = normalize.normalize_coastline(raw_path=raw)
    assert list(base.SCHEMA_COLUMNS) == [
        c for c in out.columns if c in base.SCHEMA_COLUMNS
    ]
    assert out["layer_id"].iloc[0] == "coastline"
    assert out["source_id"].iloc[0] == "osm_coastline"
    assert out["category"].iloc[0] == "coastline"
    assert out["id"].tolist() == ["w1", "w2"]
    assert out["name_it"].tolist()[1] == "Spiaggia di X"


def test_normalize_coastline_synthesises_id_when_missing(tmp_path: Path):
    raw = tmp_path / "coastline.geojson"
    gpd.GeoDataFrame(
        {"natural": ["coastline"]},
        geometry=[LineString([(15.9, 41.6), (16.0, 41.65)])],
        crs="EPSG:4326",
    ).to_file(raw, driver="GeoJSON")
    out = normalize.normalize_coastline(raw_path=raw)
    assert out["id"].tolist() == ["coastline_0"]


# --- admin_boundaries (zipped shapefile) ------------------------------

def _write_istat_zip(zip_path: Path) -> None:
    """Create a minimal zip mimicking the ISTAT bundle layout."""
    inner_dir = zip_path.parent / "istat_src" / "Limiti01012024_g" / "Com01012024_g"
    inner_dir.mkdir(parents=True)
    shp = inner_dir / "Com01012024_g_WGS84.shp"
    gpd.GeoDataFrame(
        {
            "PRO_COM_T": ["071029", "071033", "071001"],
            "COMUNE": ["Manfredonia", "Monte Sant'Angelo", "Foggia"],
            "PROVINCIA": ["Foggia", "Foggia", "Foggia"],
            "REGIONE": ["Puglia", "Puglia", "Puglia"],
        },
        geometry=[
            Polygon([(15.85, 41.55), (15.95, 41.55), (15.95, 41.65), (15.85, 41.65)]),
            Polygon([(15.95, 41.65), (16.05, 41.65), (16.05, 41.75), (15.95, 41.75)]),
            Polygon([(15.50, 41.40), (15.60, 41.40), (15.60, 41.50), (15.50, 41.50)]),
        ],
        crs="EPSG:32632",
    ).to_file(shp, driver="ESRI Shapefile")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in inner_dir.glob("Com01012024_g_WGS84.*"):
            zf.write(f, arcname=f"Limiti01012024_g/Com01012024_g/{f.name}")


def test_normalize_admin_boundaries_filters_to_target_comuni(tmp_path: Path):
    z = tmp_path / "istat.zip"
    _write_istat_zip(z)
    out = normalize.normalize_admin_boundaries(raw_zip=z)
    assert sorted(out["id"].tolist()) == ["071029", "071033"]
    assert set(out["name_it"]) == {"Manfredonia", "Monte Sant'Angelo"}
    assert (out["layer_id"] == "admin_boundaries").all()
    assert (out["source_id"] == "istat_limiti_2024_generalized").all()
    assert (out["year_data"] == 2024).all()
    assert "PROVINCIA" in out.columns


def test_normalize_admin_boundaries_target_comuni_overridable(tmp_path: Path):
    z = tmp_path / "istat.zip"
    _write_istat_zip(z)
    out = normalize.normalize_admin_boundaries(raw_zip=z, target_comuni=("071029",))
    assert out["id"].tolist() == ["071029"]


# --- hydrography_surface (ISPRA WFS GeoJSON) --------------------------

def _write_ispra_reticolo(path: Path) -> None:
    gpd.GeoDataFrame(
        {
            "id_tratta": [42644, 45014],
            "nome": ["CERVARO", "CARAPELLE"],
            "tipo": ["TORRENTE", "TORRENTE"],
            "ordine": [1, 1],
            "bacino_pri": ["CERVARO", "CARAPELLE"],
            "st_length_": [16872.0, 29881.0],
        },
        geometry=[
            LineString([(15.85, 41.55), (15.95, 41.60)]),
            LineString([(15.90, 41.40), (15.95, 41.50)]),
        ],
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")


def test_normalize_hydrography_surface_keeps_layer_fields(tmp_path: Path):
    raw = tmp_path / "hy.geojson"
    _write_ispra_reticolo(raw)
    out = normalize.normalize_hydrography_surface(raw_path=raw)
    assert sorted(out["id"].tolist()) == ["42644", "45014"]
    assert set(out["name_it"]) == {"CERVARO", "CARAPELLE"}
    assert (out["category"] == "water").all()
    assert (out["source_id"] == "ispra_hy_reticolo_idrografico").all()
    # The extra columns survive in the output.
    for col in ("tipo", "ordine", "bacino_pri", "st_length_"):
        assert col in out.columns


# --- registry --------------------------------------------------------

def test_normalizers_registry_contains_expected_layer_ids():
    expected = {
        "coastline", "admin_boundaries", "hydrography_surface",
        "roads", "cycle_paths", "cycle_routes",
        "harbours", "beaches", "wetlands",
        "industrial_areas", "archeological_areas",
        "natura2000", "sin_manfredonia",
    }
    assert expected <= set(normalize.NORMALIZERS)
    for lid, spec in normalize.NORMALIZERS.items():
        assert spec.layer_id == lid
        assert callable(spec.fn)


# --- OSM helper + per-OSM-layer normalizers ----------------------------

def _write_osm_geojson(path: Path, rows: dict, geometry: list) -> None:
    gpd.GeoDataFrame(rows, geometry=geometry, crs="EPSG:4326").to_file(
        path, driver="GeoJSON"
    )


def test_normalize_osm_layer_helper_handles_minimal_columns(tmp_path: Path):
    raw = tmp_path / "min.geojson"
    gpd.GeoDataFrame(
        {"natural": ["wetland"]},
        geometry=[Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)])],
        crs="EPSG:4326",
    ).to_file(raw, driver="GeoJSON")
    out = normalize._normalize_osm_layer(
        raw,
        layer_id="x",
        source_id="osm_x",
        year_data=2026,
        category="bucket",
    )
    assert out["layer_id"].iloc[0] == "x"
    assert out["source_id"].iloc[0] == "osm_x"
    assert out["category"].iloc[0] == "bucket"
    # No id/name → synthetic
    assert out["id"].iloc[0] == "x_0"
    assert out["name_it"].isna().all()


def test_normalize_roads_keeps_extras(tmp_path: Path):
    raw = tmp_path / "roads.geojson"
    _write_osm_geojson(
        raw,
        {"id": [1, 2], "name": ["SS89", None], "highway": ["primary", "residential"],
         "surface": ["asphalt", None], "maxspeed": [90, 50]},
        [LineString([(15.9, 41.6), (15.95, 41.65)]),
         LineString([(15.95, 41.65), (16.0, 41.7)])],
    )
    out = normalize.normalize_roads(raw_path=raw)
    assert out["id"].tolist() == ["1", "2"]
    assert out["name_it"].iloc[0] == "SS89"
    assert out["category"].iloc[0] == "road"
    for col in ("highway", "surface", "maxspeed"):
        assert col in out.columns


def test_normalize_cycle_routes_returns_empty_when_raw_missing(tmp_path: Path):
    # Ciclovia Adriatica is not tagged in our AOI; the file may not exist.
    out = normalize.normalize_cycle_routes(raw_path=tmp_path / "missing.geojson")
    assert out.empty
    assert out.crs is not None


def test_normalize_harbours_handles_mixed_geom_types(tmp_path: Path):
    raw = tmp_path / "harbours.geojson"
    _write_osm_geojson(
        raw,
        {"id": [1, 2], "name": ["Porto", "Pier"], "man_made": [None, "pier"],
         "harbour": ["yes", None], "mooring": [None, "private"], "material": ["concrete", "wood"]},
        [Polygon([(15.9, 41.6), (15.95, 41.6), (15.95, 41.65), (15.9, 41.65)]),
         LineString([(15.92, 41.62), (15.93, 41.63)])],
    )
    out = normalize.normalize_harbours(raw_path=raw)
    assert out["category"].iloc[0] == "harbour"
    assert set(out.geometry.geom_type) == {"Polygon", "LineString"}


def test_normalize_wetlands_keeps_wetland_subtype(tmp_path: Path):
    raw = tmp_path / "wet.geojson"
    _write_osm_geojson(
        raw,
        {"id": [1], "name": ["Lago Salso"], "natural": ["wetland"],
         "wetland": ["marsh"], "wikidata": ["Q123"]},
        [Polygon([(15.91, 41.60), (15.93, 41.60), (15.93, 41.62), (15.91, 41.62)])],
    )
    out = normalize.normalize_wetlands(raw_path=raw)
    assert out["name_it"].iloc[0] == "Lago Salso"
    assert out["wetland"].iloc[0] == "marsh"


def test_normalize_industrial_areas_passes_through_landuse(tmp_path: Path):
    raw = tmp_path / "ind.geojson"
    _write_osm_geojson(
        raw,
        {"id": [1], "name": ["Zona Industriale"], "landuse": ["industrial"]},
        [Polygon([(15.93, 41.58), (15.96, 41.58), (15.96, 41.60), (15.93, 41.60)])],
    )
    out = normalize.normalize_industrial_areas(raw_path=raw)
    assert out["layer_id"].iloc[0] == "industrial_areas"
    assert out["landuse"].iloc[0] == "industrial"


def test_normalize_archeological_areas_keeps_historic_extras(tmp_path: Path):
    raw = tmp_path / "arc.geojson"
    _write_osm_geojson(
        raw,
        {"id": [1, 2], "name": ["Grotta Scaloria", "Siponto"],
         "historic": ["archaeological_site", "archaeological_site"],
         "wikidata": ["Q1", "Q2"],
         "historic:civilization": ["neolithic", "roman"]},
        [Polygon([(15.90, 41.64), (15.92, 41.64), (15.92, 41.66), (15.90, 41.66)]),
         Polygon([(15.86, 41.58), (15.88, 41.58), (15.88, 41.60), (15.86, 41.60)])],
    )
    out = normalize.normalize_archeological_areas(raw_path=raw)
    assert sorted(out["name_it"].tolist()) == ["Grotta Scaloria", "Siponto"]
    assert "historic:civilization" in out.columns


# --- MASE Natura 2000 ------------------------------------------------

def _write_natura2000_zip(zip_path: Path) -> None:
    """Build a minimal MASE-like zip with a single shapefile.

    Coordinates are in EPSG:32632 (extended UTM 32N) metres. Two
    polygons sit inside the Manfredonia AOI bbox (≈ 41.6°N, 15.9°E →
    easting ≈ 1.02 M, northing ≈ 4.60 M); a third polygon is in Valle
    d'Aosta and must be filtered out.
    """
    src_dir = zip_path.parent / "n2k_src"
    src_dir.mkdir()
    shp = src_dir / "sic_zps_ita_32_reportnet_contuttiicampi.shp"
    gpd.GeoDataFrame(
        {
            "OBJECTID": [1, 2, 3],
            "site_code": ["IT9110005", "IT9110038", "IT9999999"],
            "tipo_sito": ["C", "A", "B"],
            "denominazi": [
                "Zone umide della Capitanata",
                "Paludi presso il Golfo di Manfredonia",
                "Far-away site",
            ],
            "reg_biog": ["MED", "MED", "ALP"],
            "regione": ["Puglia", "Puglia", "Valle d'Aosta"],
            "sic_zsc": ["ZSC", None, "ZSC"],
            "zps": ["ZPS", "ZPS", None],
            "hectares": ["14109", "14437", "100"],
        },
        geometry=[
            # Two polygons in the Manfredonia AOI. Extended UTM 32N:
            # easting ~1.07 M, northing ~4.63 M → lat/lon ≈ 41.6°N, 15.9°E
            # (derived empirically from the TINITALY e46005_s10 bbox).
            Polygon([
                (1_070_000, 4_625_000), (1_080_000, 4_625_000),
                (1_080_000, 4_635_000), (1_070_000, 4_635_000),
                (1_070_000, 4_625_000),
            ]),
            Polygon([
                (1_080_000, 4_625_000), (1_090_000, 4_625_000),
                (1_090_000, 4_635_000), (1_080_000, 4_635_000),
                (1_080_000, 4_625_000),
            ]),
            # Valle d'Aosta — far from our AOI.
            Polygon([
                (400_000, 5_050_000), (410_000, 5_050_000),
                (410_000, 5_060_000), (400_000, 5_060_000),
                (400_000, 5_050_000),
            ]),
        ],
        crs="EPSG:32632",
    ).to_file(shp, driver="ESRI Shapefile")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in src_dir.glob("sic_zps_ita_32_reportnet_contuttiicampi.*"):
            zf.write(f, arcname=f.name)


def _write_aoi_buffered(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [15.85, 41.55],
                                    [16.05, 41.55],
                                    [16.05, 41.70],
                                    [15.85, 41.70],
                                    [15.85, 41.55],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_normalize_natura2000_filters_by_aoi_bbox(tmp_path: Path):
    z = tmp_path / "n2k.zip"
    aoi = tmp_path / "aoi.geojson"
    _write_natura2000_zip(z)
    _write_aoi_buffered(aoi)

    out = normalize.normalize_natura2000(raw_zip=z, aoi_bbox_path=aoi)
    assert sorted(out["id"].tolist()) == ["IT9110005", "IT9110038"]
    assert (out["layer_id"] == "natura2000").all()
    assert (out["source_id"] == "mase_natura2000_2025_tuttiicampi").all()
    assert (out["year_data"] == 2025).all()
    assert "Zone umide della Capitanata" in out["name_it"].tolist()
    assert "tipo_sito" in out.columns


# --- sin_manfredonia (authoritative MASE/ISPRA perimeter) -----------

def _write_sin_shp(tmp_path: Path) -> Path:
    """Build a minimal SIN-like shapefile with multiple Puglia sites."""
    shp = tmp_path / "SIN.shp"
    gpd.GeoDataFrame(
        {
            "DGC_CODICE": [18.0, 18.0, 18.0, 37.0, 0.0],
            "SITO": ["MANFREDONIA", "MANFREDONIA", "MANFREDONIA", "TARANTO", "BARI"],
        },
        geometry=[
            # Three Manfredonia polygons in EPSG:32633 (UTM 33N).
            Polygon([
                (572_000, 4_605_000), (575_000, 4_605_000),
                (575_000, 4_608_000), (572_000, 4_608_000),
                (572_000, 4_605_000),
            ]),
            Polygon([
                (575_000, 4_605_000), (578_000, 4_605_000),
                (578_000, 4_608_000), (575_000, 4_608_000),
                (575_000, 4_605_000),
            ]),
            Polygon([
                (570_000, 4_600_000), (573_000, 4_600_000),
                (573_000, 4_603_000), (570_000, 4_603_000),
                (570_000, 4_600_000),
            ]),
            # Other Puglia SINs — must be filtered out.
            Polygon([
                (680_000, 4_480_000), (682_000, 4_480_000),
                (682_000, 4_482_000), (680_000, 4_482_000),
                (680_000, 4_480_000),
            ]),
            Polygon([
                (620_000, 4_550_000), (622_000, 4_550_000),
                (622_000, 4_552_000), (620_000, 4_552_000),
                (620_000, 4_550_000),
            ]),
        ],
        crs="EPSG:32633",
    ).to_file(shp, driver="ESRI Shapefile")
    return shp


def test_normalize_sin_manfredonia_filters_to_manfredonia_only(tmp_path: Path):
    shp = _write_sin_shp(tmp_path)
    out = normalize.normalize_sin_manfredonia(raw_path=shp)
    assert len(out) == 3   # only the three MANFREDONIA rows
    assert (out["layer_id"] == "sin_manfredonia").all()
    assert (out["source_id"] == "mase_sin_manfredonia_manual").all()
    assert (out["category"] == "sin").all()
    assert (out["year_data"] == 2024).all()
    assert (out["name_it"] == "MANFREDONIA").all()
    assert "DGC_CODICE" in out.columns
    # CRS preserved at this stage; downstream `to_storage_crs` reprojects.
    assert out.crs.to_epsg() == 32633


def test_natura_shapefile_inside_raises_when_no_shp(tmp_path: Path):
    z = tmp_path / "empty.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("readme.txt", "no shapefile here")
    with pytest.raises(ValueError, match="no shapefile"):
        normalize._natura_shapefile_inside(z)
