import type { MapboxStyle } from "../types";

/**
 * Fetch and parse the prebuilt Mapbox style JSON.
 *
 * The Python pipeline writes `data/processed/style.json` via
 * `mfd-map publish style`; `scripts/sync-config.mjs` copies it into
 * `webapp/public/style.json` at build time, so this fetch is local
 * (no network round-trip, no CORS).
 */
export async function loadStyle(
  baseUrl: string = "/style.json",
  fetchFn: typeof fetch = fetch,
): Promise<MapboxStyle> {
  const res = await fetchFn(baseUrl);
  if (!res.ok) {
    throw new Error(`failed to load ${baseUrl}: HTTP ${res.status}`);
  }
  const style = (await res.json()) as MapboxStyle;
  assertIsStyle(style, baseUrl);
  return style;
}

/**
 * Inject the user's `pk.*` token into every Mapbox source/sprite/glyph
 * URL. Mapbox GL JS does this automatically when you set the access
 * token *before* `new Map(...)`, but we keep the helper so the loader
 * is callable in tests without booting a map.
 */
export function styleSourceCount(style: MapboxStyle): number {
  return Object.keys(style.sources ?? {}).length;
}

export function styleLayerCount(style: MapboxStyle): number {
  return (style.layers ?? []).length;
}

function assertIsStyle(value: unknown, where: string): asserts value is MapboxStyle {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${where} did not return a JSON object`);
  }
  const s = value as { version?: unknown; sources?: unknown; layers?: unknown };
  if (s.version !== 8) {
    throw new Error(`${where}: expected Mapbox style version 8, got ${String(s.version)}`);
  }
  if (typeof s.sources !== "object" || s.sources === null) {
    throw new Error(`${where}: missing or invalid \`sources\` object`);
  }
  if (!Array.isArray(s.layers)) {
    throw new Error(`${where}: missing or invalid \`layers\` array`);
  }
}
