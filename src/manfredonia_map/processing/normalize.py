"""Per-layer normalizers — read raw input, return a schema-conformed GDF.

Each :class:`NormalizerSpec` in :data:`NORMALIZERS` is a small recipe
that the CLI dispatcher (``processing.cli.process_vector``) executes.
A normalizer is responsible for:

1. Reading the raw input (one or more files under ``data/raw/``).
2. Filtering / sub-setting per layer rules.
3. Calling :func:`~manfredonia_map.processing.base.conform_to_schema`
   to produce the canonical column shape.

The downstream pipeline (reproject → clip → make_valid → write) is
generic and lives in ``processing.base``.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from manfredonia_map.paths import CONFIG_DIR, DATA_RAW
from manfredonia_map.processing import base


#: OSM acquisitions all share the same on-disk shape: a single GeoJSON
#: under ``data/raw/osm_<source>/<source>.geojson`` with an ``id`` column
#: (OSM ID) and a ``name`` column when the feature is named. The helper
#: below DRYs the per-layer normalizers down to a one-line spec.
def _normalize_osm_layer(
    raw_path: Path,
    *,
    layer_id: str,
    source_id: str,
    year_data: int,
    category: str,
    extra_columns: tuple[str, ...] = (),
) -> gpd.GeoDataFrame:
    """Read an OSM raw GeoJSON and conform it to the canonical schema."""
    gdf = gpd.read_file(raw_path)
    return base.conform_to_schema(
        gdf,
        layer_id=layer_id,
        source_id=source_id,
        year_data=year_data,
        category=category,
        id_col="id" if "id" in gdf.columns else None,
        name_col="name" if "name" in gdf.columns else None,
        extra_columns=extra_columns,
    )


# --- coastline (OSM) ---------------------------------------------------

def normalize_coastline(
    raw_path: Path = DATA_RAW / "osm_coastline" / "coastline.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM coastline lines into the canonical schema."""
    return _normalize_osm_layer(
        raw_path,
        layer_id="coastline",
        source_id="osm_coastline",
        year_data=2026,
        category="coastline",
    )


# --- admin_boundaries (ISTAT zipped shapefile) -------------------------

ISTAT_TARGET_COMUNI: tuple[str, ...] = (
    "071029",  # Manfredonia
    "071033",  # Monte Sant'Angelo
)


def _istat_comuni_shp(zip_path: Path) -> str:
    """Return the inner-zip GDAL VSI path for the comuni shapefile."""
    inner = "Limiti01012024_g/Com01012024_g/Com01012024_g_WGS84.shp"
    return f"zip://{zip_path}!{inner}"


def normalize_admin_boundaries(
    raw_zip: Path = DATA_RAW / "istat_admin" / "Limiti01012024_g.zip",
    target_comuni: tuple[str, ...] = ISTAT_TARGET_COMUNI,
) -> gpd.GeoDataFrame:
    """Normalize ISTAT comuni; keep only Manfredonia + Monte Sant'Angelo."""
    gdf = gpd.read_file(_istat_comuni_shp(raw_zip))
    filtered = gdf[gdf["PRO_COM_T"].astype(str).isin(target_comuni)].copy()
    return base.conform_to_schema(
        filtered,
        layer_id="admin_boundaries",
        source_id="istat_limiti_2024_generalized",
        year_data=2024,
        category="admin_comune",
        id_col="PRO_COM_T",
        name_col="COMUNE",
        extra_columns=("PROVINCIA", "REGIONE"),
    )


# --- hydrography_surface (ISPRA WFS) -----------------------------------

def normalize_hydrography_surface(
    raw_path: Path = DATA_RAW / "ispra_hydrography" / "hy_reticolo_idrografico_aoi.geojson",
) -> gpd.GeoDataFrame:
    """Normalize ISPRA Reticolo Idrografico Nazionale (river network)."""
    gdf = gpd.read_file(raw_path)
    # ISPRA `tipo` column is FIUME / TORRENTE / CANALE / etc. Default to
    # `water` so styling picks the same palette regardless of subtype;
    # the raw `tipo` is preserved as an extra column for richer styling
    # in the web app if we want it.
    return base.conform_to_schema(
        gdf,
        layer_id="hydrography_surface",
        source_id="ispra_hy_reticolo_idrografico",
        year_data=2020,
        category="water",
        id_col="id_tratta" if "id_tratta" in gdf.columns else None,
        name_col="nome" if "nome" in gdf.columns else None,
        extra_columns=("tipo", "ordine", "bacino_pri", "st_length_"),
    )


# --- roads (OSM) -------------------------------------------------------

def normalize_roads(
    raw_path: Path = DATA_RAW / "osm_roads" / "roads.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM road network (every `highway=*` way)."""
    return _normalize_osm_layer(
        raw_path,
        layer_id="roads",
        source_id="osm_roads",
        year_data=2026,
        category="road",
        extra_columns=("highway", "surface", "maxspeed", "lanes", "ref"),
    )


# --- cycle_paths (OSM) -------------------------------------------------

def normalize_cycle_paths(
    raw_path: Path = DATA_RAW / "osm_cycle_paths" / "cycle_paths.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM dedicated cycle infrastructure (`highway=cycleway`)."""
    return _normalize_osm_layer(
        raw_path,
        layer_id="cycle_paths",
        source_id="osm_cycle_paths",
        year_data=2026,
        category="cycle",
        extra_columns=("highway", "surface", "bicycle", "foot"),
    )


# --- cycle_routes (OSM relations — may be empty for our AOI) ----------

def normalize_cycle_routes(
    raw_path: Path = DATA_RAW / "osm_cycle_routes" / "cycle_routes.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM long-distance bike routes (relations).

    Falls back to an empty GeoDataFrame when the raw file is missing —
    Ciclovia Adriatica is not currently tagged through our AOI
    (OPEN-CICLOVIA-1 in ``SPECIFICATIONS.md``).
    """
    if not raw_path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=base.STORAGE_CRS)
    return _normalize_osm_layer(
        raw_path,
        layer_id="cycle_routes",
        source_id="osm_cycle_routes",
        year_data=2026,
        category="cycle",
        extra_columns=("network", "ref", "operator"),
    )


# --- harbours (OSM) ---------------------------------------------------

def normalize_harbours(
    raw_path: Path = DATA_RAW / "osm_harbours" / "harbours.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM port elements (`harbour`, `man_made=pier|breakwater`)."""
    return _normalize_osm_layer(
        raw_path,
        layer_id="harbours",
        source_id="osm_harbours",
        year_data=2026,
        category="harbour",
        extra_columns=("man_made", "harbour", "mooring", "material"),
    )


# --- beaches (OSM) ----------------------------------------------------

def normalize_beaches(
    raw_path: Path = DATA_RAW / "osm_beaches" / "beaches.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM beaches (`natural=beach`)."""
    return _normalize_osm_layer(
        raw_path,
        layer_id="beaches",
        source_id="osm_beaches",
        year_data=2026,
        category="beach",
        extra_columns=("surface", "wheelchair"),
    )


# --- wetlands (OSM `natural=wetland`) --------------------------------

def normalize_wetlands(
    raw_path: Path = DATA_RAW / "osm_wetlands" / "wetlands.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM informal wetland polygons.

    Distinct from the protected-area perimeters in ``natura2000`` (which
    cover wider habitats designated under EU directives). Lago Salso
    appears here as three polygons.
    """
    return _normalize_osm_layer(
        raw_path,
        layer_id="wetlands",
        source_id="osm_wetlands",
        year_data=2026,
        category="wetland",
        extra_columns=("wetland", "wikidata"),
    )


# --- industrial_areas (OSM `landuse=industrial|brownfield`) ----------

def normalize_industrial_areas(
    raw_path: Path = DATA_RAW / "osm_industrial" / "industrial.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM industrial / brownfield polygons.

    Contains the "Zona Industriale di Manfredonia-Monte Sant'Angelo"
    polygon used as the v1 SIN proxy (OPEN-SIN-1 in
    ``SPECIFICATIONS.md``).
    """
    return _normalize_osm_layer(
        raw_path,
        layer_id="industrial_areas",
        source_id="osm_industrial",
        year_data=2026,
        category="industrial",
        extra_columns=("landuse",),
    )


# --- archeological_areas (OSM `historic=archaeological_site`) --------

def normalize_archeological_areas(
    raw_path: Path = DATA_RAW / "osm_archaeology" / "archaeology.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM archaeological sites (Grotta Scaloria, Siponto, ...).

    v1 proxy for MiC Vincoli in Rete (OPEN-VIR-1 in ``SPECIFICATIONS.md``).
    """
    return _normalize_osm_layer(
        raw_path,
        layer_id="archeological_areas",
        source_id="osm_archaeology",
        year_data=2026,
        category="archeological",
        extra_columns=("historic", "wikidata", "historic:civilization"),
    )


# --- sin_manfredonia (authoritative MASE/ISPRA SIN perimeter) --------

#: ``SITO`` column value used to filter the multi-SIN Puglia shapefile
#: down to the Manfredonia SIN-5 sub-polygons (5 polygons total covering
#: public landfills + ex-Enichem private area + marine areas).
SIN_TARGET_SITO = "MANFREDONIA"


def normalize_sin_manfredonia(
    raw_path: Path = DATA_RAW / "regione_puglia_sin" / "sin_puglia.zip",
) -> gpd.GeoDataFrame:
    """Normalize the authoritative SIN Manfredonia perimeter.

    Source: **Regione Puglia / InnovaPuglia** open-data CKAN dataset
    *Siti di Interesse Nazionale (SIN)* —
    ``https://dati.puglia.it/ckan/dataset/siti-di-interesse-nazionale-sin``
    (CC-BY-4.0). The shapefile inside the zip is in EPSG:32633 and
    contains 18 SIN polygons across all 4 Puglia SINs (Bari, Brindisi,
    Manfredonia, Taranto); we filter to ``SITO == "MANFREDONIA"``
    (5 polygons covering public landfills + ex-Enichem private area +
    marine areas) before passing to the generic clip step.

    Closes OPEN-SIN-1 in ``SPECIFICATIONS.md``.
    """
    gdf = gpd.read_file(f"zip://{raw_path}!sin/SIN.shp")
    filtered = gdf[gdf["SITO"] == SIN_TARGET_SITO].copy()
    return base.conform_to_schema(
        filtered,
        layer_id="sin_manfredonia",
        source_id="regione_puglia_sin",
        # SIN-5 perimeter initial decree 2000-01-10, modified 2024-12-02.
        year_data=2024,
        category="sin",
        name_col="SITO",
        extra_columns=("DGC_CODICE",),
    )


# --- natura2000 (MASE national bundle filtered to AOI bbox) ----------

#: Default Natura 2000 shapefile path inside the zip (single .shp).
_NATURA_SHP_INNER = "sic_zps_ita_32_reportnet_contuttiicampi.shp"


def _natura_shapefile_inside(raw_zip: Path) -> str:
    """Locate the single .shp inside the MASE Natura 2000 zip."""
    with zipfile.ZipFile(raw_zip) as zf:
        shps = sorted(n for n in zf.namelist() if n.lower().endswith(".shp"))
    if not shps:
        raise ValueError(f"no shapefile found inside {raw_zip}")
    return shps[0]


def normalize_natura2000(
    raw_zip: Path = DATA_RAW / "mase_natura2000" / "sic_zps_ita_32_tuttiicampi_2025.zip",
    aoi_bbox_path: Path = CONFIG_DIR / "aoi_buffered.geojson",
) -> gpd.GeoDataFrame:
    """Filter MASE Natura 2000 to sites whose perimeter intersects the AOI bbox.

    The MASE bundle is national (2,649 sites in EPSG:32632). We pre-filter
    to the AOI's bounding box (cheap geometry test) before passing to the
    generic ``clip_to_aoi`` step downstream; that avoids reprojecting and
    intersecting all 2,649 polygons against a complex AOI shape.
    """
    inner = _natura_shapefile_inside(raw_zip)
    gdf = gpd.read_file(f"zip://{raw_zip}!{inner}")
    gdf_4326 = gdf.to_crs(base.STORAGE_CRS)
    aoi_total_bounds = gpd.read_file(aoi_bbox_path).total_bounds
    bbox_poly = box(*aoi_total_bounds)
    filtered = gdf_4326[gdf_4326.geometry.intersects(bbox_poly)].copy()
    return base.conform_to_schema(
        filtered,
        layer_id="natura2000",
        source_id="mase_natura2000_2025_tuttiicampi",
        year_data=2025,
        category="natura2000",
        id_col="site_code",
        name_col="denominazi",
        extra_columns=("tipo_sito", "sic_zsc", "zps", "hectares", "regione"),
    )


# --- registry ---------------------------------------------------------

#: One row per supported layer_id. Functions take no arguments so the
#: CLI dispatcher is trivial; per-layer raw paths are baked in as
#: defaults but tests can pass alternative paths.
@dataclass(frozen=True)
class NormalizerSpec:
    """How to normalize one ``layer_id``."""

    layer_id: str
    fn: Callable[[], gpd.GeoDataFrame]


NORMALIZERS: dict[str, NormalizerSpec] = {
    "coastline": NormalizerSpec(layer_id="coastline", fn=normalize_coastline),
    "admin_boundaries": NormalizerSpec(
        layer_id="admin_boundaries", fn=normalize_admin_boundaries
    ),
    "hydrography_surface": NormalizerSpec(
        layer_id="hydrography_surface", fn=normalize_hydrography_surface
    ),
    "roads": NormalizerSpec(layer_id="roads", fn=normalize_roads),
    "cycle_paths": NormalizerSpec(layer_id="cycle_paths", fn=normalize_cycle_paths),
    "cycle_routes": NormalizerSpec(layer_id="cycle_routes", fn=normalize_cycle_routes),
    "harbours": NormalizerSpec(layer_id="harbours", fn=normalize_harbours),
    "beaches": NormalizerSpec(layer_id="beaches", fn=normalize_beaches),
    "wetlands": NormalizerSpec(layer_id="wetlands", fn=normalize_wetlands),
    "industrial_areas": NormalizerSpec(
        layer_id="industrial_areas", fn=normalize_industrial_areas
    ),
    "archeological_areas": NormalizerSpec(
        layer_id="archeological_areas", fn=normalize_archeological_areas
    ),
    "natura2000": NormalizerSpec(layer_id="natura2000", fn=normalize_natura2000),
    "sin_manfredonia": NormalizerSpec(
        layer_id="sin_manfredonia", fn=normalize_sin_manfredonia
    ),
}
