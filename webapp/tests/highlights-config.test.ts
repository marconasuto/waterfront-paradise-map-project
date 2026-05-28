import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { parse as parseYaml } from "yaml";
import { describe, expect, it } from "vitest";

import type { HighlightsConfig } from "../src/types";

/**
 * Sanity checks for `public/highlights.yaml`.
 *
 * Pins are read by humans and rendered at zoom 10–14 — the difference
 * between "in the harbour" and "in the open sea" is a few hundred
 * metres. After we discovered every pin was misplaced in the first
 * iteration, this test locks in the AOI bbox + per-category land
 * constraints so a future YAML edit can't silently drop a pin in the
 * Adriatic again.
 */

// Read the canonical source (config/), not the gitignored public/ copy
// that's only generated at dev/build time — CI runs tests before the build.
const CONFIG_PATH = resolve(process.cwd(), "../config/highlights.yaml");

const CFG = parseYaml(readFileSync(CONFIG_PATH, "utf-8")) as HighlightsConfig;

// Manfredonia AOI envelope (from data/catalog.yaml `aoi.source_path` extent).
// lon: 15.7939 — 16.0550, lat: 41.4852 — 41.6930
const AOI = {
  lonMin: 15.7939,
  lonMax: 16.0551,
  latMin: 41.4852,
  latMax: 41.6931,
} as const;

describe("highlights.yaml — schema", () => {
  it("is version 1", () => {
    expect(CFG.version).toBe(1);
  });

  it("contains a non-empty highlights array", () => {
    expect(Array.isArray(CFG.highlights)).toBe(true);
    expect(CFG.highlights.length).toBeGreaterThan(0);
  });

  it.each(["id", "name_it", "category", "coord", "style_token", "content_ref"])(
    "every entry has %s",
    (key) => {
      for (const h of CFG.highlights) {
        expect(h, `entry ${h.id} missing ${key}`).toHaveProperty(key);
      }
    },
  );

  it("ids are unique", () => {
    const ids = CFG.highlights.map((h) => h.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("highlights.yaml — coordinates", () => {
  it.each(CFG.highlights.map((h) => [h.id, h.coord] as const))(
    "%s lies inside the Manfredonia AOI envelope",
    (_id, coord) => {
      const [lon, lat] = coord;
      expect(lon).toBeGreaterThanOrEqual(AOI.lonMin);
      expect(lon).toBeLessThanOrEqual(AOI.lonMax);
      expect(lat).toBeGreaterThanOrEqual(AOI.latMin);
      expect(lat).toBeLessThanOrEqual(AOI.latMax);
    },
  );

  it.each(CFG.highlights.map((h) => [h.id, h.coord] as const))(
    "%s has [lon, lat] order (lat plausibly larger than lon for southern Italy)",
    (_id, coord) => {
      const [lon, lat] = coord;
      // Manfredonia: lon ~15.9, lat ~41.6 — flipping the pair would
      // give lon > 41 (off the planet's edge for Italy).
      expect(lon).toBeLessThan(20);
      expect(lat).toBeGreaterThan(20);
    },
  );

  // Per-id land vs. sea sanity. The coastline runs roughly N-S between
  // lon 15.91 and 15.95 across the AOI; points with lon > 15.97 at
  // any of these latitudes are almost certainly in the bay. The
  // harbour pin is the only one that's allowed to sit "in the water"
  // because the port itself is the basin.
  const MAX_LANDSIDE_LON: Record<string, number> = {
    grotta_scaloria: 15.95,
    acqua_di_cristo: 15.95,
    lago_salso: 15.92,
    oasi_laguna_del_re: 15.93,
    sin_manfredonia: 15.96,
  };

  it.each(Object.entries(MAX_LANDSIDE_LON))(
    "%s sits west of lon %s (not adrift in the bay)",
    (id, maxLon) => {
      const h = CFG.highlights.find((entry) => entry.id === id);
      expect(h, `expected highlight ${id} to exist`).toBeDefined();
      if (!h) return;
      expect(h.coord[0]).toBeLessThan(maxLon);
    },
  );
});
