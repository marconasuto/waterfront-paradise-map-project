import type { Map as MapboxMap } from "mapbox-gl";

import type { MapboxStyle } from "../types";

/** Per-layer UI-controlled state. The order in a `LayerState[]`
 * matches the desired render order (top of the array = bottom of the
 * map, same convention as Mapbox layer arrays). */
export interface LayerState {
  layerId: string;
  visible: boolean;
  opacity: number;
}

const STORAGE_KEY = "manfredonia-map:layer-state:v1";
const DEFAULT_OPACITY = 1;

/**
 * Extract the manfredonia-* layer ids from a built style. We exclude
 * the background and any non-`manfredonia-*` layers (these come from
 * the basemap and should not be user-toggleable here).
 */
export function extractManfredoniaLayerIds(style: MapboxStyle): string[] {
  return style.layers.filter((l) => l.id.startsWith("manfredonia-")).map((l) => l.id);
}

/** Build a sane default state from a layer-id list (all visible, full opacity). */
export function defaultLayerState(layerIds: string[]): LayerState[] {
  return layerIds.map((layerId) => ({ layerId, visible: true, opacity: DEFAULT_OPACITY }));
}

/**
 * Merge `stored` state into the canonical layer order from `layerIds`.
 *
 * - Layers in `layerIds` but not in `stored` get defaults.
 * - Layers in `stored` but not in `layerIds` are dropped (we no longer
 *   render them — e.g. the user upgraded and the layer was removed).
 * - Order follows `layerIds` (the rendered order), not the stored array.
 */
export function reconcileLayerState(
  layerIds: string[],
  stored: LayerState[] | null,
): LayerState[] {
  const storedById = new Map((stored ?? []).map((s) => [s.layerId, s]));
  return layerIds.map((layerId) => {
    const prev = storedById.get(layerId);
    return {
      layerId,
      visible: prev?.visible ?? true,
      opacity: clampOpacity(prev?.opacity ?? DEFAULT_OPACITY),
    };
  });
}

function clampOpacity(o: number): number {
  if (!Number.isFinite(o)) return DEFAULT_OPACITY;
  if (o < 0) return 0;
  if (o > 1) return 1;
  return o;
}

/** Persist the current state. Throws on QuotaExceeded etc. — caller should catch. */
export function saveLayerState(state: LayerState[], storage: Storage = localStorage): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/** Read state from storage. Returns `null` on missing / malformed. */
export function loadLayerState(storage: Storage = localStorage): LayerState[] | null {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    return parsed
      .filter(
        (e): e is LayerState =>
          typeof e === "object" &&
          e !== null &&
          typeof (e as LayerState).layerId === "string" &&
          typeof (e as LayerState).visible === "boolean" &&
          typeof (e as LayerState).opacity === "number",
      )
      .map((e) => ({ ...e, opacity: clampOpacity(e.opacity) }));
  } catch {
    return null;
  }
}

/**
 * Pick the Mapbox paint property that controls opacity for a given
 * layer type. Mapbox uses `${type}-opacity` for fill/line/circle/raster.
 */
export function opacityPaintProperty(layerType: string): string {
  return `${layerType}-opacity`;
}

/**
 * Move element at `from` to position `to`. Returns a new array; the
 * input is untouched. `to` is clamped into range so out-of-range
 * indices are a no-op instead of an exception.
 */
export function moveLayerStateEntry(
  state: LayerState[],
  from: number,
  to: number,
): LayerState[] {
  if (from < 0 || from >= state.length) return state;
  const clamped = Math.max(0, Math.min(state.length - 1, to));
  if (from === clamped) return state;
  const next = state.slice();
  const [item] = next.splice(from, 1);
  if (item) next.splice(clamped, 0, item);
  return next;
}

/**
 * Push the current render order to the map.
 *
 * Mapbox layer ordering: layers later in the array render on top.
 * `moveLayer(id)` without a `before` argument moves the layer to the
 * top of the stack. By walking `state` first → last and moving each
 * id to the top in turn, the final order matches the state array
 * (state[0] at the bottom, state[N-1] at the top). Unknown ids are
 * skipped — happens during the brief window after `setStyle()` while
 * the new style is still loading.
 */
export function applyLayerOrder(map: MapboxMap, state: LayerState[]): void {
  for (const entry of state) {
    if (!map.getLayer(entry.layerId)) continue;
    try {
      map.moveLayer(entry.layerId);
    } catch {
      // Some basemap layouts can race the moveLayer call; ignore.
    }
  }
}

/**
 * Push the entire state into the map: visibility via `setLayoutProperty`,
 * opacity via `setPaintProperty`. Layers we don't recognise are skipped
 * silently (this happens during the brief window after `setStyle` while
 * the new style is still loading).
 */
export function applyLayerState(map: MapboxMap, state: LayerState[]): void {
  // Mapbox types each paint property as a string-literal union, so the
  // generic `${type}-opacity` form doesn't typecheck. The shape is
  // correct at runtime; cast to a permissive signature once here.
  const setPaint = map.setPaintProperty.bind(map) as (
    layerId: string,
    name: string,
    value: unknown,
  ) => unknown;
  for (const entry of state) {
    const layer = map.getLayer(entry.layerId);
    if (!layer) continue;
    map.setLayoutProperty(entry.layerId, "visibility", entry.visible ? "visible" : "none");
    setPaint(entry.layerId, opacityPaintProperty(layer.type), entry.opacity);
  }
}
