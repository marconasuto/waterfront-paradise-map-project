import mapboxgl, { Map as MapboxMap } from "mapbox-gl";

import type { AppEnv } from "../env";
import type { MapboxStyle } from "../types";

export interface InitMapOptions {
  container: HTMLElement;
  /** A full style document or a `mapbox://styles/...` URL. */
  style: MapboxStyle | string;
  env: AppEnv;
  /** Initial camera pitch (deg, 0–85). Defaults to flat (0). */
  pitch?: number;
}

/**
 * Boot a Mapbox GL JS map from a (possibly already-merged) style document.
 *
 * The token is set on the module global before construction so all source,
 * sprite and glyph fetches carry it. The URL hash drives the camera so
 * deep links survive reloads.
 */
export function initMap({ container, style, env, pitch }: InitMapOptions): MapboxMap {
  mapboxgl.accessToken = env.mapboxPublicToken;
  const map = new MapboxMap({
    container,
    style,
    attributionControl: true,
    cooperativeGestures: false,
    // The storymap engine drives the camera via flyTo; the URL hash is
    // reserved for `#slide-<id>` deep links (see ui/story-panel.ts).
    hash: false,
    pitch: typeof pitch === "number" ? pitch : 0,
  });
  map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new mapboxgl.ScaleControl({ unit: "metric" }), "bottom-left");
  return map;
}
