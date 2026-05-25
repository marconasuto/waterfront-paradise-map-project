"""Click subcommands grouped under ``mfd-map catalog``."""

from __future__ import annotations

import logging
from pathlib import Path

import click
from pydantic import ValidationError

from manfredonia_map.catalog import builder
from manfredonia_map.paths import CONFIG_DIR, DATA_DIR, DATA_PROCESSED, DATA_RAW

logger = logging.getLogger(__name__)


@click.group(name="catalog", help="Build / validate data/catalog.yaml.")
def catalog() -> None:
    """Group of catalog subcommands."""


@catalog.command(name="build")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=CONFIG_DIR,
    show_default=True,
)
@click.option(
    "--data-raw",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DATA_RAW,
    show_default=True,
)
@click.option(
    "--processed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DATA_PROCESSED,
    show_default=True,
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DATA_DIR / "catalog.yaml",
    show_default=True,
)
def catalog_build(
    config_dir: Path, data_raw: Path, processed_dir: Path, out_path: Path
) -> None:
    """Walk raw provenance + processed outputs into ``data/catalog.yaml``."""
    cat = builder.assemble(
        config_dir=config_dir,
        data_raw=data_raw,
        processed_dir=processed_dir,
    )
    builder.write(cat, out_path)
    click.echo(
        f"Wrote {out_path}  "
        f"({len(cat.sources)} sources, "
        f"{len(cat.vector_layers)} vector layers, "
        f"{len(cat.raster_layers)} raster layers)"
    )


@catalog.command(name="validate")
@click.argument(
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
)
def catalog_validate(catalog_path: Path | None) -> None:
    """Validate a catalog YAML against the pydantic schema."""
    path = catalog_path or DATA_DIR / "catalog.yaml"
    if not path.exists():
        raise click.ClickException(f"catalog not found: {path}")
    try:
        cat = builder.load(path)
    except ValidationError as exc:
        raise click.ClickException(f"catalog invalid:\n{exc}") from exc
    click.echo(
        f"OK  {path}  "
        f"(v{cat.version}, {len(cat.sources)} sources, "
        f"{len(cat.vector_layers)} vector layers, "
        f"{len(cat.raster_layers)} raster layers)"
    )
