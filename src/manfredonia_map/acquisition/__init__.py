"""Data-acquisition layer.

Each submodule owns one source family (OSM, ISPRA, MASE, MiC, …). Every
downloader is structured so it can be unit-tested without network access:
the actual HTTP / Overpass call is performed by a small injectable
``fetcher`` callable that tests override.

Output convention:
- Raw artifact → ``data/raw/<source>/<layer>.<ext>``.
- Sidecar provenance → ``data/raw/<source>/<layer>.provenance.json``.
"""

from manfredonia_map.acquisition import (
    base,
    emodnet,
    http,
    ispra,
    istat,
    mase,
    osm,
    regione_puglia,
    tinitaly,
    vir,
)

__all__ = [
    "base",
    "emodnet",
    "http",
    "ispra",
    "istat",
    "mase",
    "osm",
    "regione_puglia",
    "tinitaly",
    "vir",
]
