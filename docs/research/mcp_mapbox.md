# Research — MCP servers for Mapbox / geospatial

> Findings from 2026-05-23. Conclusions fold back into `SPECIFICATIONS.md`
> §15 and `plans/07_mcp_hooks.md`.

## TL;DR

**There is an official Mapbox MCP server.** It exposes Mapbox's
location-intelligence APIs (geocoding, search, routing, isochrone, static
maps) as MCP tools. There is also a separate **Mapbox DevKit MCP server**
for AI coding agents (build/preview/upload/style management) and a
**mapbox/mcp-docs-server** for Mapbox documentation Q&A.

This changes the design of our `src/manfredonia_map/mcp/` from "hypothetical
hook for some future server" to "shaped to compose alongside the official
Mapbox server". The post-v1 path is now clear and short.

---

## 1. Is there an official Mapbox MCP server in 2025-2026?

**Yes.** Two distinct official servers + one docs server:

| Server                  | Repo                                                 | Focus                                              |
|-------------------------|------------------------------------------------------|----------------------------------------------------|
| **Mapbox MCP Server**   | <https://github.com/mapbox/mcp-server>               | Mapbox location-intelligence APIs as MCP tools     |
| **Mapbox DevKit MCP**   | <https://github.com/mapbox/mcp-server> (docs/devkit) | Coding-agent helpers (tokens, styles, tilesets)    |
| **Mapbox Docs MCP**     | <https://github.com/mapbox/mcp-docs-server>          | Q&A over Mapbox documentation                      |

Reference posts:
- [Introducing the Mapbox MCP Server](https://www.mapbox.com/blog/introducing-the-mapbox-model-context-protocol-mcp-server)
- [Building with AI Agents: Mapbox DevKit MCP at BUILD 2025](https://www.mapbox.com/blog/how-the-mapbox-devkit-mcp-server-enhances-ai-coding-workflows)
- [MCP Server API guide](https://docs.mapbox.com/api/guides/mcp-server/)
- [DevKit MCP Server API guide](https://docs.mapbox.com/api/guides/devkit-mcp-server/)

### Tools exposed by the Mapbox MCP Server (location intelligence)

1. **Geocoding** — forward / reverse using Mapbox Geocoding v6.
2. **Search Box — text search** — POIs, addresses, places.
3. **Search Box — category search** — POIs by category (restaurants, hotels…).
4. **Directions** — driving (with traffic), walking, cycling; 2–25 waypoints.
5. **Matrix** — many-to-many travel times / distances.
6. **Static Map** — generate static images from style + camera.
7. **Isochrone** — reachable polygons by travel time and mode.

### Transport / install (Claude Desktop)

Standard MCP stdio transport. Configuration block:

```json
{
  "mcpServers": {
    "MapboxServer": {
      "command": "npx",
      "args": ["-y", "@mapbox/mcp-server"],
      "env": {
        "MAPBOX_ACCESS_TOKEN": "<your token>"
      }
    }
  }
}
```

Refs:
- [Claude Desktop setup](https://github.com/mapbox/mcp-server/blob/main/docs/claude-desktop-setup.md)
- [Hosted MCP guide](https://github.com/mapbox/mcp-server/blob/main/docs/hosted-mcp-guide.md)
- [Getting Started with Local MCP Servers on Claude Desktop](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

### Auth model

`MAPBOX_ACCESS_TOKEN` env var; **a public `pk.…` token is enough** for the
read-only tools (geocoding, directions, isochrone). Use a separate secret
token only if the MCP host is ever asked to manage tilesets / styles
(DevKit territory).

### Maturity

- **License:** check repo (BSD/MIT-style; verify before fork).
- **Active:** referenced in Mapbox BUILD 2025; Mapbox blog posts in
  2025–2026; Docker image at <https://hub.docker.com/r/mcp/mapbox>.

## 2. Community geospatial MCP servers

| Server                                                                     | Scope                                              | Notes                                  |
|----------------------------------------------------------------------------|----------------------------------------------------|----------------------------------------|
| <https://github.com/leependu/mapbox-mcp>                                   | Mapbox APIs                                        | Pre-official community alternative.     |
| <https://github.com/windsornguyen/mapbox-mcp>                              | Mapbox web services                                | Lightweight wrapper.                    |
| <https://github.com/AidenYangX/mapbox-mcp-server>                          | Mapbox API                                         | Smaller scope.                          |

For broader geospatial work (GDAL, PostGIS, QGIS, PMTiles) the registry on
<https://mcpservers.org/> is the right place to scan — the ecosystem is
fragmented and changes monthly. For our project we don't need any of
these in v1.

## 3. Mapbox APIs most useful via MCP for our use cases

| Use case            | Why                                                                 | Suggested MCP tools                                     |
|---------------------|---------------------------------------------------------------------|---------------------------------------------------------|
| Museum kiosk        | "What is at this point on the map?" + Italian content lookup        | `geocode_reverse`, our `get_feature_at`, `get_location` |
| Urban planning      | "Show wetlands within 500 m of the SIN site"                        | our `clip_to_polygon`, `summarize_layer_in_polygon`     |
| Citizen science     | "Submit this observation as a point"                                | our `submit_observation`; Mapbox `geocode_forward` for placename → coord |

Mapbox's official server gives us the geocoding/directions/static-map
slice for free. **Our MCP layer should add the *project-specific* tools
(layer catalog, location content, AOI clipping) that the Mapbox server
cannot provide.**

## 4. Design pressure for our v1 stubs

We will **only define dataclasses and bridging functions** in v1 — no MCP
library import. The shape below is JSON-Schema-flavored and corresponds
directly to MCP tools.

```python
# src/manfredonia_map/mcp/protocol.py (sketch, v1)

from dataclasses import dataclass
from typing import Any

# --- tool: list_layers ---
@dataclass(frozen=True)
class ListLayersInput: pass

@dataclass(frozen=True)
class LayerSummary:
    id: str
    title_it: str
    geometry_type: str
    year_data: int
    source: str
    tileset_id: str | None

@dataclass(frozen=True)
class ListLayersOutput:
    layers: list[LayerSummary]

# --- tool: get_layer ---
@dataclass(frozen=True)
class GetLayerInput:
    id: str

# --- tool: get_feature_at ---
@dataclass(frozen=True)
class GetFeatureAtInput:
    lat: float
    lon: float
    layers: list[str] | None = None   # default: all interactive layers

@dataclass(frozen=True)
class FeatureMatch:
    layer_id: str
    feature_id: str
    properties: dict[str, Any]
    distance_m: float

@dataclass(frozen=True)
class GetFeatureAtOutput:
    matches: list[FeatureMatch]

# --- tool: list_locations ---
@dataclass(frozen=True)
class ListLocationsInput: pass

@dataclass(frozen=True)
class LocationSummary:
    id: str
    name_it: str
    category: str
    coord: tuple[float, float]

@dataclass(frozen=True)
class ListLocationsOutput:
    locations: list[LocationSummary]

# --- tool: get_location ---
@dataclass(frozen=True)
class GetLocationInput:
    id: str

@dataclass(frozen=True)
class GetLocationOutput:
    id: str
    name_it: str
    description_it: str
    coord: tuple[float, float]
    sources: list[str]
    media: list[dict[str, str]]

# --- tool: clip_to_polygon ---  (URBAN-PLANNING use case)
@dataclass(frozen=True)
class ClipToPolygonInput:
    layer: str
    polygon_geojson: dict[str, Any]

@dataclass(frozen=True)
class ClipToPolygonOutput:
    feature_count: int
    geojson: dict[str, Any]

# --- tool: summarize_layer_in_polygon ---
@dataclass(frozen=True)
class SummarizeLayerInPolygonInput:
    layer: str
    polygon_geojson: dict[str, Any]

@dataclass(frozen=True)
class SummarizeLayerInPolygonOutput:
    feature_count: int
    total_length_m: float | None    # for line layers
    total_area_m2: float | None     # for polygon layers
    by_category: dict[str, int]
```

Bridging functions in `bridges.py` map each `*Input` → `*Output` by
calling the catalog/content APIs (no MCP imports). When we add an MCP
server later, `server.py` will import the `mcp` library and register one
handler per dataclass pair. The bridges remain pure and unit-testable.

### Walkthrough — museum-kiosk turn

1. User taps screen at lat/lon. Front-end calls Claude via MCP host.
2. Claude calls `get_feature_at(lat, lon)` (ours).
3. Claude calls `get_location(id)` for the matched feature (ours).
4. Claude calls Mapbox `static_map` (official) to embed an image in the reply.
5. Claude replies in Italian, citing the publisher and year from the layer.

The fact that the official Mapbox server already provides step 4 is
exactly why our stubs must coexist with it cleanly — we should not
re-implement static maps, reverse geocoding, or routing on our side.

## 5. Recommended path post-v1

- **Library**: [`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP-style) — official and stable.
- **Transport**:
  - **stdio** for Claude Desktop and Claude Code local use.
  - **Streamable HTTP** if we ever expose the server to a web app (e.g., the
    museum kiosk's tablet calling back to a small Python service).
- **Composition**: ship our server *alongside* the official Mapbox MCP
  server in the host's config. Claude can call tools from both.
- **Estimated effort to ship our MCP server** in v1.1: **~2–3 person-days**
  for a senior engineer (server module + smoke tests + Claude Desktop
  config docs), assuming the v1 catalog/content APIs and bridging
  functions already exist.

---

## Folded-back updates to `SPECIFICATIONS.md`

- §15 — replace "we will design hooks for an undefined future server" with
  "we design hooks to compose with the official Mapbox MCP server; our v1
  stubs are dataclasses; a v1.1 server takes 2–3 days using the official
  Python MCP SDK."
- §18 — close **OPEN-MCP-1**: target the official Mapbox MCP server
  (<https://github.com/mapbox/mcp-server>) as the companion; our server
  provides project-specific layer/content/AOI tools.
