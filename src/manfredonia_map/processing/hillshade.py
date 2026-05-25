"""DTM hillshade derivation — slope + aspect → 8-bit RGBA COG.

Standard Esri-style analytical hillshade:

    zenith  = (90 - altitude_deg) * pi / 180
    azimuth = (360 - azimuth_deg + 90) * pi / 180   (math-angle convention)
    slope   = arctan( z_factor * sqrt( dz/dx² + dz/dy² ) )
    aspect  = arctan2( dz/dy, -dz/dx )
    HS      = cos(zenith)·cos(slope) + sin(zenith)·sin(slope)·cos(azimuth - aspect)
    HS_8bit = clip(HS * 255, 0, 255).uint8

Gradients use ``numpy.gradient`` (central differences with one-sided
fall-back at edges), which produces nearly-identical visual output to
the canonical Esri 3x3 weighted kernel and is much simpler to read.

The output is a 4-band 8-bit RGBA COG (grayscale value in R/G/B + full
alpha) so a Mapbox raster tileset can stack it on top of the
hypsometric layer with a multiply blend.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import xarray as xr

from manfredonia_map.paths import DATA_PROCESSED
from manfredonia_map.processing import base, raster

#: Default sun position — NW azimuth, 45° altitude. Matches Esri /
#: gdaldem defaults and produces a familiar shaded relief look.
DEFAULT_AZIMUTH_DEG = 315.0
DEFAULT_ALTITUDE_DEG = 45.0

#: Vertical exaggeration factor. ``1.0`` = unexaggerated (preferred for
#: small relief differences; cartographers often push 1.5 to 3.0).
DEFAULT_Z_FACTOR = 1.0


def compute_hillshade(
    elevation: np.ndarray,
    *,
    cellsize_x: float,
    cellsize_y: float,
    azimuth_deg: float = DEFAULT_AZIMUTH_DEG,
    altitude_deg: float = DEFAULT_ALTITUDE_DEG,
    z_factor: float = DEFAULT_Z_FACTOR,
) -> np.ndarray:
    """Compute an 8-bit hillshade grayscale array from elevation.

    Args:
        elevation: 2-D float array of elevations. NaN (or masked) cells
            propagate to value 0 in the output.
        cellsize_x: Pixel size in CRS units (metres) along the x axis.
            Must be positive.
        cellsize_y: Pixel size in CRS units (metres) along the y axis.
            Must be positive — the raster orientation is handled
            internally.
        azimuth_deg: Sun azimuth in degrees clockwise from north.
        altitude_deg: Sun altitude in degrees above the horizon.
        z_factor: Vertical exaggeration (1.0 = no exaggeration).

    Returns:
        ``(H, W)`` ``uint8`` array with values in ``[0, 255]``.
    """
    if cellsize_x <= 0 or cellsize_y <= 0:
        raise ValueError(
            f"cellsize_x and cellsize_y must be positive (got "
            f"{cellsize_x}, {cellsize_y})"
        )

    zenith_rad = math.radians(90.0 - altitude_deg)
    azimuth_rad = math.radians((360.0 - azimuth_deg + 90.0) % 360.0)

    # numpy.gradient returns (dy, dx) when called with row,col spacing.
    # We pass spacing in (y, x) order to match the array axes.
    dy, dx = np.gradient(elevation, cellsize_y, cellsize_x)
    slope = np.arctan(z_factor * np.hypot(dx, dy))
    aspect = np.arctan2(dy, -dx)

    shaded = (
        math.cos(zenith_rad) * np.cos(slope)
        + math.sin(zenith_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
    )
    hs = np.clip(shaded * 255.0, 0.0, 255.0)
    # NaN does *not* propagate through central-difference gradient when the
    # NaN sits between two finite neighbours; mask explicitly so nodata
    # pixels in the source become nodata (value 0) in the output.
    invalid = ~np.isfinite(elevation) | ~np.isfinite(hs)
    hs = np.where(invalid, 0.0, hs)
    return hs.astype(np.uint8)


def grayscale_to_rgba(gray: np.ndarray) -> np.ndarray:
    """Wrap a grayscale ``uint8`` array as an ``(H, W, 4)`` RGBA array.

    Alpha is 255 everywhere the value is > 0 and 0 elsewhere — the
    latter is treated as nodata. This pairs with the hypsometric COG's
    alpha-band convention so styling can blend the two layers cleanly.
    """
    rgb = np.repeat(gray[..., np.newaxis], 3, axis=-1)
    alpha = np.where(gray > 0, 255, 0).astype(np.uint8)
    return np.concatenate([rgb, alpha[..., np.newaxis]], axis=-1)


def process_hillshade(
    raster_id: str,
    aoi,  # Shapely BaseGeometry; avoid the extra import
    *,
    processed_dir: Path = DATA_PROCESSED,
    azimuth_deg: float = DEFAULT_AZIMUTH_DEG,
    altitude_deg: float = DEFAULT_ALTITUDE_DEG,
    z_factor: float = DEFAULT_Z_FACTOR,
) -> Path:
    """Derive a hillshade COG from a registered ``raster_id``.

    Re-uses ``raster.read_raster`` + ``raster.reproject_and_clip`` so we
    stay aligned with the hypsometric COG's geometry; the analytical
    Zarr could be used here too once rioxarray's Zarr CRS round-trip is
    smoother (left as a future optimisation).
    """
    if raster_id not in raster.PROCESSORS:
        raise KeyError(f"unknown raster_id={raster_id!r}")
    spec = raster.PROCESSORS[raster_id]
    da = raster.read_raster(spec)
    clipped = raster.reproject_and_clip(da, dst_crs=base.ANALYSIS_CRS, aoi=aoi)

    values = clipped.values
    expected_band_dim = 3
    if values.ndim == expected_band_dim and values.shape[0] == 1:
        values = values[0]

    # The clipped DataArray's transform gives us metric pixel sizes
    # (we're in EPSG:32633). The y-resolution from rasterio is negative
    # (north-up rasters) — take abs.
    transform = clipped.rio.transform()
    cellsize_x = float(abs(transform.a))
    cellsize_y = float(abs(transform.e))

    gray = compute_hillshade(
        values,
        cellsize_x=cellsize_x,
        cellsize_y=cellsize_y,
        azimuth_deg=azimuth_deg,
        altitude_deg=altitude_deg,
        z_factor=z_factor,
    )
    rgba = grayscale_to_rgba(gray)
    rgba_da = raster._rgba_to_dataarray(rgba, ref_da=clipped)
    out = processed_dir / f"{raster_id}_hillshade_8bit.tif"
    raster.write_8bit_cog(rgba_da, out)
    return out


def _coerce_xarray(elevation: np.ndarray | xr.DataArray) -> np.ndarray:
    """Convenience: unwrap an ``xarray.DataArray`` to ``np.ndarray``."""
    if isinstance(elevation, xr.DataArray):
        return elevation.values
    return elevation
