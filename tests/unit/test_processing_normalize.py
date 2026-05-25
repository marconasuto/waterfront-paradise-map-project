from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon

from manfredonia_map.processing import base, normalize

# --- coastline --------------------------------------------------------

def _write_osm_coastline(path: Path) -> None:
    gdf = gpd.GeoDataFrame(
        {
            "osmid": ["w1", "w2"],
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
    assert {"coastline", "admin_boundaries", "hydrography_surface"} <= set(
        normalize.NORMALIZERS
    )
    for lid, spec in normalize.NORMALIZERS.items():
        assert spec.layer_id == lid
        assert callable(spec.fn)
