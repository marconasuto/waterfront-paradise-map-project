import { describe, expect, it, vi } from "vitest";

import {
  fetchBasemapStyle,
  mapboxStyleApiUrl,
  mergeOverlay,
  overlayLayers,
  overlaySources,
  pickDefaultBasemap,
} from "../src/map/style-merge";
import type { BasemapEntry, MapboxStyle } from "../src/types";

const TOKEN = "pk.test";

const BASE: MapboxStyle = {
  version: 8,
  name: "base",
  sources: { "mapbox-streets": { type: "vector", url: "mapbox://mapbox.mapbox-streets-v8" } },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#fff" } },
    { id: "roads", type: "line", source: "mapbox-streets", "source-layer": "road", paint: {} },
  ],
  sprite: "mapbox://sprites/mapbox/light-v11",
  glyphs: "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
} as MapboxStyle;

const OVERLAY: MapboxStyle = {
  version: 8,
  name: "overlay",
  sources: {
    "manfredonia-wetlands": { type: "vector", url: "mapbox://tester.x" },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#000" } },
    {
      id: "manfredonia-wetlands",
      type: "fill",
      source: "manfredonia-wetlands",
      "source-layer": "wetlands",
      paint: {},
    },
  ],
} as MapboxStyle;

describe("mapboxStyleApiUrl", () => {
  it("translates mapbox:// to the REST endpoint", () => {
    const u = mapboxStyleApiUrl("mapbox://styles/mapbox/light-v11", TOKEN);
    expect(u).toBe("https://api.mapbox.com/styles/v1/mapbox/light-v11?access_token=pk.test");
  });

  it("rejects non-mapbox URLs", () => {
    expect(() => mapboxStyleApiUrl("https://example.com/x", TOKEN)).toThrow(/mapbox:\/\//);
  });
});

describe("fetchBasemapStyle", () => {
  const basemap: BasemapEntry = {
    id: "light",
    name_it: "Chiaro",
    style_url: "mapbox://styles/mapbox/light-v11",
  };

  function ok(body: unknown): typeof fetch {
    return vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    }) as unknown as typeof fetch;
  }

  function fail(status: number): typeof fetch {
    return vi.fn().mockResolvedValue({
      ok: false,
      status,
      json: () => Promise.resolve({}),
    }) as unknown as typeof fetch;
  }

  it("returns the base style on a 200 response", async () => {
    const s = await fetchBasemapStyle(basemap, TOKEN, ok(BASE));
    expect(s.version).toBe(8);
    expect(Object.keys(s.sources)).toContain("mapbox-streets");
  });

  it("throws on HTTP error", async () => {
    await expect(fetchBasemapStyle(basemap, TOKEN, fail(403))).rejects.toThrow(/HTTP 403/);
  });

  it("throws on a non-v8 style", async () => {
    await expect(fetchBasemapStyle(basemap, TOKEN, ok({ ...BASE, version: 7 }))).rejects.toThrow(
      /v8/,
    );
  });
});

describe("overlay helpers + mergeOverlay", () => {
  it("strips the overlay's background layer", () => {
    const layers = overlayLayers(OVERLAY);
    expect(layers.map((l) => l.id)).toEqual(["manfredonia-wetlands"]);
  });

  it("exposes overlay sources untouched", () => {
    const srcs = overlaySources(OVERLAY);
    expect(Object.keys(srcs)).toEqual(["manfredonia-wetlands"]);
  });

  it("merges sources and appends overlay layers above the base stack", () => {
    const merged = mergeOverlay(BASE, OVERLAY);
    expect(Object.keys(merged.sources)).toEqual(["mapbox-streets", "manfredonia-wetlands"]);
    expect(merged.layers.map((l) => l.id)).toEqual([
      "background",
      "roads",
      "manfredonia-wetlands",
    ]);
    // Sprite + glyphs come from the base.
    expect(merged.sprite).toBe("mapbox://sprites/mapbox/light-v11");
  });
});

describe("pickDefaultBasemap", () => {
  it("returns the entry flagged default", () => {
    const a: BasemapEntry = { id: "a", name_it: "A", style_url: "mapbox://styles/x/a" };
    const b: BasemapEntry = {
      id: "b",
      name_it: "B",
      style_url: "mapbox://styles/x/b",
      default: true,
    };
    expect(pickDefaultBasemap([a, b]).id).toBe("b");
  });

  it("falls back to the first entry when none is flagged", () => {
    const a: BasemapEntry = { id: "a", name_it: "A", style_url: "mapbox://styles/x/a" };
    const b: BasemapEntry = { id: "b", name_it: "B", style_url: "mapbox://styles/x/b" };
    expect(pickDefaultBasemap([a, b]).id).toBe("a");
  });

  it("throws on an empty list", () => {
    expect(() => pickDefaultBasemap([])).toThrow(/no basemaps/);
  });
});
