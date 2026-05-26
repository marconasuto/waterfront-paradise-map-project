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
