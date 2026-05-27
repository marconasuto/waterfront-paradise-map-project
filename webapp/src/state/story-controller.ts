import type { Map as MapboxMap } from "mapbox-gl";

import type { SlideMeta } from "../content/slides";
import { applyLayerState, type LayerState } from "./layer-state";

/**
 * Convert a slide's `layers_visible` list (bare ids like `coastline`)
 * into a `LayerState[]` whose visibility matches: every layer in the
 * baseline state is set to `visible: true` if it's in `layers_visible`,
 * `false` otherwise. Opacity is preserved.
 *
 * If `layers_visible` is missing or empty, the baseline is returned
 * unchanged (no override).
 */
export function deriveSlideState(
  baseline: LayerState[],
  layersVisible: string[] | undefined,
  prefix = "manfredonia-",
): LayerState[] {
  if (!layersVisible || layersVisible.length === 0) return baseline;
  const want = new Set(layersVisible.map((id) => `${prefix}${id}`));
  return baseline.map((s) => ({ ...s, visible: want.has(s.layerId) }));
}

export interface ApplySlideOptions {
  map: MapboxMap;
  baseline: LayerState[];
  slide: SlideMeta;
  /** Override `flyTo` (used in tests so we don't need a real Mapbox map). */
  flyTo?: (cam: SlideMeta["camera"]) => void;
}

/**
 * Apply a slide's camera + layer visibility to the map.
 *
 * Returns the derived layer state so the caller can update the layer
 * panel UI to mirror what's now actually visible on the map.
 */
export function applySlide(opts: ApplySlideOptions): LayerState[] {
  const cam = opts.slide.camera;
  const flyTo =
    opts.flyTo ??
    ((c) =>
      opts.map.flyTo({
        center: c.center,
        zoom: c.zoom,
        bearing: c.bearing ?? 0,
        pitch: c.pitch ?? 0,
        essential: true,
      }));
  flyTo(cam);
  const next = deriveSlideState(opts.baseline, opts.slide.layers_visible);
  applyLayerState(opts.map, next);
  return next;
}
