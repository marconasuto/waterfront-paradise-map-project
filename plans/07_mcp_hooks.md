# Subplan — MCP hooks (design now, build later)

> Owns `src/manfredonia_map/mcp/` (v1: stubs only). Research deliverable
> lives in `docs/research/mcp_mapbox.md`.

## Research

- [ ] Inventory MCP servers relevant to Mapbox / geospatial:
  - Any **official Mapbox MCP server** (if released).
  - Community servers (search for "mcp mapbox", "mcp gis", "mcp gdal").
  - Anthropic-published examples.
- [ ] For each, note: scope of tools, transport (stdio/http), auth model,
      maturity.
- [ ] Identify which **Mapbox APIs** are most useful to expose via MCP
      (Geocoding, Directions, Tilesets, Datasets, Static Images, Style API).
- [ ] Map our v1 use cases (museum, urban planning, citizen science) to
      the smallest set of MCP tools we would expose later.

## v1 design (stubs only, no transport)

```
src/manfredonia_map/mcp/
    __init__.py
    protocol.py     ← typed dataclasses for tool inputs/outputs
    bridges.py      ← pure functions that adapt catalog/content APIs to
                       MCP-shaped dicts (no MCP library import)
    README.md       ← how to add a real MCP server in a later release
```

Design rules:
- No new dependency on any MCP library in v1.
- All bridging logic is pure Python and reuses the public APIs of
  `catalog/` and `content/`.
- A future PR adds one file (`server.py`) that imports the MCP library and
  wires the existing bridges to it.

## v1 use-case sketches (for design pressure, not delivery)

- [ ] **Museum kiosk**: tools `list_locations()`, `get_location(id)`,
      `list_layers()`, `get_feature_at(lat,lon)`.
- [ ] **Urban planning**: tools above + `clip_to_polygon(geojson)`,
      `summarize_layer_in_polygon(layer, geojson)`.
- [ ] **Citizen science**: a write path `submit_observation(geojson, lang)`
      that lands in a moderation queue, plus moderator tooling. Out of scope
      for v1; ensure the catalog write path is at least pluggable.

## Acceptance (v1)

- [ ] Stub modules compile, are documented, and are not exposed in
      `mfd-map`.
- [ ] `docs/research/mcp_mapbox.md` documents the post-v1 path with file
      paths and a concrete API surface.
