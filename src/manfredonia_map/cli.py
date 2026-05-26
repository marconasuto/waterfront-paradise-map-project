"""Top-level Click CLI for the Manfredonia coastal map pipeline.

Subcommands are imported lazily so the CLI starts fast even when heavy
dependencies (``geopandas``, ``rasterio``) are present.
"""

from __future__ import annotations

import logging

import click

from manfredonia_map import __version__


@click.group(name="mfd-map", help="Manfredonia coastal map pipeline.")
@click.version_option(__version__)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase logging verbosity (-v INFO, -vv DEBUG).",
)
def main(verbose: int) -> None:
    """Configure root logging and dispatch to a subcommand."""
    level = logging.WARNING - 10 * verbose
    logging.basicConfig(
        level=max(level, logging.DEBUG),
        format="%(levelname)s %(name)s: %(message)s",
    )


# --- subcommand wiring (kept light so importing this module is cheap) ---

from manfredonia_map.acquisition.cli import acquire as _acquire  # noqa: E402
from manfredonia_map.aoi.cli import build_aoi as _build_aoi  # noqa: E402
from manfredonia_map.catalog.cli import catalog as _catalog  # noqa: E402
from manfredonia_map.processing.cli import process as _process  # noqa: E402
from manfredonia_map.publishing.cli import publish as _publish  # noqa: E402

main.add_command(_build_aoi, name="build-aoi")
main.add_command(_acquire, name="acquire")
main.add_command(_process, name="process")
main.add_command(_catalog, name="catalog")
main.add_command(_publish, name="publish")
