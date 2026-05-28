#!/usr/bin/env python3
"""Build a Mapbox-Tiling-compatible Terrain-RGB MBTiles and upload it.

The Uploads API recompresses standalone GeoTIFFs lossily, which trashes
the bit-packed Terrain-RGB encoding (see `plans/10_3d_basemap.md` Phase
2b). Packaging the same elevation data into an MBTiles with **PNG**
tiles via `rio rgbify` makes Mapbox preserve the tiles byte-for-byte.

Steps:

  1. Merge the float-32 TINITALY DTM + EMODnet bathymetry on a common
     EPSG:3857 grid (re-using the existing `terrain_rgb.merge_dtm_bathy`
     helper).
  2. Write the merged float DEM to a temporary GeoTIFF.
  3. Shell out to ``rio rgbify`` to encode it into a PNG-tile MBTiles.
  4. Upload that MBTiles via the existing ``MapboxUploadsClient``.

Usage:
  pixi run --environment dev python scripts/build_terrain_mbtiles.py \
      [--tileset-id manfredonia-terrain-rgb-v2]

Re-using the same tileset id overwrites the previous version.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import rasterio  # noqa: E402

from manfredonia_map.processing import base, terrain_rgb  # noqa: E402
from manfredonia_map.publishing.uploads_api import MapboxUploadsClient  # noqa: E402


def write_merged_float(spec: terrain_rgb.TerrainRgbSpec, *, aoi, out_path: Path) -> Path:
    """Run the merge then write the result as a float32 GeoTIFF in EPSG:4326.

    rio-rgbify reprojects to Web Mercator internally; passing a 3857
    source can trigger a PROJ ``densify_pts`` error. Geographic input
    keeps the tile generator happy.
    """
    import numpy as np  # noqa: PLC0415

    dtm = terrain_rgb._open_dtm(spec)
    bathy = terrain_rgb._open_bathy(spec)
    # Build the merge in EPSG:4326 directly so rio-rgbify gets a
    # geographic input it can reproject from.
    merged = terrain_rgb.merge_dtm_bathy(dtm, bathy, aoi=aoi, target_crs="EPSG:4326")
    # rio-rgbify maps NaN to the base value (-10000 m), which would
    # render the sea + out-of-coverage pixels as a deep abyss and put a
    # cliff at the coastline. Fill them with 0 m (sea level) so the
    # terrain stays flat where we have no land data.
    filled = merged.where(np.isfinite(merged), 0.0)
    filled = filled.rio.write_nodata(None)
    filled.rio.to_raster(str(out_path), driver="GTiff", dtype="float32")
    return out_path


def run_rgbify(src: Path, dst: Path, *, max_z: int = 14, min_z: int = 0) -> Path:
    """Shell out to `rio rgbify` to produce PNG-tile MBTiles."""
    cmd = [
        "rio", "rgbify",
        "-b", "-10000",
        "-i", "0.1",
        "--format", "png",
        "--min-z", str(min_z),
        "--max-z", str(max_z),
        str(src), str(dst),
    ]
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tileset-id",
        default="manfredonia-terrain-rgb-v2",
        help="Mapbox tileset id suffix (the part after `<username>.`).",
    )
    parser.add_argument("--max-z", type=int, default=14)
    parser.add_argument("--min-z", type=int, default=0)
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Build the MBTiles but skip the Mapbox upload step.",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    username = os.environ.get("MAPBOX_USERNAME")
    secret = os.environ.get("MAPBOX_SECRET_TOKEN")

    aoi_path = REPO_ROOT / "config" / "aoi.geojson"
    aoi = base.read_aoi_polygon(aoi_path)

    spec = terrain_rgb.DEFAULT_SPEC

    out_mbtiles = REPO_ROOT / "data" / "processed" / "terrain_rgb.mbtiles"
    out_mbtiles.parent.mkdir(parents=True, exist_ok=True)
    out_mbtiles.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as td:
        merged_tif = Path(td) / "terrain_merged.tif"
        print(f"--- merging DTM + bathy → {merged_tif}", flush=True)
        write_merged_float(spec, aoi=aoi, out_path=merged_tif)
        with rasterio.open(merged_tif) as ds:
            print(
                f"    crs={ds.crs} size={ds.width}x{ds.height} dtype={ds.dtypes[0]}",
                flush=True,
            )

        print(f"--- rio rgbify → {out_mbtiles}", flush=True)
        run_rgbify(merged_tif, out_mbtiles, max_z=args.max_z, min_z=args.min_z)

    size = out_mbtiles.stat().st_size
    print(f"    wrote {out_mbtiles}  ({size:,} bytes)", flush=True)

    if args.no_upload:
        print("--- skipping upload (--no-upload)")
        return 0

    if not username or not secret:
        print(
            "ERROR: MAPBOX_USERNAME and MAPBOX_SECRET_TOKEN must be set "
            "(see .env). Skipping upload.",
            file=sys.stderr,
        )
        return 1

    print(f"--- uploading to {username}.{args.tileset_id}", flush=True)
    client = MapboxUploadsClient(username=username, secret_token=secret)
    result = client.publish(
        out_mbtiles,
        tileset_id=args.tileset_id,
        name=args.tileset_id,
    )
    print(
        f"    complete={result.complete} error={result.error} "
        f"progress={result.progress}",
        flush=True,
    )
    print(f"    tileset URL: mapbox://{username}.{result.tileset_id}", flush=True)
    return 0 if result.complete and not result.error else 2


if __name__ == "__main__":
    raise SystemExit(main())
