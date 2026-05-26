import mapboxgl, { Map as MapboxMap } from "mapbox-gl";

import type { AppEnv } from "../env";
import type { MapboxStyle } from "../types";

export interface InitMapOptions {
  container: HTMLElement;
  style: MapboxStyle;
  env: AppEnv;
}

/**
 * Boot a Mapbox GL JS map from a prebuilt style document.
 *
 * The style's center/zoom drive the initial camera; the access token is
 * set on the module global before construction so all source/sprite/glyph
 * fetches carry it.
 */
export function initMap({ container, style, env }: InitMapOptions): MapboxMap {
  mapboxgl.accessToken = env.mapboxPublicToken;
  const map = new MapboxMap({
    container,
    style,
    attributionControl: true,
    cooperativeGestures: false,
    hash: true,
  });
  map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new mapboxgl.ScaleControl({ unit: "metric" }), "bottom-left");
  return map;
}
