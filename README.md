# Manfredonia Coastal Map

Multi-layer geospatial map and Mapbox storymap for the Manfredonia coast
(Puglia, Italy).

> 📜 **The authoritative document is [`SPECIFICATIONS.md`](./SPECIFICATIONS.md).**
> Read it first. Plans live in [`plans/`](./plans/); research notes in
> [`docs/research/`](./docs/research/).

## Quick links

- Living spec: [`SPECIFICATIONS.md`](./SPECIFICATIONS.md)
- Master plan: [`plans/00_overview.md`](./plans/00_overview.md)
- Change log: [`CHANGELOG.md`](./CHANGELOG.md)

## Status

Pre-research (v0.1). No code yet — we are in the data-source & tooling
research phase. See `plans/00_overview.md` → Phase 1.

## Local setup

```bash
# Install pixi (https://pixi.sh) if you don't have it:
#   curl -fsSL https://pixi.sh/install.sh | bash

# Bring up the locked Python + native environment:
pixi install

# Open a shell with the dev environment active:
pixi shell -e dev

# Environment variables (gitignored):
cp .env.example .env
# fill in MAPBOX_SECRET_TOKEN (sk.*), MAPBOX_PUBLIC_TOKEN (pk.*), MAPBOX_USERNAME

# Run common tasks via pixi:
pixi run lint          # ruff check
pixi run typecheck     # mypy --strict
pixi run test-cov      # pytest with 95% coverage gate
pixi run all           # lint + typecheck + tests
```

The stack:
- **pixi** (conda-forge for native binaries: GDAL, PROJ, GEOS, tippecanoe, netcdf)
- **geopandas / pyogrio / shapely / pyproj** for vector data
- **xarray + zarr + rioxarray + dask** for raster data
- **mapbox-gl-js v3** + a custom slide engine for the storymap (in `webapp/`)
