import { describe, expect, it, vi } from "vitest";

import { loadStyle, styleLayerCount, styleSourceCount } from "../src/map/style-loader";

const STYLE_FIXTURE = {
  version: 8,
  name: "test",
  sources: {
    a: { type: "vector", url: "mapbox://tester.a" },
    b: { type: "raster", url: "mapbox://tester.b", tileSize: 256 },
  },
  layers: [
    { id: "background", type: "background", paint: {} },
    { id: "a-fill", type: "fill", source: "a", "source-layer": "a", paint: {} },
  ],
};

function fakeFetch(status: number, body: unknown): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

describe("loadStyle", () => {
  it("returns the parsed style on a 200 response", async () => {
    const style = await loadStyle("/style.json", fakeFetch(200, STYLE_FIXTURE));
    expect(style.version).toBe(8);
    expect(Object.keys(style.sources)).toEqual(["a", "b"]);
  });

  it("throws on a non-2xx response", async () => {
    await expect(loadStyle("/style.json", fakeFetch(404, {}))).rejects.toThrow(/HTTP 404/);
  });

  it("rejects a non-object body", async () => {
    await expect(loadStyle("/style.json", fakeFetch(200, "oops"))).rejects.toThrow(/JSON object/);
  });

  it("rejects a wrong style version", async () => {
    await expect(
      loadStyle("/style.json", fakeFetch(200, { ...STYLE_FIXTURE, version: 7 })),
    ).rejects.toThrow(/version 8/);
  });

  it("rejects missing sources", async () => {
    const broken = { ...STYLE_FIXTURE, sources: null };
    await expect(loadStyle("/style.json", fakeFetch(200, broken))).rejects.toThrow(/sources/);
  });

  it("rejects missing layers", async () => {
    const broken = { ...STYLE_FIXTURE, layers: "nope" };
    await expect(loadStyle("/style.json", fakeFetch(200, broken))).rejects.toThrow(/layers/);
  });
});

describe("styleSourceCount + styleLayerCount", () => {
  it("counts sources and layers", () => {
    expect(styleSourceCount(STYLE_FIXTURE as never)).toBe(2);
    expect(styleLayerCount(STYLE_FIXTURE as never)).toBe(2);
  });

  it("returns 0 for an empty style", () => {
    const empty = { version: 8, sources: {}, layers: [] };
    expect(styleSourceCount(empty as never)).toBe(0);
    expect(styleLayerCount(empty as never)).toBe(0);
  });
});
