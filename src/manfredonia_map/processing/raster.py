"""Raster processing: reproject + clip + 8-bit hypsometric COG.

Pipeline for every supported raster:

1. **Read** the raw GeoTIFF (possibly inside a zip) via ``rioxarray`` —
   returns an ``xarray.DataArray`` with CRS / transform / nodata metadata.
2. **Reproject** to the analysis CRS (EPSG:32633) using bilinear
   interpolation.
3. **Clip** to the AOI polygon, dropping pixels outside.
4. **Persist analytical** copy as a Zarr store under ``data/interim/``
   for future processing (hillshade derivation, mosaicking, etc.).
5. **Colormap** the values via a hand-rolled hypsometric tint
   (terrain-like ramp) → 8-bit RGBA.
6. **Write COG** under ``data/processed/`` ready for Mapbox raster
   tilesets (Mapbox only accepts 8-bit GeoTIFFs).

Each supported raster is a :class:`RasterProcessorSpec` entry in
:data:`PROCESSORS`. The CLI dispatcher in ``processing.cli`` runs the
pipeline end-to-end given a ``raster_id``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rioxarray
import xarray as xr
from rasterio.enums import Resampling
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry.base import BaseGeometry

from manfredonia_map.paths import DATA_INTERIM, DATA_PROCESSED, DATA_RAW
from manfredonia_map.processing import base

#: Discrete hypsometric stops used by :func:`hypsometric_tint`.
#: Each row: ``(normalised_elevation_in_[0,1], (R, G, B))``. Chosen for
#: combined land+sea rasters (TINITALY land DTM, EMODnet land+sea DEM).
TERRAIN_STOPS: tuple[tuple[float, tuple[int, int, int]], ...] = (
    (0.00, (10, 50, 130)),  # deep sea
    (0.15, (60, 130, 200)),  # shallow sea / coastal shelf
    (0.20, (220, 220, 160)),  # beach / lowland
    (0.30, (110, 180, 90)),  # green plain
    (0.50, (170, 150, 80)),  # foothills
    (0.75, (140, 100, 60)),  # peaks
    (0.90, (200, 200, 200)),  # alpine
    (1.00, (255, 255, 255)),  # summit
)


@dataclass(frozen=True)
class RasterProcessorSpec:
    """How to process one raster from raw to 8-bit COG."""

    raster_id: str
    raw_path: Path
    source_id: str
    year_data: int
    inner_zip_filename: str | None = None  # for zipped rasters (TINITALY)
    # Fixed value range for the colormap, in source units (e.g. metres of
    # elevation). When None, the actual min/max of the clipped raster are
    # used; pinning yields consistent colours across re-runs.
    value_min: float | None = None
    value_max: float | None = None


PROCESSORS: dict[str, RasterProcessorSpec] = {
    "tinitaly_dtm": RasterProcessorSpec(
        raster_id="tinitaly_dtm",
        raw_path=DATA_RAW / "tinitaly" / "e46005_s10.zip",
        inner_zip_filename="e46005_s10/e46005_s10.tif",
        source_id="tinitaly_1_1_e46005_s10",
        year_data=2023,
        # Gargano peaks ~840 m; lock the range so re-runs use the same
        # colour ramp regardless of which pixels happened to clip out.
        value_min=-50.0,
        value_max=850.0,
    ),
    "emodnet_bathymetry": RasterProcessorSpec(
        raster_id="emodnet_bathymetry",
        # Filename embeds the bbox + resolution; we read whatever the
        # acquisition step wrote (one file per AOI bbox).
        raw_path=DATA_RAW / "emodnet_bathymetry",
        source_id="emodnet_bathymetry_dtm2024_mean",
        year_data=2024,
        # AOI range observed empirically: -16 m sea to +667 m Gargano hills.
        # Share the DTM range for visual consistency with `tinitaly_dtm`.
        value_min=-50.0,
        value_max=850.0,
    ),
}


def _resolve_emodnet_geotiff(raw_dir: Path) -> Path:
    """Return the single GeoTIFF inside ``raw_dir`` (EMODnet variable name)."""
    tifs = sorted(raw_dir.glob("*.tif"))
    if not tifs:
        raise FileNotFoundError(f"no GeoTIFF in {raw_dir}")
    if len(tifs) > 1:
        raise ValueError(f"expected exactly one GeoTIFF in {raw_dir}; found {len(tifs)}")
    return tifs[0]


def read_raster(spec: RasterProcessorSpec) -> xr.DataArray:
    """Open the raw raster as an ``xarray.DataArray`` with CRS metadata."""
    if spec.inner_zip_filename is not None:
        # Verify the inner file exists in the zip for a clear error message
        # when the wrong tile id is configured.
        with zipfile.ZipFile(spec.raw_path) as zf:
            if spec.inner_zip_filename not in zf.namelist():
                raise FileNotFoundError(f"{spec.inner_zip_filename} not in {spec.raw_path}")
        return rioxarray.open_rasterio(
            f"zip://{spec.raw_path}!{spec.inner_zip_filename}", masked=True
        )
    if spec.raw_path.is_dir():
        return rioxarray.open_rasterio(_resolve_emodnet_geotiff(spec.raw_path), masked=True)
    return rioxarray.open_rasterio(spec.raw_path, masked=True)


def reproject_and_clip(da: xr.DataArray, *, dst_crs: str, aoi: BaseGeometry) -> xr.DataArray:
    """Re-project to ``dst_crs`` and clip to the AOI polygon."""
    reprojected = da.rio.reproject(dst_crs, resampling=Resampling.bilinear)
    aoi_in_dst = gpd.GeoDataFrame(geometry=[aoi], crs=base.STORAGE_CRS).to_crs(dst_crs).geometry
    return reprojected.rio.clip(aoi_in_dst, drop=True, all_touched=True)


def hypsometric_tint(values: np.ndarray, *, value_min: float, value_max: float) -> np.ndarray:
    """Map a 2-D elevation array to an ``(H, W, 4)`` ``uint8`` RGBA array.

    Pixels with NaN (nodata) get ``alpha = 0`` so they render transparent
    in Mapbox raster tilesets.
    """
    valid = np.isfinite(values)
    normalised = np.zeros_like(values, dtype=np.float64)
    if value_max > value_min:
        normalised = (values - value_min) / (value_max - value_min)
    normalised = np.clip(normalised, 0.0, 1.0)
    normalised = np.where(valid, normalised, 0.0)

    stops = np.array([s[0] for s in TERRAIN_STOPS])
    colors = np.array([s[1] for s in TERRAIN_STOPS], dtype=np.float64)
    r = np.interp(normalised, stops, colors[:, 0])
    g = np.interp(normalised, stops, colors[:, 1])
    b = np.interp(normalised, stops, colors[:, 2])
    a = np.where(valid, 255, 0)
    return np.stack([r, g, b, a], axis=-1).astype(np.uint8)


def _rgba_to_dataarray(rgba: np.ndarray, *, ref_da: xr.DataArray) -> xr.DataArray:
    """Wrap a ``(H, W, 4)`` ``uint8`` array as an xarray ``(band, y, x)``."""
    # rgba shape: (H, W, 4) → transpose to (4, H, W).
    bands = rgba.transpose(2, 0, 1)
    # Drop the singleton band dim from the reference, if present, before
    # copying coordinates.
    if "band" in ref_da.dims and ref_da.sizes.get("band", 1) == 1:
        ref_da = ref_da.isel(band=0, drop=True)
    out = xr.DataArray(
        bands,
        dims=("band", "y", "x"),
        coords={"band": [1, 2, 3, 4], "y": ref_da.y, "x": ref_da.x},
    )
    out.rio.write_crs(ref_da.rio.crs, inplace=True)
    out.rio.write_transform(ref_da.rio.transform(), inplace=True)
    # No explicit nodata — the alpha band (#4) already encodes transparency
    # for masked pixels. Setting *both* triggers a ``NodataAlphaMaskWarning``
    # from rio-cogeo and is genuinely ambiguous for downstream renderers.
    return out


def write_8bit_cog(rgba_da: xr.DataArray, out_path: Path, *, profile_name: str = "deflate") -> None:
    """Write an 8-bit RGBA ``xarray`` DataArray as a Cloud-Optimized GeoTIFF.

    Uses ``rio-cogeo`` to produce a real COG with internal overviews and
    tiling — what Mapbox raster tilesets expect.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out_path.name + ".", suffix=".tif", dir=out_path.parent)
    os.close(fd)
    try:
        tmp_path = Path(tmp)
        rgba_da.rio.to_raster(tmp_path, driver="GTiff", dtype="uint8")
        cog_translate(
            str(tmp_path),
            str(out_path),
            cog_profiles.get(profile_name),
            in_memory=True,
            quiet=True,
            use_cog_driver=True,
        )
        os.chmod(out_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_zarr(da: xr.DataArray, out_path: Path) -> None:
    """Persist the analytical (float) raster as a Zarr store."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # zarr is happiest with a Dataset; the elevation band becomes a
    # named variable so future processing (hillshade, mosaics, ...) can
    # round-trip through xarray cleanly.
    name = "elevation"
    if "band" in da.dims and da.sizes.get("band", 1) == 1:
        da = da.isel(band=0, drop=True)
    ds = da.to_dataset(name=name)
    # Drop any existing store at out_path so the write is idempotent.
    if out_path.exists():
        shutil.rmtree(out_path)
    # ``consolidated=True`` is a cloud-storage optimisation; the Zarr v3
    # spec does not include it and zarr 3.x raises ``ZarrUserWarning``
    # when asked for it. Local stores don't benefit from consolidation,
    # so we skip it explicitly.
    ds.to_zarr(out_path, mode="w", consolidated=False)


def process_raster(
    spec: RasterProcessorSpec,
    aoi: BaseGeometry,
    *,
    interim_dir: Path = DATA_INTERIM,
    processed_dir: Path = DATA_PROCESSED,
) -> tuple[Path, Path]:
    """Run the full raster pipeline for ``spec``; return ``(zarr_path, cog_path)``."""
    da = read_raster(spec)
    clipped = reproject_and_clip(da, dst_crs=base.ANALYSIS_CRS, aoi=aoi)

    # 1) analytical (interim) Zarr
    zarr_path = interim_dir / f"{spec.raster_id}.zarr"
    write_zarr(clipped, zarr_path)

    # 2) 8-bit hypsometric COG (Mapbox-ready)
    values = clipped.values
    _expected_band_dim = 3
    if values.ndim == _expected_band_dim and values.shape[0] == 1:
        values = values[0]
    vmin = spec.value_min if spec.value_min is not None else float(np.nanmin(values))
    vmax = spec.value_max if spec.value_max is not None else float(np.nanmax(values))
    rgba = hypsometric_tint(values, value_min=vmin, value_max=vmax)
    rgba_da = _rgba_to_dataarray(rgba, ref_da=clipped)
    cog_path = processed_dir / f"{spec.raster_id}_8bit.tif"
    write_8bit_cog(rgba_da, cog_path)
    return zarr_path, cog_path
