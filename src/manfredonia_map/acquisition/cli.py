"""Click subcommands grouped under ``mfd-map acquire <thing>``."""

from __future__ import annotations

import logging
from pathlib import Path

import click
import geopandas as gpd

from manfredonia_map.acquisition import base, osm
from manfredonia_map.aoi import io as aoi_io
from manfredonia_map.paths import CONFIG_DIR, DATA_RAW

logger = logging.getLogger(__name__)


@click.group(name="acquire", help="Download raw data into data/raw/.")
def acquire() -> None:
    """Group of acquisition subcommands."""


def _bbox_from_aoi(aoi_path: Path) -> tuple[float, float, float, float]:
    """Return ``(west, south, east, north)`` from a single-feature GeoJSON."""
    gdf = gpd.read_file(aoi_path)
    minx, miny, maxx, maxy = gdf.total_bounds
    return (float(minx), float(miny), float(maxx), float(maxy))


@acquire.command(name="coastline")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi_buffered.geojson",
    show_default=True,
    help="GeoJSON whose bounding box defines the Overpass query area.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DATA_RAW / "coastline" / "coastline.geojson",
    show_default=True,
    help="Destination for the raw coastline GeoJSON.",
)
def acquire_coastline(aoi_path: Path, out_path: Path) -> None:
    """Fetch OSM ``natural=coastline`` for the AOI bbox via Overpass."""
    bbox = _bbox_from_aoi(aoi_path)
    logger.info("Fetching coastline for bbox=%s", bbox)
    gdf = osm.fetch_coastline(bbox)
    if gdf.empty:
        raise click.ClickException(f"Overpass returned 0 coastline features for bbox={bbox}.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Write GeoJSON via geopandas (deterministic enough for raw artifacts;
    # downstream processing always re-reads and never compares bytes).
    gdf[["geometry"]].to_file(out_path, driver="GeoJSON")

    prov = base.Provenance(
        source_id="osm_coastline",
        publisher="OpenStreetMap contributors",
        dataset="OSM natural=coastline",
        url="https://overpass-api.de/api/interpreter",
        access_method="Overpass via osmnx",
        license="ODbL-1.0",
        accessed_at=base.now_iso_utc(),
        bbox=bbox,
        query={"tags": {"natural": "coastline"}},
    )
    prov = base.stamp_provenance(prov, out_path)
    base.write_provenance(prov, out_path.with_suffix(".provenance.json"))

    # And give the AOI builder what it needs (it reads as a unioned geometry).
    geom, _ = aoi_io.read_geometry_geojson(out_path)
    click.echo(f"Wrote {out_path}  ({len(gdf)} features, geom.length≈{geom.length:.4f}°)")
    click.echo(f"Wrote {out_path.with_suffix('.provenance.json')}")
