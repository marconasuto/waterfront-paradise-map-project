import { parse as parseYaml } from "yaml";

import type { BasemapsConfig, ColorScheme, HighlightsConfig } from "../types";

/**
 * Fetch a YAML config from the webapp's publicDir.
 *
 * `scripts/sync-config.mjs` mirrors `config/*.yaml` from the repo root
 * into `webapp/public/` at build time, so these are local fetches with
 * no network round-trip.
 */
export async function loadYaml<T>(url: string, fetchFn: typeof fetch = fetch): Promise<T> {
  const res = await fetchFn(url);
  if (!res.ok) {
    throw new Error(`failed to load ${url}: HTTP ${res.status}`);
  }
  const text = await res.text();
  const parsed = parseYaml(text);
  if (typeof parsed !== "object" || parsed === null) {
    throw new Error(`${url}: YAML did not parse to an object`);
  }
  return parsed as T;
}

/** Load + shallow-validate the basemap registry. */
export async function loadBasemaps(
  url = "/basemaps.yaml",
  fetchFn?: typeof fetch,
): Promise<BasemapsConfig> {
  const cfg = await loadYaml<BasemapsConfig>(url, fetchFn);
  if (!Array.isArray(cfg.basemaps) || cfg.basemaps.length === 0) {
    throw new Error(`${url}: expected non-empty \`basemaps\` array`);
  }
  for (const b of cfg.basemaps) {
    if (!b.id || !b.style_url) {
      throw new Error(`${url}: every basemap needs an \`id\` and \`style_url\``);
    }
  }
  return cfg;
}

export async function loadHighlights(
  url = "/highlights.yaml",
  fetchFn?: typeof fetch,
): Promise<HighlightsConfig> {
  const cfg = await loadYaml<HighlightsConfig>(url, fetchFn);
  if (!Array.isArray(cfg.highlights)) {
    throw new Error(`${url}: expected \`highlights\` array`);
  }
  return cfg;
}

export async function loadColorScheme(
  url = "/color_scheme.yaml",
  fetchFn?: typeof fetch,
): Promise<ColorScheme> {
  const cfg = await loadYaml<ColorScheme>(url, fetchFn);
  if (typeof cfg.palette !== "object" || cfg.palette === null) {
    throw new Error(`${url}: missing \`palette\` mapping`);
  }
  return cfg;
}
