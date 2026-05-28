import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { parse as parseYaml } from "yaml";
import { describe, expect, it } from "vitest";

import type { BasemapsConfig, MapboxStyle } from "../src/types";

/**
 * Lock in the wiring that powers Phase 1 of the 3D-basemap plan
 * (see `plans/10_3d_basemap.md`):
 *
 *   1. `basemaps.yaml` ships a `standard_3d` entry, marked `default: true`,
 *      with `pitch: 60`.
 *   2. `style.json`'s `manfredonia-*` overlay layers all carry
 *      `slot: "middle"` so they render under labels in Mapbox Standard.
 *
 * Either piece silently regressing would make Standard "look broken"
 * without throwing — a UI-only failure that's easy to miss.
 */

const BASEMAPS_PATH = resolve(process.cwd(), "public/basemaps.yaml");
const STYLE_PATH = resolve(process.cwd(), "public/style.json");

const BASEMAPS = parseYaml(readFileSync(BASEMAPS_PATH, "utf-8")) as BasemapsConfig;
const STYLE = JSON.parse(readFileSync(STYLE_PATH, "utf-8")) as MapboxStyle;

describe("basemaps.yaml — Standard 3D wiring", () => {
  it("contains a `standard_3d` entry", () => {
    const ids = BASEMAPS.basemaps.map((b) => b.id);
    expect(ids).toContain("standard_3d");
  });

  it("standard_3d points at Mapbox's Standard style", () => {
    const std = BASEMAPS.basemaps.find((b) => b.id === "standard_3d");
    expect(std?.style_url).toBe("mapbox://styles/mapbox/standard");
  });

  it("standard_3d is the default basemap", () => {
    const defaults = BASEMAPS.basemaps.filter((b) => b.default === true);
    expect(defaults).toHaveLength(1);
    expect(defaults[0]?.id).toBe("standard_3d");
  });

  it("standard_3d declares a 3D camera pitch", () => {
    const std = BASEMAPS.basemaps.find((b) => b.id === "standard_3d");
    expect(std?.pitch).toBeGreaterThanOrEqual(45);
    expect(std?.pitch).toBeLessThanOrEqual(75);
  });

  it("standard_3d enables DEM terrain with a positive exaggeration", () => {
    const std = BASEMAPS.basemaps.find((b) => b.id === "standard_3d");
    // Uses Mapbox's global Terrain-DEM (terrain: true). A custom AOI-clipped
    // LIDAR raster-dem was tried but fights Mapbox's global tile pyramid —
    // see plans/10_3d_basemap.md.
    expect(std?.terrain).toBe(true);
    expect(std?.terrain_exaggeration).toBeGreaterThan(0);
  });

  it("satellite_3d combines satellite imagery with DEM terrain", () => {
    const sat = BASEMAPS.basemaps.find((b) => b.id === "satellite_3d");
    expect(sat).toBeDefined();
    expect(sat?.style_url).toMatch(/satellite/);
    expect(sat?.pitch).toBeGreaterThanOrEqual(45);
    expect(sat?.terrain).toBe(true);
  });

  it("every basemap with a pitch field has a sane value (0–85)", () => {
    for (const b of BASEMAPS.basemaps) {
      if (typeof b.pitch === "number") {
        expect(b.pitch).toBeGreaterThanOrEqual(0);
        expect(b.pitch).toBeLessThanOrEqual(85);
      }
    }
  });

  it("at least one non-Standard basemap opts into Mapbox DEM terrain", () => {
    const terrainBasemaps = BASEMAPS.basemaps.filter(
      (b) => b.terrain === true && b.id !== "standard_3d",
    );
    expect(terrainBasemaps.length).toBeGreaterThan(0);
  });
});

describe("style.json — slots", () => {
  const overlayLayers = STYLE.layers.filter((l) => l.id.startsWith("manfredonia-"));

  it("every `manfredonia-*` layer carries `slot: \"middle\"`", () => {
    expect(overlayLayers.length).toBeGreaterThan(0);
    for (const layer of overlayLayers) {
      expect((layer as { slot?: string }).slot).toBe("middle");
    }
  });

  it("the background layer does not get a slot (it's stripped at merge time)", () => {
    const bg = STYLE.layers.find((l) => l.id === "background");
    expect(bg).toBeDefined();
    expect((bg as { slot?: string }).slot).toBeUndefined();
  });
});
