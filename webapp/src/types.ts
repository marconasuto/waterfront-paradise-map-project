/**
 * Lightweight types for the data files we pull from the Python pipeline
 * via scripts/sync-config.mjs. These mirror the shape produced by
 * `src/manfredonia_map/publishing/styles.py` and `config/*.yaml` but stay
 * deliberately permissive — Mapbox GL JS already validates the style.
 */

import type { StyleSpecification } from "mapbox-gl";

export type MapboxStyle = StyleSpecification;

export interface BasemapEntry {
  id: string;
  name_it: string;
  style_url: string;
  default?: boolean;
  /** Camera pitch (deg, 0–85) applied when this basemap is selected.
   *  Used by 3D-capable styles like `mapbox://styles/mapbox/standard`. */
  pitch?: number;
  /** Whether to enable Mapbox's built-in DEM terrain layer (Standard
   *  has its own; this is for static styles like outdoors-v12 where we
   *  add `map.setTerrain()` against the global mapbox-dem source). */
  terrain?: boolean;
  /** Optional custom raster-dem tileset URL (e.g. our LIDAR-derived
   *  `mapbox://marconasuto.manfredonia-terrain-rgb-v1`). When set,
   *  `applyBasemapTerrain` uses this tileset instead of the global
   *  Mapbox DEM. Implies `terrain: true`. */
  terrain_url?: string;
  /** Vertical exaggeration for `setTerrain`. Defaults to 1.3. */
  terrain_exaggeration?: number;
}

export interface BasemapsConfig {
  version: number;
  basemaps: BasemapEntry[];
}

export interface HighlightEntry {
  id: string;
  name_it: string;
  category: string;
  coord: [number, number];
  style_token: string;
  content_ref: string;
}

export interface HighlightsConfig {
  version: number;
  highlights: HighlightEntry[];
}

export type PaletteSwatch = "fill" | "line" | "label";
export type Palette = Record<string, Partial<Record<PaletteSwatch, string>>>;

export interface ColorScheme {
  version: number;
  palette: Palette;
}
