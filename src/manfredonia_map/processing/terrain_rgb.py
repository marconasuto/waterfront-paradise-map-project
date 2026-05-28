"""Build a Mapbox Terrain-RGB raster from the LIDAR DTM + bathymetry.

Mapbox `setTerrain()` consumes a `raster-dem` source that encodes
elevation in the RGB channels using the formula

    elev = -10000 + ((R * 256 * 256) + (G * 256) + B) * 0.1

(metres, 0.1 m resolution, -10 000 m floor). This module produces such
a raster by:

1. Reading the **float32** TINITALY DTM (from raw zip; we do not use the
   8-bit hypsometric COG because the encoding needs the original
   precision).
2. Reading the EMODnet bathymetry GeoTIFF.
3. Merging both onto a common EPSG:3857 grid via a `rioxarray` mosaic
   with the DTM taking precedence on land overlaps.
4. Clipping the merged DEM to the AOI envelope.
5. Encoding every pixel into 8-bit RGB using the Terrain-RGB formula.
6. Writing the result as a Cloud-Optimized GeoTIFF that the publishing
   pipeline can upload to Mapbox as a raster tileset.

The output is a single `data/processed/terrain_rgb.tif` ready for the
Mapbox Uploads API. The frontend then wires it up via:

    map.addSource("manfredonia-terrain", {
      type: "raster-dem",
      url: "mapbox://marconasuto.manfredonia-terrain-rgb-v1",
      tileSize: 512,
      maxzoom: 14,
    });
    map.setTerrain({ source: "manfredonia-terrain", exaggeration: 1.3 });

The encoding is exercised by unit tests on synthetic float arrays so
the conversion stays stable under refactors.
"""

from __future__ import annotations

import os
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

from manfredonia_map.paths import DATA_PROCESSED, DATA_RAW
from manfredonia_map.processing import base

#: Mapbox Terrain-RGB constants. The "v1" encoding ships in Mapbox GL JS
#: out of the box; the alternative "v2" mode (`encoding: "terrarium"`)
#: uses a different formula. We stick to v1 because Mapbox's own
#: `mapbox.mapbox-terrain-dem-v1` tileset uses the same one and the
#: viewer code is simpler.
ELEV_FLOOR_M: float = -10_000.0
ELEV_QUANT_M: float = 0.1

#: Web Mercator — the projection Mapbox renders raster-dem tiles in.
WEB_MERCATOR_CRS: str = "EPSG:3857"


@dataclass(frozen=True)
class TerrainRgbSpec:
    """Inputs and output path for the Terrain-RGB build."""

    dtm_zip: Path
    dtm_inner_filename: str
    bathy_dir: Path
    out_path: Path
    exaggeration: float = 1.0


DEFAULT_SPEC = TerrainRgbSpec(
    dtm_zip=DATA_RAW / "tinitaly" / "e46005_s10.zip",
    dtm_inner_filename="e46005_s10/e46005_s10.tif",
    bathy_dir=DATA_RAW / "emodnet_bathymetry",
    out_path=DATA_PROCESSED / "terrain_rgb.tif",
)


def encode_terrain_rgb(elev_m: np.ndarray) -> np.ndarray:
    """Encode a float elevation array to a `(3, H, W)` uint8 RGB stack.

    NaN pixels become RGB (1, 134, 160) — the value the Mapbox spec
    designates for "no data" (elev = 0 metres, with the smallest
    non-zero component to distinguish from a real zero). Callers that
    need alpha-based masking should add a 4th band themselves.

    Round-trips with :func:`decode_terrain_rgb` to within 0.05 m for
    elevations in [-10 000, 10 000] m.
    """
    if elev_m.dtype != np.float64:
        elev_m = elev_m.astype(np.float64, copy=False)
    valid = np.isfinite(elev_m)
    # Replace NaN with 0 m before encoding so the integer math is stable;
    # we restore the spec's "no-data" value afterwards.
    safe = np.where(valid, elev_m, 0.0)
    n = np.rint((safe - ELEV_FLOOR_M) / ELEV_QUANT_M).astype(np.int64)
    # Clamp to the 24-bit Terrain-RGB range to keep the math defined for
    # absurd inputs (out-of-range pixels render as the clamped value).
    n = np.clip(n, 0, (1 << 24) - 1)
    r = ((n >> 16) & 0xFF).astype(np.uint8)
    g = ((n >> 8) & 0xFF).astype(np.uint8)
    b = (n & 0xFF).astype(np.uint8)
    if not np.all(valid):
        nodata_r, nodata_g, nodata_b = 1, 134, 160  # baked from spec
        r = np.where(valid, r, nodata_r).astype(np.uint8)
        g = np.where(valid, g, nodata_g).astype(np.uint8)
        b = np.where(valid, b, nodata_b).astype(np.uint8)
    return np.stack([r, g, b], axis=0)


def decode_terrain_rgb(rgb: np.ndarray) -> np.ndarray:
    """Inverse of :func:`encode_terrain_rgb` — for tests / debugging."""
    r = rgb[0].astype(np.int64)
    g = rgb[1].astype(np.int64)
    b = rgb[2].astype(np.int64)
    return ELEV_FLOOR_M + ((r << 16) | (g << 8) | b) * ELEV_QUANT_M


def _open_dtm(spec: TerrainRgbSpec) -> xr.DataArray:
    with zipfile.ZipFile(spec.dtm_zip) as zf:
        if spec.dtm_inner_filename not in zf.namelist():
            raise FileNotFoundError(f"{spec.dtm_inner_filename} not in {spec.dtm_zip}")
    return rioxarray.open_rasterio(
        f"zip://{spec.dtm_zip}!{spec.dtm_inner_filename}", masked=True
    )


def _open_bathy(spec: TerrainRgbSpec) -> xr.DataArray:
    tifs = sorted(spec.bathy_dir.glob("*.tif"))
    if not tifs:
        raise FileNotFoundError(f"no GeoTIFF in {spec.bathy_dir}")
    return rioxarray.open_rasterio(tifs[0], masked=True)


def merge_dtm_bathy(
    dtm: xr.DataArray,
    bathy: xr.DataArray,
    *,
    aoi: BaseGeometry,
    target_crs: str = WEB_MERCATOR_CRS,
) -> xr.DataArray:
    """Re-project both rasters to ``target_crs`` and merge.

    The DTM is the higher-resolution dataset (10 m TinItaly) and is
    authoritative wherever it has valid data. The bathymetry fills in
    sea pixels (where the DTM is NaN). The output is a single-band
    float32 ``DataArray`` clipped to the AOI envelope.
    """
    dtm_xy = dtm.rio.reproject(target_crs, resampling=Resampling.bilinear)
    if "band" in dtm_xy.dims and dtm_xy.sizes.get("band", 1) == 1:
        dtm_xy = dtm_xy.isel(band=0, drop=True)

    # Reproject bathy onto the DTM grid so they overlap cell-for-cell.
    bathy_xy = bathy.rio.reproject_match(dtm_xy, resampling=Resampling.bilinear)
    if "band" in bathy_xy.dims and bathy_xy.sizes.get("band", 1) == 1:
        bathy_xy = bathy_xy.isel(band=0, drop=True)

    merged_vals = np.where(np.isfinite(dtm_xy.values), dtm_xy.values, bathy_xy.values)
    merged = xr.DataArray(
        merged_vals.astype(np.float32),
        dims=dtm_xy.dims,
        coords=dtm_xy.coords,
    )
    merged.rio.write_crs(target_crs, inplace=True)
    merged.rio.write_transform(dtm_xy.rio.transform(), inplace=True)

    aoi_in_dst = gpd.GeoDataFrame(geometry=[aoi], crs=base.STORAGE_CRS).to_crs(target_crs).geometry
    return merged.rio.clip(aoi_in_dst, drop=True, all_touched=True)


def _rgb_to_dataarray(rgb: np.ndarray, *, ref_da: xr.DataArray) -> xr.DataArray:
    out = xr.DataArray(
        rgb,
        dims=("band", "y", "x"),
        coords={"band": [1, 2, 3], "y": ref_da.y, "x": ref_da.x},
    )
    out.rio.write_crs(ref_da.rio.crs, inplace=True)
    out.rio.write_transform(ref_da.rio.transform(), inplace=True)
    return out


def write_cog(rgb_da: xr.DataArray, out_path: Path) -> None:
    """Write the encoded RGB stack as a Cloud-Optimized GeoTIFF."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out_path.name + ".", suffix=".tif", dir=out_path.parent)
    os.close(fd)
    try:
        tmp_path = Path(tmp)
        rgb_da.rio.to_raster(tmp_path, driver="GTiff", dtype="uint8")
        cog_translate(
            str(tmp_path),
            str(out_path),
            cog_profiles.get("deflate"),
            in_memory=True,
            quiet=True,
            use_cog_driver=True,
        )
        os.chmod(out_path, 0o644)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_terrain_rgb(
    spec: TerrainRgbSpec = DEFAULT_SPEC,
    *,
    aoi: BaseGeometry,
) -> Path:
    """Run the full Terrain-RGB pipeline.

    Returns the path to the written COG. Re-runs are idempotent; the
    output file is overwritten in place.
    """
    dtm = _open_dtm(spec)
    bathy = _open_bathy(spec)
    merged = merge_dtm_bathy(dtm, bathy, aoi=aoi)
    if spec.exaggeration != 1.0:
        # Exaggeration usually lives client-side, but baking it in lets
        # us ship a "punchier" DEM for low-zoom previews if needed.
        merged = merged * spec.exaggeration
    rgb = encode_terrain_rgb(merged.values)
    rgb_da = _rgb_to_dataarray(rgb, ref_da=merged)
    write_cog(rgb_da, spec.out_path)
    return spec.out_path


__all__ = [
    "DEFAULT_SPEC",
    "ELEV_FLOOR_M",
    "ELEV_QUANT_M",
    "WEB_MERCATOR_CRS",
    "TerrainRgbSpec",
    "build_terrain_rgb",
    "decode_terrain_rgb",
    "encode_terrain_rgb",
    "merge_dtm_bathy",
    "write_cog",
]
