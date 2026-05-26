"""Click subcommands grouped under ``mfd-map publish``."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import click

from manfredonia_map.catalog import builder as catalog_builder
from manfredonia_map.paths import DATA_DIR, DATA_PROCESSED
from manfredonia_map.publishing import manifest as manifest_mod
from manfredonia_map.publishing import settings as settings_mod
from manfredonia_map.publishing import tippecanoe as tippecanoe_mod

logger = logging.getLogger(__name__)


@click.group(name="publish", help="Prepare and upload tilesets to Mapbox.")
def publish() -> None:
    """Group of publishing subcommands."""


def _build_one_layer(
    layer_id: str,
    *,
    processed_dir: Path,
    mbtiles_dir: Path,
    catalog: catalog_builder.models.Catalog,
) -> Path:
    """Run tippecanoe for one layer; return the MBTiles path."""
    geojson = processed_dir / f"{layer_id}.geojson"
    src = next(
        (s for vl in catalog.vector_layers if vl.layer_id == layer_id
         for s in catalog.sources if s.source_id == vl.source_id),
        None,
    )
    spec = tippecanoe_mod.TippecanoeBuildSpec(
        input_geojson=geojson,
        output_mbtiles=mbtiles_dir / f"{layer_id}.mbtiles",
        layer_name=layer_id,
        name=f"Manfredonia coastal map — {layer_id}",
        description=(
            f"Source: {src.dataset} ({src.publisher})." if src else f"Layer {layer_id}."
        ),
        attribution=(
            f"{src.publisher}. License: {src.license}." if src else "Manfredonia map."
        ),
    )
    return tippecanoe_mod.build_mbtiles(spec)


@publish.command(name="prepare-mbtiles")
@click.option(
    "--processed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--mbtiles-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to write the MBTiles. Defaults to data/processed/mbtiles/.",
)
@click.option(
    "--only",
    "only_layers",
    multiple=True,
    type=str,
    help="Restrict to specific layer ids (may be repeated).",
)
@click.option(
    "--skip",
    "skip_layers",
    multiple=True,
    type=str,
    help="Layer ids to skip (may be repeated).",
)
def publish_prepare_mbtiles(
    processed_dir: Path,
    mbtiles_dir: Path | None,
    only_layers: tuple[str, ...],
    skip_layers: tuple[str, ...],
) -> None:
    """Run tippecanoe for every vector layer that has features."""
    catalog = catalog_builder.assemble(processed_dir=processed_dir)
    mb_dir = mbtiles_dir or manifest_mod.default_mbtiles_dir(processed_dir)
    failures: list[tuple[str, str]] = []
    for vl in catalog.vector_layers:
        if vl.feature_count == 0:
            click.echo(f"--- skip {vl.layer_id}  (no features)")
            continue
        if only_layers and vl.layer_id not in only_layers:
            continue
        if vl.layer_id in skip_layers:
            click.echo(f"--- skip {vl.layer_id}  (--skip)")
            continue
        click.echo(f"--- mbtiles {vl.layer_id}")
        try:
            out = _build_one_layer(
                vl.layer_id, processed_dir=processed_dir,
                mbtiles_dir=mb_dir, catalog=catalog,
            )
            click.echo(f"  wrote {out}")
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            logger.warning("tippecanoe %s failed: %s", vl.layer_id, exc)
            failures.append((vl.layer_id, str(exc)))
    if failures:
        msg = "; ".join(f"{lid}: {err}" for lid, err in failures)
        raise click.ClickException(f"tippecanoe failed for: {msg}")


@publish.command(name="manifest")
@click.option(
    "--processed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--mbtiles-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to read the MBTiles from. Defaults to data/processed/mbtiles/.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DATA_DIR / "publish_manifest.yaml",
    show_default=True,
)
def publish_manifest(
    processed_dir: Path, mbtiles_dir: Path | None, out_path: Path,
) -> None:
    """Walk the catalog + MBTiles + COGs into ``data/publish_manifest.yaml``."""
    cat = catalog_builder.assemble(processed_dir=processed_dir)
    s = settings_mod.MapboxSettings()
    entries = manifest_mod.build_and_write(
        cat,
        username=s.username,
        mbtiles_dir=mbtiles_dir,
        processed_dir=processed_dir,
        out_path=out_path,
    )
    vec = sum(1 for e in entries if e.layer_type == "vector")
    ras = sum(1 for e in entries if e.layer_type == "raster")
    click.echo(f"Wrote {out_path}  ({vec} vector + {ras} raster entries)")


@publish.command(name="prepare")
@click.pass_context
def publish_prepare(ctx: click.Context) -> None:
    """Run ``prepare-mbtiles`` then ``manifest`` end-to-end."""
    ctx.invoke(publish_prepare_mbtiles)
    ctx.invoke(publish_manifest)
