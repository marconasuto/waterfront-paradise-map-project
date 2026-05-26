import { describe, expect, it, vi } from "vitest";

import {
  loadBasemaps,
  loadColorScheme,
  loadHighlights,
  loadYaml,
} from "../src/config/loader";

function fakeFetch(status: number, body: string): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

describe("loadYaml", () => {
  it("parses a YAML object", async () => {
    const out = await loadYaml<{ a: number }>("/x", fakeFetch(200, "a: 1"));
    expect(out.a).toBe(1);
  });

  it("throws on HTTP error", async () => {
    await expect(loadYaml("/x", fakeFetch(500, ""))).rejects.toThrow(/HTTP 500/);
  });

  it("throws when YAML is not an object", async () => {
    await expect(loadYaml("/x", fakeFetch(200, "just-a-string"))).rejects.toThrow(/object/);
  });
});

describe("loadBasemaps", () => {
  const ok = `
version: 1
basemaps:
  - { id: a, name_it: A, style_url: "mapbox://styles/mapbox/light-v11", default: true }
  - { id: b, name_it: B, style_url: "mapbox://styles/mapbox/streets-v12" }
`;

  it("returns the parsed registry", async () => {
    const cfg = await loadBasemaps("/b.yaml", fakeFetch(200, ok));
    expect(cfg.basemaps).toHaveLength(2);
    expect(cfg.basemaps[0]!.id).toBe("a");
  });

  it("rejects an empty list", async () => {
    await expect(
      loadBasemaps("/b.yaml", fakeFetch(200, "version: 1\nbasemaps: []\n")),
    ).rejects.toThrow(/non-empty/);
  });

  it("rejects entries missing id or style_url", async () => {
    const bad = `
version: 1
basemaps:
  - { name_it: A }
`;
    await expect(loadBasemaps("/b.yaml", fakeFetch(200, bad))).rejects.toThrow(/id.*style_url/);
  });
});

describe("loadHighlights + loadColorScheme", () => {
  it("loads highlights", async () => {
    const yaml = `
version: 1
highlights:
  - { id: x, name_it: X, category: c, coord: [1,2], style_token: t, content_ref: r.md }
`;
    const cfg = await loadHighlights("/h.yaml", fakeFetch(200, yaml));
    expect(cfg.highlights).toHaveLength(1);
  });

  it("rejects highlights without an array", async () => {
    await expect(
      loadHighlights("/h.yaml", fakeFetch(200, "version: 1\nhighlights: oops\n")),
    ).rejects.toThrow(/highlights/);
  });

  it("loads color scheme", async () => {
    const yaml = `
version: 1
palette:
  water: { fill: "#0000ff", line: "#000088" }
`;
    const cfg = await loadColorScheme("/c.yaml", fakeFetch(200, yaml));
    expect(cfg.palette.water?.fill).toBe("#0000ff");
  });

  it("rejects color scheme without palette", async () => {
    await expect(
      loadColorScheme("/c.yaml", fakeFetch(200, "version: 1\n")),
    ).rejects.toThrow(/palette/);
  });
});
