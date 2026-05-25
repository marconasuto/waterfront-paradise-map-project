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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from manfredonia_map.paths import DATA_RAW
from manfredonia_map.processing import base

# --- coastline (OSM) ---------------------------------------------------

def normalize_coastline(
    raw_path: Path = DATA_RAW / "osm_coastline" / "coastline.geojson",
) -> gpd.GeoDataFrame:
    """Normalize OSM coastline lines into the canonical schema."""
    gdf = gpd.read_file(raw_path)
    return base.conform_to_schema(
        gdf,
        layer_id="coastline",
        source_id="osm_coastline",
        year_data=2026,
        category="coastline",
        id_col="osmid" if "osmid" in gdf.columns else None,
        name_col="name" if "name" in gdf.columns else None,
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
    "coastline": NormalizerSpec(
        layer_id="coastline",
        fn=normalize_coastline,
    ),
    "admin_boundaries": NormalizerSpec(
        layer_id="admin_boundaries",
        fn=normalize_admin_boundaries,
    ),
    "hydrography_surface": NormalizerSpec(
        layer_id="hydrography_surface",
        fn=normalize_hydrography_surface,
    ),
}
