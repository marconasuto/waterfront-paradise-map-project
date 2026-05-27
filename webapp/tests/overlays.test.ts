import { beforeEach, describe, expect, it, vi } from "vitest";

import { OverlayManager } from "../src/state/overlays";

function makeFakeMap() {
  const sources = new Set<string>();
  const layers = new Set<string>();
  return {
    addSource: vi.fn((id: string, _spec: unknown) => sources.add(id)),
    addLayer: vi.fn((layer: { id: string }) => layers.add(layer.id)),
    removeSource: vi.fn((id: string) => sources.delete(id)),
    removeLayer: vi.fn((id: string) => layers.delete(id)),
    getLayer: vi.fn((id: string) => (layers.has(id) ? { id } : undefined)),
    getSource: vi.fn((id: string) => (sources.has(id) ? {} : undefined)),
    _sources: sources,
    _layers: layers,
  };
}

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };

describe("OverlayManager", () => {
  let map: ReturnType<typeof makeFakeMap>;
  let mgr: OverlayManager;

  beforeEach(() => {
    map = makeFakeMap();
    mgr = new OverlayManager(map as never);
  });

  it("starts with an empty list", () => {
    expect(mgr.list()).toEqual([]);
  });

  it("adds a source + 3 layers per overlay", () => {
    const h = mgr.add("citizens.geojson", EMPTY_FC);
    expect(map.addSource).toHaveBeenCalledTimes(1);
    expect(map.addLayer).toHaveBeenCalledTimes(3);
    expect(map._sources.size).toBe(1);
    expect(map._layers.size).toBe(3);
    expect(h.name).toBe("citizens.geojson");
  });

  it("assigns a fresh id per add (sequential)", () => {
    const a = mgr.add("a.geojson", EMPTY_FC);
    const b = mgr.add("b.geojson", EMPTY_FC);
    expect(a.id).not.toBe(b.id);
    expect(mgr.list().map((o) => o.id)).toEqual([a.id, b.id]);
  });

  it("cycles colors across overlays", () => {
    const a = mgr.add("a.geojson", EMPTY_FC);
    const b = mgr.add("b.geojson", EMPTY_FC);
    expect(a.color).not.toBe(b.color);
  });

  it("remove drops all 3 layers + the source", () => {
    const h = mgr.add("a.geojson", EMPTY_FC);
    mgr.remove(h.id);
    expect(map.removeLayer).toHaveBeenCalledTimes(3);
    expect(map.removeSource).toHaveBeenCalledTimes(1);
    expect(mgr.list()).toEqual([]);
  });

  it("remove of an unknown id is a no-op", () => {
    mgr.remove("never-existed");
    expect(map.removeLayer).not.toHaveBeenCalled();
  });

  it("clear removes everything", () => {
    mgr.add("a", EMPTY_FC);
    mgr.add("b", EMPTY_FC);
    mgr.clear();
    expect(mgr.list()).toEqual([]);
    expect(map._sources.size).toBe(0);
    expect(map._layers.size).toBe(0);
  });

  it("records the feature count", () => {
    const fc = {
      type: "FeatureCollection" as const,
      features: [
        { type: "Feature" as const, geometry: null, properties: null },
        { type: "Feature" as const, geometry: null, properties: null },
      ],
    };
    const h = mgr.add("two.geojson", fc);
    expect(h.featureCount).toBe(2);
  });
});
