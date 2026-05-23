"""Click subcommands grouped under ``mfd-map acquire``."""

from __future__ import annotations

import logging
from pathlib import Path

import click
import geopandas as gpd

from manfredonia_map.acquisition import base, osm
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


def _persist_osm_layer(
    gdf: gpd.GeoDataFrame,
    out_path: Path,
    *,
    spec: osm.OsmLayerSpec,
    bbox: tuple[float, float, float, float],
) -> base.Provenance:
    """Write the GeoJSON + provenance sidecar for an OSM layer.

    pyogrio (the GeoPandas backend) handles nested-type columns (lists,
    dicts from osmnx) natively, serialising them as JSON arrays / objects
    inside the GeoJSON ``properties``. No manual coercion required.
    """
    if gdf.empty:
        raise click.ClickException(
            f"Overpass returned 0 features for source={spec.source_id} bbox={bbox}."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_path, driver="GeoJSON")
    prov = base.Provenance(
        source_id=spec.source_id,
        publisher="OpenStreetMap contributors",
        dataset=spec.dataset,
        url="https://overpass-api.de/api/interpreter",
        access_method="Overpass via osmnx",
        license="ODbL-1.0",
        accessed_at=base.now_iso_utc(),
        bbox=bbox,
        query={"tags": spec.tags},
    )
    stamped = base.stamp_provenance(prov, out_path)
    base.write_provenance(stamped, out_path.with_suffix(".provenance.json"))
    click.echo(f"Wrote {out_path}  ({len(gdf)} features)")
    return stamped


@acquire.group(name="osm")
def acquire_osm() -> None:
    """Download OSM layers configured in ``osm.LAYERS``."""


def _default_aoi_path() -> Path:
    return CONFIG_DIR / "aoi_buffered.geojson"


def _out_path_for(layer: str) -> Path:
    spec = osm.LAYERS[layer]
    return DATA_RAW / spec.source_id / f"{layer}.geojson"


@acquire_osm.command(name="layer")
@click.argument("layer", type=click.Choice(sorted(osm.LAYERS), case_sensitive=False))
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_aoi_path,
    show_default="config/aoi_buffered.geojson",
    help="GeoJSON whose bounding box defines the Overpass query area.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Destination GeoJSON path. Defaults to data/raw/<source_id>/<layer>.geojson.",
)
def acquire_osm_layer(layer: str, aoi_path: Path, out_path: Path | None) -> None:
    """Fetch a single OSM layer (e.g. ``coastline``, ``roads``, ``wetlands``)."""
    spec = osm.LAYERS[layer]
    out = out_path if out_path is not None else _out_path_for(layer)
    bbox = _bbox_from_aoi(aoi_path)
    logger.info("Fetching OSM layer %s for bbox=%s", layer, bbox)
    gdf = osm.fetch_layer(layer, bbox)
    _persist_osm_layer(gdf, out, spec=spec, bbox=bbox)


@acquire_osm.command(name="all")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=_default_aoi_path,
    show_default="config/aoi_buffered.geojson",
    help="GeoJSON whose bounding box defines the Overpass query area.",
)
@click.option(
    "--skip",
    "skip_layers",
    multiple=True,
    type=click.Choice(sorted(osm.LAYERS), case_sensitive=False),
    help="Layers to skip (may be repeated).",
)
def acquire_osm_all(aoi_path: Path, skip_layers: tuple[str, ...]) -> None:
    """Fetch every OSM layer in ``osm.LAYERS`` sequentially."""
    bbox = _bbox_from_aoi(aoi_path)
    failures: list[str] = []
    for layer in sorted(osm.LAYERS):
        if layer in skip_layers:
            click.echo(f"--- skip osm:{layer}")
            continue
        click.echo(f"--- acquire osm:{layer}")
        try:
            spec = osm.LAYERS[layer]
            out = _out_path_for(layer)
            gdf = osm.fetch_layer(layer, bbox)
            _persist_osm_layer(gdf, out, spec=spec, bbox=bbox)
        except click.ClickException as exc:
            logger.warning("osm:%s failed: %s", layer, exc.message)
            failures.append(layer)
    if failures:
        raise click.ClickException(f"acquisitions failed: {', '.join(failures)}")
