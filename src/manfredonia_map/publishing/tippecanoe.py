"""Thin wrapper around the ``tippecanoe`` binary.

We use the ``felt/tippecanoe`` fork (vendored by conda-forge as
``tippecanoe``). Flags are pinned for deterministic, Mapbox-friendly
output (per ``docs/research/mapbox.md`` §1):

- ``-zg`` — auto-pick maxzoom from data density.
- ``--drop-densest-as-needed`` — keep individual tiles under Mapbox's
  500 KB per-tile limit.
- ``--extend-zooms-if-still-dropping`` — extend maxzoom when needed.
- ``--coalesce-densest-as-needed`` — coalesce overcrowded features.
- ``--no-tile-stats`` — smaller MBTiles; tile stats live in our catalog.
- ``--force`` — overwrite the output if it already exists.

(``--read-parallel`` is *intentionally omitted*: it splits the input on
newlines for parallel reads, which fragments features in our pretty-
printed GeoJSON outputs. Our biggest layer is ~5 MB, so single-threaded
reading is plenty fast.)

Per-layer name/description/attribution are baked into the MBTiles
header so the tileset carries its own provenance.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def find_tippecanoe(executable: str = "tippecanoe") -> str:
    """Locate the tippecanoe binary; raise a helpful error if missing."""
    found = shutil.which(executable)
    if not found:
        raise FileNotFoundError(
            f"`{executable}` not found in $PATH. Make sure you are running "
            "inside the pixi environment (`pixi shell`) where conda-forge "
            "provides tippecanoe."
        )
    return found


@dataclass(frozen=True)
class TippecanoeBuildSpec:
    """Inputs needed for one ``tippecanoe`` invocation."""

    input_geojson: Path
    output_mbtiles: Path
    layer_name: str
    name: str
    description: str
    attribution: str

    def command(self, tippecanoe_path: str) -> list[str]:
        """Return the argv list that runs this build."""
        return [
            tippecanoe_path,
            "-o", str(self.output_mbtiles),
            "-zg",
            "--drop-densest-as-needed",
            "--extend-zooms-if-still-dropping",
            "--coalesce-densest-as-needed",
            "--no-tile-stats",
            f"--layer={self.layer_name}",
            f"--name={self.name}",
            f"--description={self.description}",
            f"--attribution={self.attribution}",
            "--force",
            str(self.input_geojson),
        ]


def build_mbtiles(spec: TippecanoeBuildSpec, executable: str = "tippecanoe") -> Path:
    """Run ``tippecanoe`` for ``spec`` and return the output path.

    Raises:
        FileNotFoundError: When the input GeoJSON or the tippecanoe
            binary is missing.
        subprocess.CalledProcessError: When tippecanoe exits non-zero.
    """
    if not spec.input_geojson.exists():
        raise FileNotFoundError(f"input GeoJSON not found: {spec.input_geojson}")
    spec.output_mbtiles.parent.mkdir(parents=True, exist_ok=True)
    tippecanoe_path = find_tippecanoe(executable)
    subprocess.run(spec.command(tippecanoe_path), check=True)
    return spec.output_mbtiles
