"""CLI shim: ``python scripts/build_aoi.py`` ≡ ``mfd-map build-aoi``.

Lets contributors invoke the AOI builder without installing the package's
console script. Both paths share the same underlying Click command.
"""

from __future__ import annotations

from manfredonia_map.aoi.cli import build_aoi

if __name__ == "__main__":
    build_aoi()
