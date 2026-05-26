import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyLayerState,
  defaultLayerState,
  extractManfredoniaLayerIds,
  loadLayerState,
  opacityPaintProperty,
  reconcileLayerState,
  saveLayerState,
  type LayerState,
} from "../src/state/layer-state";
import type { MapboxStyle } from "../src/types";

class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  key(i: number): string | null {
    return Array.from(this.store.keys())[i] ?? null;
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

const STYLE: MapboxStyle = {
  version: 8,
  name: "x",
  sources: {},
  layers: [
    { id: "background", type: "background", paint: {} },
    { id: "mapbox-roads", type: "line", source: "mapbox-streets", paint: {} },
    {
      id: "manfredonia-wetlands",
      type: "fill",
      source: "manfredonia-wetlands",
      "source-layer": "wetlands",
      paint: {},
    },
    {
      id: "manfredonia-coastline",
      type: "line",
      source: "manfredonia-coastline",
      "source-layer": "coastline",
      paint: {},
    },
  ],
} as MapboxStyle;

describe("extractManfredoniaLayerIds", () => {
  it("keeps only manfredonia-* layers in style order", () => {
    expect(extractManfredoniaLayerIds(STYLE)).toEqual([
      "manfredonia-wetlands",
      "manfredonia-coastline",
    ]);
  });
});

describe("defaultLayerState + reconcileLayerState", () => {
  it("defaults to visible + opacity 1", () => {
    const s = defaultLayerState(["a", "b"]);
    expect(s).toEqual([
      { layerId: "a", visible: true, opacity: 1 },
      { layerId: "b", visible: true, opacity: 1 },
    ]);
  });

  it("reconciles stored state with fresh layer-id list", () => {
    const stored: LayerState[] = [
      { layerId: "a", visible: false, opacity: 0.5 },
      { layerId: "gone", visible: true, opacity: 1 },
    ];
    const next = reconcileLayerState(["a", "b"], stored);
    expect(next).toEqual([
      { layerId: "a", visible: false, opacity: 0.5 },
      { layerId: "b", visible: true, opacity: 1 },
    ]);
  });

  it("clamps stored opacity to [0,1]", () => {
    const stored: LayerState[] = [{ layerId: "a", visible: true, opacity: 99 }];
    expect(reconcileLayerState(["a"], stored)[0]!.opacity).toBe(1);

    const stored2: LayerState[] = [{ layerId: "a", visible: true, opacity: -5 }];
    expect(reconcileLayerState(["a"], stored2)[0]!.opacity).toBe(0);
  });

  it("falls back to defaults when stored is null", () => {
    expect(reconcileLayerState(["a"], null)).toEqual([
      { layerId: "a", visible: true, opacity: 1 },
    ]);
  });
});

describe("save / loadLayerState", () => {
  let storage: MemoryStorage;
  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it("round-trips state through storage", () => {
    const state: LayerState[] = [{ layerId: "a", visible: false, opacity: 0.3 }];
    saveLayerState(state, storage);
    expect(loadLayerState(storage)).toEqual(state);
  });

  it("returns null when nothing is stored", () => {
    expect(loadLayerState(storage)).toBeNull();
  });

  it("returns null on malformed JSON", () => {
    storage.setItem("manfredonia-map:layer-state:v1", "{not-json");
    expect(loadLayerState(storage)).toBeNull();
  });

  it("ignores entries with the wrong shape", () => {
    storage.setItem(
      "manfredonia-map:layer-state:v1",
      JSON.stringify([
        { layerId: "ok", visible: true, opacity: 0.5 },
        { layerId: 42 }, // wrong shape
      ]),
    );
    expect(loadLayerState(storage)).toEqual([{ layerId: "ok", visible: true, opacity: 0.5 }]);
  });
});

describe("opacityPaintProperty", () => {
  it.each([
    ["fill", "fill-opacity"],
    ["line", "line-opacity"],
    ["circle", "circle-opacity"],
    ["raster", "raster-opacity"],
  ])("%s -> %s", (input, expected) => {
    expect(opacityPaintProperty(input)).toBe(expected);
  });
});

describe("applyLayerState", () => {
  it("calls setLayoutProperty + setPaintProperty for every known layer", () => {
    const layers: Record<string, { id: string; type: string }> = {
      "manfredonia-wetlands": { id: "manfredonia-wetlands", type: "fill" },
      "manfredonia-coastline": { id: "manfredonia-coastline", type: "line" },
    };
    const getLayer = vi.fn((id: string) => layers[id]);
    const setLayoutProperty = vi.fn();
    const setPaintProperty = vi.fn();
    const map = { getLayer, setLayoutProperty, setPaintProperty } as never;

    applyLayerState(map, [
      { layerId: "manfredonia-wetlands", visible: false, opacity: 0.4 },
      { layerId: "manfredonia-coastline", visible: true, opacity: 1 },
      { layerId: "manfredonia-missing", visible: true, opacity: 1 },
    ]);

    expect(setLayoutProperty).toHaveBeenCalledTimes(2);
    expect(setLayoutProperty).toHaveBeenCalledWith(
      "manfredonia-wetlands",
      "visibility",
      "none",
    );
    expect(setLayoutProperty).toHaveBeenCalledWith(
      "manfredonia-coastline",
      "visibility",
      "visible",
    );
    expect(setPaintProperty).toHaveBeenCalledTimes(2);
    expect(setPaintProperty).toHaveBeenCalledWith("manfredonia-wetlands", "fill-opacity", 0.4);
    expect(setPaintProperty).toHaveBeenCalledWith("manfredonia-coastline", "line-opacity", 1);
  });
});
