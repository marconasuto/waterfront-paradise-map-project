"""Click command implementing ``mfd-map build-aoi``.

Reads the source polygon (and, when available, the coastline + mandatory
features) and writes ``aoi_buffered.geojson``, ``aoi_near_coast.geojson``,
and the ``aoi.geojson`` alias. Hard-fails on sanity-check failure when
enough inputs are present to make the assertions meaningful.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
import yaml
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from manfredonia_map.aoi import builder, io, sanity
from manfredonia_map.paths import CONFIG_DIR, DATA_PROCESSED, DATA_RAW

logger = logging.getLogger(__name__)


def _load_mandatory_features(directory: Path) -> list[BaseGeometry]:
    """Load every ``*.geojson`` file under ``directory`` as a list of geoms."""
    if not directory.exists():
        return []
    geoms: list[BaseGeometry] = []
    for fp in sorted(directory.glob("*.geojson")):
        geom, _ = io.read_geometry_geojson(fp)
        geoms.append(geom)
        logger.info("Loaded mandatory feature from %s", fp.name)
    return geoms


def _load_mandatory_points(points_yaml: Path) -> list[BaseGeometry]:
    """Load buffered points from ``mandatory_locations.yaml``.

    Each entry ``{lon, lat, buffer_m}`` becomes a single buffered polygon in
    EPSG:4326 (buffer computed in EPSG:32633). Returns an empty list if the
    file does not exist or has no entries.
    """
    if not points_yaml.exists():
        return []
    data = yaml.safe_load(points_yaml.read_text(encoding="utf-8")) or {}
    geoms: list[BaseGeometry] = []
    for entry in data.get("locations") or []:
        point = Point(entry["lon"], entry["lat"])
        buffered = builder.build_coastal_band(point, "EPSG:4326", band_m=entry["buffer_m"])
        if buffered is not None and not buffered.is_empty:
            geoms.append(buffered)
            logger.info(
                "Loaded mandatory point: %s (buffer %s m)",
                entry["id"],
                entry["buffer_m"],
            )
    return geoms


@click.command(name="build-aoi")
@click.option(
    "--source",
    "source_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi_source.geojson",
    show_default=True,
    help="Source polygon (single-feature GeoJSON).",
)
@click.option(
    "--coastline",
    "coastline_path",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    default=DATA_RAW / "coastline" / "coastline.geojson",
    show_default=True,
    help="Coastline geometry. Optional; if missing, the near-coast AOI "
    "falls back to ``aoi_buffered`` with a warning.",
)
@click.option(
    "--mandatory-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED / "mandatory_for_aoi",
    show_default=True,
    help="Directory whose ``*.geojson`` files are unioned into the "
    "mandatory-features inclusion set (SIN, Lago Salso, ...).",
)
@click.option(
    "--mandatory-points",
    "mandatory_points_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "mandatory_locations.yaml",
    show_default=True,
    help="YAML of {lon, lat, buffer_m} entries; each is buffered and "
    "added to the mandatory-features set. Falls back gracefully if missing.",
)
@click.option("--buffer-m", type=float, default=1000.0, show_default=True)
@click.option("--coastal-band-m", type=float, default=2000.0, show_default=True)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=CONFIG_DIR,
    show_default=True,
    help="Directory to write the three GeoJSON outputs into.",
)
@click.option(
    "--alias",
    type=click.Choice(["near_coast", "buffered"]),
    default="near_coast",
    show_default=True,
    help="Which shape ``aoi.geojson`` should alias (OPEN-AOI-3).",
)
def build_aoi(
    source_path: Path,
    coastline_path: Path,
    mandatory_dir: Path,
    mandatory_points_path: Path,
    buffer_m: float,
    coastal_band_m: float,
    out_dir: Path,
    alias: str,
) -> None:
    """Compute the two AOI shapes and write them to ``out_dir``."""
    source_geom, source_crs = io.read_polygon_geojson(source_path)
    logger.info("Source polygon loaded (crs=%s)", source_crs)

    aoi_buffered = builder.build_buffered_aoi(source_geom, source_crs, buffer_m=buffer_m)

    coastline_geom: BaseGeometry | None = None
    coastline_crs: str | None = None
    if coastline_path.exists():
        coastline_geom, coastline_crs = io.read_geometry_geojson(coastline_path)
        logger.info("Coastline loaded from %s", coastline_path)
    else:
        logger.warning(
            "Coastline not found at %s — near-coast AOI will fall back to buffered.",
            coastline_path,
        )

    coastal_band = builder.build_coastal_band(coastline_geom, coastline_crs, band_m=coastal_band_m)
    mandatory = _load_mandatory_features(mandatory_dir) + _load_mandatory_points(
        mandatory_points_path
    )
    if not mandatory:
        logger.warning(
            "No mandatory features in %s and no points in %s — SIN / wetlands / "
            "Grotta Scaloria guarantees not enforced. Add some, or wait for "
            "Phase 3 acquisition.",
            mandatory_dir,
            mandatory_points_path,
        )

    near_coast = builder.build_near_coast_aoi(aoi_buffered, coastal_band, mandatory)

    if not aoi_buffered.contains(near_coast):
        extension_area = near_coast.difference(aoi_buffered).area
        logger.warning(
            "Near-coast AOI extends beyond aoi_buffered by ~%.6f deg^2 — some "
            "mandatory features sit outside the source polygon's 1 km buffer. "
            "Consider revising config/aoi_source.geojson to encompass them.",
            extension_area,
        )

    sanity_results = sanity.run_checks(near_coast)
    failed = sorted(k for k, v in sanity_results.items() if not v)
    enough_inputs = coastal_band is not None or bool(mandatory)
    if failed and enough_inputs:
        raise click.ClickException(
            "AOI sanity checks failed: "
            + ", ".join(failed)
            + ". Inspect inputs or expand mandatory features."
        )
    if failed:
        logger.warning("AOI sanity checks skipped (insufficient inputs): %s", failed)

    out_dir.mkdir(parents=True, exist_ok=True)
    io.write_aoi_geojson(
        aoi_buffered,
        out_dir / "aoi_buffered.geojson",
        name="aoi_buffered",
        properties={
            "description": "Source polygon buffered by buffer_m on both sides.",
            "buffer_m": buffer_m,
            "buffer_crs": "EPSG:32633",
        },
    )
    io.write_aoi_geojson(
        near_coast,
        out_dir / "aoi_near_coast.geojson",
        name="aoi_near_coast",
        properties={
            "description": (
                "aoi_buffered intersected with the union of the coastal band "
                "and the mandatory features."
            ),
            "coastal_band_m": coastal_band_m,
            "coastal_band_present": coastal_band is not None,
            "mandatory_feature_count": len(mandatory),
            "sanity_results": sanity_results,
        },
    )
    alias_geom = near_coast if alias == "near_coast" else aoi_buffered
    io.write_aoi_geojson(
        alias_geom,
        out_dir / "aoi.geojson",
        name=f"aoi (alias -> {alias})",
        properties={"alias_target": alias},
    )

    click.echo(f"Wrote {out_dir / 'aoi_buffered.geojson'}")
    click.echo(f"Wrote {out_dir / 'aoi_near_coast.geojson'}")
    click.echo(f"Wrote {out_dir / 'aoi.geojson'}  (alias -> {alias})")
