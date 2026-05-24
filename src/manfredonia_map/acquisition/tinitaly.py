"""INGV TINITALY DEM acquisition.

TINITALY/1.1 is a 10 m-cell-size DEM covering all of Italy, distributed by
INGV under CC BY 4.0. The dataset is split into ~193 zipped tiles (~50 km
side, ~96 MB each, ~38 MB for partial-coverage tiles) at

``https://tinitaly.pi.ingv.it/data/<tile_id>/<tile_id>.zip``

Each tile zip contains a single GeoTIFF in EPSG:32632 (WGS84 / UTM 32N)
plus accompanying metadata. The pipeline downloads the zip verbatim;
Phase 4 processing reads the GeoTIFF via ``rioxarray``, reprojects to our
working CRS (EPSG:32633), clips to the AOI, and produces a colormapped
8-bit COG for Mapbox raster tilesets.

Tile naming scheme decoded empirically (the public docs don't spell it
out): ``<dir><NN><EEE>_s<RR>`` where

- ``dir`` is ``e`` for the extended-UTM-32N eastern band (easting >= 1000
  km) and ``w`` for the standard zone (easting < 1000 km).
- ``NN`` is the SW corner northing divided by 100 km (e.g. ``46`` =>
  N 4_600 km).
- ``EEE`` is the SW corner easting **minus 1000 km** divided by 10 km
  (zero-padded). For ``e46005`` => 5 => easting = 1000 + 5*10 = 1050 km.
- ``RR`` is the cell resolution in metres (``s10`` = 10 m).

Tiles are 50 km tall x variable width (50 km nominally, less along
coastal edges).

For the Manfredonia AOI tile **``e46005_s10``** (~130 MB) covers
everything: native bounds (1_049_950, 4_599_950, 1_115_050, 4_650_050)
in EPSG:32632, bbox 15.57E-16.40E x 41.32N-41.81N in EPSG:4326,
shape 5_010 x 6_510, ``float32``.

**Note on TLS**: ``tinitaly.pi.ingv.it`` ships a cert chain Python's
default CA bundle does not verify. The CLI defaults to
``--no-verify-ssl`` for this source; pin with ``--expected-sha256`` in
CI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TinitalyTileSpec:
    """Static spec for one TINITALY/1.1 tile."""

    tile_id: str

    @property
    def url(self) -> str:
        """Return the canonical zip URL for this tile."""
        return f"https://tinitaly.pi.ingv.it/data/{self.tile_id}/{self.tile_id}.zip"

    @property
    def out_filename(self) -> str:
        """Suggested filename under ``data/raw/tinitaly/``."""
        return f"{self.tile_id}.zip"

    @property
    def source_id(self) -> str:
        """Catalog source identifier for the provenance record."""
        return f"tinitaly_1_1_{self.tile_id}"

    @property
    def dataset(self) -> str:
        """Human-readable dataset name for the provenance record."""
        return f"INGV TINITALY/1.1 DEM — tile {self.tile_id}"
