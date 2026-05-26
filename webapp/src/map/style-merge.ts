import type { BasemapEntry, MapboxStyle } from "../types";

/**
 * Convert a `mapbox://styles/<user>/<id>` URL into the REST endpoint we
 * can `fetch()` to retrieve the full style document.
 */
export function mapboxStyleApiUrl(styleUrl: string, accessToken: string): string {
  const match = /^mapbox:\/\/styles\/([^/]+)\/(.+)$/.exec(styleUrl);
  if (!match) {
    throw new Error(`not a mapbox:// style URL: ${styleUrl}`);
  }
  const [, user, id] = match;
  return `https://api.mapbox.com/styles/v1/${user}/${id}?access_token=${encodeURIComponent(accessToken)}`;
}

/** Fetch a basemap's Mapbox-hosted style document. */
export async function fetchBasemapStyle(
  basemap: BasemapEntry,
  accessToken: string,
  fetchFn: typeof fetch = fetch,
): Promise<MapboxStyle> {
  const apiUrl = mapboxStyleApiUrl(basemap.style_url, accessToken);
  const res = await fetchFn(apiUrl);
  if (!res.ok) {
    throw new Error(`failed to fetch ${basemap.style_url}: HTTP ${res.status}`);
  }
  const style = (await res.json()) as MapboxStyle;
  if (style.version !== 8) {
    throw new Error(`${basemap.style_url}: not a v8 Mapbox style`);
  }
  return style;
}

/**
 * Strip the metadata-only `background` layer from our overlay style.
 *
 * The basemap's own background layer is the right one to keep when we
 * merge — otherwise we paint our flat color on top of the basemap.
 */
export function overlaySources(overlay: MapboxStyle): MapboxStyle["sources"] {
  return overlay.sources;
}

export function overlayLayers(overlay: MapboxStyle): MapboxStyle["layers"] {
  return overlay.layers.filter((lyr) => lyr.type !== "background");
}

/**
 * Compose a base Mapbox style with our overlay style.
 *
 * - Base style's sources stay unchanged.
 * - Overlay sources are appended (overlay ids are namespaced
 *   "manfredonia-*" so collisions are unlikely).
 * - Overlay layers are appended *on top* of the base layer stack,
 *   minus the overlay's background layer (the base already has one).
 * - Sprite/glyphs/light/center/zoom from the base are preserved.
 *
 * The result is a complete style document that can be passed to
 * `new Map({ style })` or `map.setStyle(style)`.
 */
export function mergeOverlay(base: MapboxStyle, overlay: MapboxStyle): MapboxStyle {
  return {
    ...base,
    sources: { ...base.sources, ...overlaySources(overlay) },
    layers: [...base.layers, ...overlayLayers(overlay)],
  };
}

/** Pick the default basemap (`default: true`) or fall back to the first one. */
export function pickDefaultBasemap(basemaps: BasemapEntry[]): BasemapEntry {
  if (basemaps.length === 0) {
    throw new Error("no basemaps configured");
  }
  const def = basemaps.find((b) => b.default === true);
  // basemaps[0] is non-null here because length > 0, but TS can't see that
  // under noUncheckedIndexedAccess, so we assert.
  return def ?? (basemaps[0] as BasemapEntry);
}
