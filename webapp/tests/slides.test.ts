import { describe, expect, it, vi } from "vitest";

import { loadSlideBody, loadSlideIndex, type SlideMeta } from "../src/content/slides";

const SLIDE: SlideMeta = {
  id: "00_intro",
  title: "Intro",
  camera: { center: [15.92, 41.62], zoom: 10.5 },
  layers_visible: ["coastline"],
  body_ref: "slides/00_intro.md",
};

function fakeJson(status: number, body: unknown): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

function fakeText(status: number, body: string): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

describe("loadSlideIndex", () => {
  it("returns slides on a 200 response", async () => {
    const got = await loadSlideIndex("/slides.json", fakeJson(200, [SLIDE]));
    expect(got).toHaveLength(1);
    expect(got[0]!.id).toBe("00_intro");
  });

  it("throws on HTTP error", async () => {
    await expect(loadSlideIndex("/slides.json", fakeJson(404, []))).rejects.toThrow(/HTTP 404/);
  });

  it("throws when JSON is not an array", async () => {
    await expect(loadSlideIndex("/slides.json", fakeJson(200, { x: 1 }))).rejects.toThrow(
      /array/,
    );
  });

  it("filters out malformed entries", async () => {
    const mix = [SLIDE, { id: "broken" }, null, { ...SLIDE, id: "ok2" }];
    const got = await loadSlideIndex("/slides.json", fakeJson(200, mix));
    expect(got.map((s) => s.id)).toEqual(["00_intro", "ok2"]);
  });
});

describe("loadSlideBody", () => {
  it("returns the rendered markdown when the body exists", async () => {
    const html = await loadSlideBody(SLIDE, fakeText(200, "# Title\n"));
    expect(html).toContain("<h1>");
  });

  it("falls back to a placeholder when the body is missing", async () => {
    const html = await loadSlideBody(SLIDE, fakeText(404, ""));
    expect(html).toContain("arrivo");
  });
});
