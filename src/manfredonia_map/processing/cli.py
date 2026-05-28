"""Click subcommands grouped under ``mfd-map process``."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from manfredonia_map.paths import CONFIG_DIR, DATA_INTERIM, DATA_PROCESSED
from manfredonia_map.processing import base, hillshade, mandatory, normalize, raster, terrain_rgb

logger = logging.getLogger(__name__)


@click.group(name="process", help="Process raw acquisitions into data/processed/.")
def process() -> None:
    """Group of processing subcommands."""


def _run_vector(layer_id: str, aoi_path: Path, out_dir: Path) -> Path:
    """Run the standard vector pipeline for one ``layer_id``."""
    if layer_id not in normalize.NORMALIZERS:
        raise click.ClickException(
            f"unknown layer_id={layer_id!r}; known: {sorted(normalize.NORMALIZERS)}"
        )
    spec = normalize.NORMALIZERS[layer_id]
    aoi = base.read_aoi_polygon(aoi_path)
    raw = spec.fn()
    logger.info("normalize(%s): %s", layer_id, base.summarize_json(raw))
    gdf = base.to_storage_crs(raw)
    gdf = base.make_valid(gdf)
    gdf = base.clip_to_aoi(gdf, aoi)
    gdf = base.make_valid(gdf)
    out = out_dir / f"{layer_id}.geojson"
    base.write_layer_geojson(gdf, out)
    logger.info("processed(%s): %s -> %s", layer_id, base.summarize_json(gdf), out)
    click.echo(f"Wrote {out}  {base.summarize_json(gdf)}")
    return out


@process.command(name="vector")
@click.argument("layer_id", type=str)
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
    help="AOI polygon to clip against (default = `aoi.geojson` alias).",
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
def process_vector(layer_id: str, aoi_path: Path, out_dir: Path) -> None:
    """Process one vector layer end-to-end."""
    _run_vector(layer_id, aoi_path, out_dir)


@process.command(name="vectors-all")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--skip",
    "skip_layers",
    multiple=True,
    type=str,
    help="Layer ids to skip (may be repeated).",
)
def process_vectors_all(aoi_path: Path, out_dir: Path, skip_layers: tuple[str, ...]) -> None:
    """Process every registered vector layer."""
    failures: list[tuple[str, str]] = []
    for layer_id in sorted(normalize.NORMALIZERS):
        if layer_id in skip_layers:
            click.echo(f"--- skip {layer_id}")
            continue
        click.echo(f"--- process {layer_id}")
        try:
            _run_vector(layer_id, aoi_path, out_dir)
        except Exception as exc:
            logger.exception("processing %s failed", layer_id)
            failures.append((layer_id, str(exc)))
    if failures:
        msg = "; ".join(f"{lid}: {err}" for lid, err in failures)
        raise click.ClickException(f"processing failed for: {msg}")


@process.command(name="mandatory-features")
@click.option(
    "--processed-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Defaults to ``<processed-dir>/mandatory_for_aoi``.",
)
def process_mandatory_features(processed_dir: Path, out_dir: Path | None) -> None:
    """Promote real perimeters into the AOI builder's mandatory-features set."""
    failures: list[tuple[str, str]] = []
    for spec in mandatory.PROMOTIONS.values():
        click.echo(f"--- promote {spec.feature_id}")
        try:
            out = mandatory.promote(spec, processed_dir=processed_dir, out_dir=out_dir)
            click.echo(f"  wrote {out}")
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("promotion %s failed: %s", spec.feature_id, exc)
            failures.append((spec.feature_id, str(exc)))
    if failures:
        msg = "; ".join(f"{fid}: {err}" for fid, err in failures)
        raise click.ClickException(f"promotion failed for: {msg}")


# --- rasters ----------------------------------------------------------


def _run_raster(
    raster_id: str, aoi_path: Path, interim_dir: Path, processed_dir: Path
) -> tuple[Path, Path]:
    """Run the standard raster pipeline for one ``raster_id``."""
    if raster_id not in raster.PROCESSORS:
        raise click.ClickException(
            f"unknown raster_id={raster_id!r}; known: {sorted(raster.PROCESSORS)}"
        )
    spec = raster.PROCESSORS[raster_id]
    aoi = base.read_aoi_polygon(aoi_path)
    zarr_path, cog_path = raster.process_raster(
        spec,
        aoi,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
    )
    click.echo(f"Wrote {zarr_path}  (analytical Zarr)")
    click.echo(f"Wrote {cog_path}  (8-bit hypsometric COG)")
    return zarr_path, cog_path


@process.command(name="raster")
@click.argument("raster_id", type=str)
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
    help="AOI polygon to clip against (default = ``aoi.geojson`` alias).",
)
@click.option(
    "--interim-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_INTERIM,
    show_default=True,
)
@click.option(
    "--processed-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
def process_raster_cmd(
    raster_id: str, aoi_path: Path, interim_dir: Path, processed_dir: Path
) -> None:
    """Process one raster end-to-end (reproject + clip + 8-bit COG)."""
    _run_raster(raster_id, aoi_path, interim_dir, processed_dir)


@process.command(name="rasters-all")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
)
@click.option(
    "--interim-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_INTERIM,
    show_default=True,
)
@click.option(
    "--processed-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--skip",
    "skip_rasters",
    multiple=True,
    type=str,
    help="Raster ids to skip (may be repeated).",
)
def process_rasters_all(
    aoi_path: Path,
    interim_dir: Path,
    processed_dir: Path,
    skip_rasters: tuple[str, ...],
) -> None:
    """Process every registered raster."""
    failures: list[tuple[str, str]] = []
    for raster_id in sorted(raster.PROCESSORS):
        if raster_id in skip_rasters:
            click.echo(f"--- skip {raster_id}")
            continue
        click.echo(f"--- process raster {raster_id}")
        try:
            _run_raster(raster_id, aoi_path, interim_dir, processed_dir)
        except Exception as exc:
            logger.exception("processing raster %s failed", raster_id)
            failures.append((raster_id, str(exc)))
    if failures:
        msg = "; ".join(f"{rid}: {err}" for rid, err in failures)
        raise click.ClickException(f"raster processing failed for: {msg}")


@process.command(name="hillshade")
@click.argument("raster_id", type=str)
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
)
@click.option(
    "--processed-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--azimuth-deg",
    type=float,
    default=hillshade.DEFAULT_AZIMUTH_DEG,
    show_default=True,
)
@click.option(
    "--altitude-deg",
    type=float,
    default=hillshade.DEFAULT_ALTITUDE_DEG,
    show_default=True,
)
@click.option(
    "--z-factor",
    type=float,
    default=hillshade.DEFAULT_Z_FACTOR,
    show_default=True,
)
def process_hillshade_cmd(
    raster_id: str,
    aoi_path: Path,
    processed_dir: Path,
    azimuth_deg: float,
    altitude_deg: float,
    z_factor: float,
) -> None:
    """Derive a hillshade COG from a registered raster (e.g. ``tinitaly_dtm``)."""
    if raster_id not in raster.PROCESSORS:
        raise click.ClickException(
            f"unknown raster_id={raster_id!r}; known: {sorted(raster.PROCESSORS)}"
        )
    aoi = base.read_aoi_polygon(aoi_path)
    out = hillshade.process_hillshade(
        raster_id,
        aoi,
        processed_dir=processed_dir,
        azimuth_deg=azimuth_deg,
        altitude_deg=altitude_deg,
        z_factor=z_factor,
    )
    click.echo(f"Wrote {out}  (8-bit hillshade COG)")


@process.command(name="terrain-rgb")
@click.option(
    "--aoi",
    "aoi_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=CONFIG_DIR / "aoi.geojson",
    show_default=True,
    help="AOI polygon to clip against (default = ``aoi.geojson`` alias).",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output COG path (default = data/processed/terrain_rgb.tif).",
)
@click.option(
    "--exaggeration",
    type=float,
    default=1.0,
    show_default=True,
    help="Vertical exaggeration baked into the encoded DEM.",
)
def process_terrain_rgb_cmd(
    aoi_path: Path,
    out_path: Path | None,
    exaggeration: float,
) -> None:
    """Build a Mapbox Terrain-RGB COG from the LIDAR DTM + EMODnet bathymetry.

    Upload the resulting file via ``mfd-map publish raster-tileset`` and
    wire it into the webapp via ``map.setTerrain()`` — see
    ``plans/10_3d_basemap.md`` for the runtime snippet.
    """
    spec = terrain_rgb.DEFAULT_SPEC
    if out_path is not None:
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=spec.dtm_zip,
            dtm_inner_filename=spec.dtm_inner_filename,
            bathy_dir=spec.bathy_dir,
            out_path=out_path,
            exaggeration=exaggeration,
        )
    elif exaggeration != 1.0:
        spec = terrain_rgb.TerrainRgbSpec(
            dtm_zip=spec.dtm_zip,
            dtm_inner_filename=spec.dtm_inner_filename,
            bathy_dir=spec.bathy_dir,
            out_path=spec.out_path,
            exaggeration=exaggeration,
        )
    aoi = base.read_aoi_polygon(aoi_path)
    out = terrain_rgb.build_terrain_rgb(spec, aoi=aoi)
    click.echo(f"Wrote {out}  (Mapbox Terrain-RGB COG)")
