import type { Map as MapboxMap } from "mapbox-gl";

import type { FeatureCollection } from "../io/geojson-file";

/** A registered ephemeral overlay tracked by `OverlayManager`. */
export interface OverlayHandle {
  id: string;
  name: string;
  color: string;
  featureCount: number;
}

const OVERLAY_PREFIX = "user-overlay-";

/** Cycle through a small palette so each overlay gets a distinct color. */
const PALETTE = ["#f8d030", "#1bd1b4", "#ff6e7a", "#7e57c2", "#ffa726", "#42a5f5"];

/**
 * Manages a small in-memory registry of user-dropped GeoJSON overlays.
 *
 * Per layer, three Mapbox layers are added on top of the style — one
 * each for circle, line, fill — filtered by `$type` so a single source
 * renders all geometry families cleanly without us inspecting the file.
 */
export class OverlayManager {
  private readonly registry = new Map<string, OverlayHandle>();
  private seq = 0;

  constructor(private readonly map: MapboxMap) {}

  list(): OverlayHandle[] {
    return Array.from(this.registry.values());
  }

  add(name: string, collection: FeatureCollection): OverlayHandle {
    const idx = this.seq;
    this.seq += 1;
    const id = `${OVERLAY_PREFIX}${idx}`;
    const color = PALETTE[idx % PALETTE.length] ?? "#f8d030";
    // Mapbox types pull in strict @types/geojson; our parsed shape is
    // permissive on purpose (geometry?: null for empty features), so we
    // hand it over as `any` at the boundary.
    this.map.addSource(id, { type: "geojson", data: collection as never });
    this.map.addLayer({
      id: `${id}-fill`,
      type: "fill",
      source: id,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": color, "fill-opacity": 0.35, "fill-outline-color": color },
    });
    this.map.addLayer({
      id: `${id}-line`,
      type: "line",
      source: id,
      filter: ["in", ["geometry-type"], ["literal", ["LineString", "Polygon"]]],
      paint: { "line-color": color, "line-width": 1.6 },
    });
    this.map.addLayer({
      id: `${id}-circle`,
      type: "circle",
      source: id,
      filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-color": color, "circle-radius": 5, "circle-stroke-color": "#0e1a23", "circle-stroke-width": 1 },
    });
    const handle: OverlayHandle = {
      id,
      name,
      color,
      featureCount: collection.features.length,
    };
    this.registry.set(id, handle);
    return handle;
  }

  remove(id: string): void {
    if (!this.registry.has(id)) return;
    for (const suffix of ["-fill", "-line", "-circle"]) {
      const layerId = `${id}${suffix}`;
      if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
    }
    if (this.map.getSource(id)) this.map.removeSource(id);
    this.registry.delete(id);
  }

  clear(): void {
    for (const id of Array.from(this.registry.keys())) {
      this.remove(id);
    }
  }
}
