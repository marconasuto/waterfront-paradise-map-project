import type { Map as MapboxMap } from "mapbox-gl";

import type { BasemapEntry } from "../types";

/**
 * Minimal Mapbox map surface used by `applyBasemapCamera` / `applyBasemapTerrain`.
 *
 * We deliberately don't depend on the full `Map` type so these helpers
 * stay easy to mock in unit tests — they only need the methods they
 * actually call.
 */
export interface MapCameraSurface {
  setPitch?: (pitch: number) => void;
  getPitch?: () => number;
}

/**
 * The `addSource` parameter is intentionally typed permissively
 * (`Parameters<...>[1]`) so this surface accepts the real Mapbox
 * `Map`'s narrower SourceSpecification union without a cast.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySource = any;

export interface MapTerrainSurface {
  getSource?: (id: string) => unknown;
  addSource?: (id: string, source: AnySource) => unknown;
  setTerrain?: (terrain: { source: string; exaggeration?: number } | null) => unknown;
}

/**
 * The Mapbox public Terrain-RGB v1 tileset. Standard already enables
 * terrain internally; for plain styles like outdoors/satellite we have
 * to add this source ourselves before calling `setTerrain`.
 */
export const MAPBOX_DEM_SOURCE_ID = "mapbox-dem";
/** Distinct id for a basemap-provided custom DEM (e.g. our LIDAR one). */
export const CUSTOM_DEM_SOURCE_ID = "custom-dem";
const MAPBOX_DEM_TILESET = "mapbox://mapbox.mapbox-terrain-dem-v1";
const DEFAULT_TERRAIN_EXAGGERATION = 1.3;

/** rio-rgbify writes 256 px tiles; our LIDAR tileset maxes at z13. */
const CUSTOM_DEM_TILE_SIZE = 256;
const CUSTOM_DEM_MAXZOOM = 13;

/**
 * Build the explicit raster-dem `tiles` URL for a custom Mapbox tileset.
 *
 * Why not just `url: "mapbox://…"`? Because GL JS then resolves the
 * tileset's TileJSON and fetches the **`.png`** endpoint, which is
 * Mapbox's palette-quantised (≤256-colour) PNG. That silently corrupts
 * Terrain-RGB wherever the elevation range needs more than 256 distinct
 * RGB triplets (i.e. anywhere with real relief). Forcing the lossless
 * **`.pngraw`** endpoint preserves the bit-exact encoding.
 */
export function customDemTilesUrl(terrainUrl: string, accessToken: string): string {
  const tileset = terrainUrl.replace(/^mapbox:\/\//, "");
  return (
    `https://api.mapbox.com/v4/${tileset}/{z}/{x}/{y}.pngraw` +
    `?access_token=${encodeURIComponent(accessToken)}`
  );
}

export interface TerrainApplyOptions {
  /** Mapbox public token — required to build the custom DEM tiles URL. */
  accessToken?: string;
}

/**
 * Apply a basemap's `pitch` (deg) to the camera. No-op when the basemap
 * doesn't declare one, or when the camera is already within 0.5° of it
 * (avoids an unnecessary render frame on basemap reloads).
 */
export function applyBasemapCamera(
  map: MapCameraSurface,
  basemap: BasemapEntry,
): boolean {
  if (typeof basemap.pitch !== "number") return false;
  if (typeof map.setPitch !== "function") return false;
  const current = typeof map.getPitch === "function" ? map.getPitch() : Number.NaN;
  if (Number.isFinite(current) && Math.abs(current - basemap.pitch) < 0.5) {
    return false;
  }
  map.setPitch(basemap.pitch);
  return true;
}

/**
 * Enable / disable DEM terrain for a basemap.
 *
 *   - `terrain_url`-bearing basemap → mount it as a `raster-dem` source
 *     and `setTerrain` against it. This is the LIDAR / custom-DEM path
 *     (e.g. our `marconasuto.manfredonia-terrain-rgb-v1`).
 *   - `terrain: true` basemap (no custom URL) → fall back to the global
 *     Mapbox Terrain-RGB tileset.
 *   - Otherwise → clear terrain explicitly so a swap back to a flat
 *     style doesn't leave the previous terrain attached.
 *
 * The source is added idempotently so repeated calls (basemap reloads)
 * don't accumulate duplicate sources on the map.
 */
export function applyBasemapTerrain(
  map: MapTerrainSurface,
  basemap: BasemapEntry,
  opts: TerrainApplyOptions = {},
): "added-custom" | "added-mapbox" | "cleared" | "noop" {
  if (typeof map.setTerrain !== "function") return "noop";

  const exaggeration = basemap.terrain_exaggeration ?? DEFAULT_TERRAIN_EXAGGERATION;
  // Bind to `map` — Mapbox `Map` methods read `this._isValidId(...)`
  // internally, so calling a destructured/bare reference throws
  // "Cannot read properties of undefined (reading '_isValidId')".
  const getSource = map.getSource?.bind(map);
  const addSource = map.addSource?.bind(map);
  const ensureSource = (id: string, source: AnySource): void => {
    if (!getSource || !addSource) return;
    if (!getSource(id)) addSource(id, source);
  };

  // Custom LIDAR DEM — only usable when we have a token to sign the
  // lossless `.pngraw` tiles URL. Without it we fall through to the
  // global Mapbox DEM rather than mount a broken source.
  if (basemap.terrain_url && opts.accessToken) {
    ensureSource(CUSTOM_DEM_SOURCE_ID, {
      type: "raster-dem",
      tiles: [customDemTilesUrl(basemap.terrain_url, opts.accessToken)],
      encoding: "mapbox",
      tileSize: CUSTOM_DEM_TILE_SIZE,
      maxzoom: CUSTOM_DEM_MAXZOOM,
    });
    map.setTerrain({ source: CUSTOM_DEM_SOURCE_ID, exaggeration });
    return "added-custom";
  }

  if (basemap.terrain || basemap.terrain_url) {
    ensureSource(MAPBOX_DEM_SOURCE_ID, {
      type: "raster-dem",
      url: MAPBOX_DEM_TILESET,
      tileSize: 512,
      maxzoom: 14,
    });
    map.setTerrain({ source: MAPBOX_DEM_SOURCE_ID, exaggeration });
    return "added-mapbox";
  }

  map.setTerrain(null);
  return "cleared";
}

/** Convenience wrapper: apply both camera + terrain in one call.
 *  Returns the terrain outcome (useful for logging / tests). */
export function applyBasemap(
  map: MapCameraSurface & MapTerrainSurface,
  basemap: BasemapEntry,
  opts: TerrainApplyOptions = {},
): ReturnType<typeof applyBasemapTerrain> {
  applyBasemapCamera(map, basemap);
  return applyBasemapTerrain(map, basemap, opts);
}

/**
 * Narrow `MapboxMap` to the surfaces these helpers actually need.
 * Lets callers pass a real Mapbox map without an explicit cast.
 */
export type ApplicableMap = MapboxMap & MapCameraSurface & MapTerrainSurface;
