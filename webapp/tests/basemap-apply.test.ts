import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CUSTOM_DEM_SOURCE_ID,
  MAPBOX_DEM_SOURCE_ID,
  applyBasemap,
  applyBasemapCamera,
  applyBasemapTerrain,
  customDemTilesUrl,
} from "../src/map/basemap-apply";
import type { BasemapEntry } from "../src/types";

/**
 * Each helper has a single side effect on the mapbox `Map`. We mock the
 * surface they actually touch so the tests stay deterministic without
 * booting Mapbox.
 */
function fakeMap(): {
  pitch: number;
  setPitch: ReturnType<typeof vi.fn>;
  getPitch: ReturnType<typeof vi.fn>;
  sources: Map<string, unknown>;
  addSource: ReturnType<typeof vi.fn>;
  getSource: ReturnType<typeof vi.fn>;
  setTerrain: ReturnType<typeof vi.fn>;
  terrain: unknown;
} {
  const sources = new Map<string, unknown>();
  const obj = {
    pitch: 0,
    terrain: null as unknown,
    sources,
    setPitch: vi.fn(),
    getPitch: vi.fn(),
    addSource: vi.fn(),
    getSource: vi.fn(),
    setTerrain: vi.fn(),
  };
  obj.setPitch.mockImplementation((p: number) => {
    obj.pitch = p;
  });
  obj.getPitch.mockImplementation(() => obj.pitch);
  obj.addSource.mockImplementation((id: string, source: unknown) => {
    sources.set(id, source);
  });
  obj.getSource.mockImplementation((id: string) => sources.get(id));
  obj.setTerrain.mockImplementation((t: unknown) => {
    obj.terrain = t;
  });
  return obj;
}

const STANDARD_3D: BasemapEntry = {
  id: "standard_3d",
  name_it: "Standard 3D",
  style_url: "mapbox://styles/mapbox/standard",
  pitch: 60,
};

const FLAT_DARK: BasemapEntry = {
  id: "dark",
  name_it: "Scuro",
  style_url: "mapbox://styles/mapbox/dark-v11",
  pitch: 0,
};

const OUTDOORS_TERRAIN: BasemapEntry = {
  id: "outdoors",
  name_it: "Outdoor",
  style_url: "mapbox://styles/mapbox/outdoors-v12",
  pitch: 45,
  terrain: true,
};

describe("applyBasemapCamera", () => {
  let map: ReturnType<typeof fakeMap>;
  beforeEach(() => {
    map = fakeMap();
  });

  it("calls setPitch for a basemap that declares one", () => {
    expect(applyBasemapCamera(map, STANDARD_3D)).toBe(true);
    expect(map.setPitch).toHaveBeenCalledWith(60);
  });

  it("returns false (and does not call setPitch) when no pitch is declared", () => {
    const noPitch: BasemapEntry = {
      id: "x",
      name_it: "x",
      style_url: "mapbox://styles/mapbox/light-v11",
    };
    expect(applyBasemapCamera(map, noPitch)).toBe(false);
    expect(map.setPitch).not.toHaveBeenCalled();
  });

  it("skips the setPitch call when the camera is already within 0.5° of target", () => {
    map.pitch = 60.2;
    applyBasemapCamera(map, STANDARD_3D);
    expect(map.setPitch).not.toHaveBeenCalled();
  });

  it("still applies the pitch when the diff exceeds the deadband", () => {
    map.pitch = 50;
    applyBasemapCamera(map, STANDARD_3D);
    expect(map.setPitch).toHaveBeenCalledWith(60);
  });

  it("flattens the camera when a basemap declares pitch 0", () => {
    map.pitch = 60;
    expect(applyBasemapCamera(map, FLAT_DARK)).toBe(true);
    expect(map.setPitch).toHaveBeenCalledWith(0);
  });
});

describe("applyBasemapTerrain", () => {
  let map: ReturnType<typeof fakeMap>;
  beforeEach(() => {
    map = fakeMap();
  });

  it("adds the Mapbox DEM source and enables terrain for `terrain: true`", () => {
    expect(applyBasemapTerrain(map, OUTDOORS_TERRAIN)).toBe("added-mapbox");
    expect(map.addSource).toHaveBeenCalledWith(
      MAPBOX_DEM_SOURCE_ID,
      expect.objectContaining({ type: "raster-dem" }),
    );
    expect(map.setTerrain).toHaveBeenCalledWith(
      expect.objectContaining({ source: MAPBOX_DEM_SOURCE_ID }),
    );
  });

  it("uses the basemap's custom `terrain_url` via lossless .pngraw tiles", () => {
    const lidar: BasemapEntry = {
      ...STANDARD_3D,
      terrain_url: "mapbox://marconasuto.manfredonia-terrain-rgb-v3",
      terrain_exaggeration: 1.5,
    };
    expect(applyBasemapTerrain(map, lidar, { accessToken: "pk.test" })).toBe("added-custom");
    const [, source] = map.addSource.mock.calls.find((c) => c[0] === CUSTOM_DEM_SOURCE_ID) ?? [];
    expect(source).toMatchObject({ type: "raster-dem", encoding: "mapbox" });
    // Must use the lossless `.pngraw` endpoint, not `url:` (which would
    // resolve to Mapbox's palette-quantised `.png` and corrupt the DEM).
    expect((source as { url?: string }).url).toBeUndefined();
    expect((source as { tiles: string[] }).tiles[0]).toContain(".pngraw");
    expect((source as { tiles: string[] }).tiles[0]).toContain("pk.test");
    expect(map.setTerrain).toHaveBeenCalledWith({
      source: CUSTOM_DEM_SOURCE_ID,
      exaggeration: 1.5,
    });
  });

  it("falls back to the global Mapbox DEM when no accessToken is supplied", () => {
    const lidar: BasemapEntry = {
      ...STANDARD_3D,
      terrain_url: "mapbox://marconasuto.x",
    };
    // Without a token we can't sign the .pngraw URL → use the global DEM
    // rather than mount a broken custom source.
    expect(applyBasemapTerrain(map, lidar)).toBe("added-mapbox");
    expect(map.setTerrain).toHaveBeenCalledWith(
      expect.objectContaining({ source: MAPBOX_DEM_SOURCE_ID }),
    );
  });

  it("custom `terrain_url` (with token) takes precedence over the global DEM", () => {
    const lidar: BasemapEntry = {
      ...OUTDOORS_TERRAIN,
      terrain_url: "mapbox://marconasuto.x",
    };
    applyBasemapTerrain(map, lidar, { accessToken: "pk.test" });
    const calls = map.addSource.mock.calls.map((c) => c[0] as string);
    expect(calls).toContain(CUSTOM_DEM_SOURCE_ID);
    expect(calls).not.toContain(MAPBOX_DEM_SOURCE_ID);
  });

  it("does not re-add the DEM source if it's already mounted", () => {
    map.sources.set(MAPBOX_DEM_SOURCE_ID, { type: "raster-dem" });
    applyBasemapTerrain(map, OUTDOORS_TERRAIN);
    expect(map.addSource).not.toHaveBeenCalled();
    expect(map.setTerrain).toHaveBeenCalled();
  });

  it("does not re-add the custom DEM source if it's already mounted", () => {
    map.sources.set(CUSTOM_DEM_SOURCE_ID, { type: "raster-dem" });
    const lidar: BasemapEntry = { ...STANDARD_3D, terrain_url: "mapbox://x.y" };
    applyBasemapTerrain(map, lidar, { accessToken: "pk.test" });
    expect(map.addSource).not.toHaveBeenCalled();
    expect(map.setTerrain).toHaveBeenCalled();
  });

  it("clears terrain when the basemap does not request it", () => {
    expect(applyBasemapTerrain(map, FLAT_DARK)).toBe("cleared");
    expect(map.setTerrain).toHaveBeenCalledWith(null);
  });

  it("clears terrain explicitly even when the basemap declares `terrain: false`", () => {
    const noTerrain: BasemapEntry = { ...OUTDOORS_TERRAIN, terrain: false };
    expect(applyBasemapTerrain(map, noTerrain)).toBe("cleared");
  });

  it("treats Standard 3D (no custom DEM) as cleared (Standard owns its own)", () => {
    expect(applyBasemapTerrain(map, STANDARD_3D)).toBe("cleared");
    expect(map.addSource).not.toHaveBeenCalled();
  });

  it("honours basemap.terrain_exaggeration when given", () => {
    applyBasemapTerrain(map, { ...OUTDOORS_TERRAIN, terrain_exaggeration: 2.0 });
    expect(map.setTerrain).toHaveBeenCalledWith(
      expect.objectContaining({ exaggeration: 2.0 }),
    );
  });

  it("returns 'noop' if the map surface has no setTerrain (older Mapbox)", () => {
    const stripped = { getSource: vi.fn(), addSource: vi.fn() };
    expect(applyBasemapTerrain(stripped, OUTDOORS_TERRAIN)).toBe("noop");
  });

  it("calls getSource/addSource bound to the map (regression: _isValidId)", () => {
    // Real Mapbox `Map` methods read `this._isValidId(...)` internally,
    // so the helper must not call a bare/destructured reference. This
    // fake throws if its methods are invoked with the wrong `this`.
    const realMap = {
      _added: new Map<string, unknown>(),
      _terrain: null as unknown,
      getSource(id: string) {
        if (this._added === undefined) throw new Error("getSource called unbound");
        return this._added.get(id);
      },
      addSource(id: string, src: unknown) {
        if (this._added === undefined) throw new Error("addSource called unbound");
        this._added.set(id, src);
      },
      setTerrain(t: unknown) {
        if (!("_terrain" in this)) throw new Error("setTerrain called unbound");
        this._terrain = t;
      },
    };
    const lidar: BasemapEntry = { ...STANDARD_3D, terrain_url: "mapbox://marconasuto.x" };
    expect(() =>
      applyBasemapTerrain(realMap as never, lidar, { accessToken: "pk.test" }),
    ).not.toThrow();
    expect(realMap._added.has(CUSTOM_DEM_SOURCE_ID)).toBe(true);
    expect(realMap._terrain).toMatchObject({ source: CUSTOM_DEM_SOURCE_ID });
  });
});

describe("customDemTilesUrl", () => {
  it("converts a mapbox:// tileset id into a signed .pngraw tiles URL", () => {
    const u = customDemTilesUrl("mapbox://marconasuto.manfredonia-terrain-rgb-v3", "pk.abc");
    expect(u).toBe(
      "https://api.mapbox.com/v4/marconasuto.manfredonia-terrain-rgb-v3/" +
        "{z}/{x}/{y}.pngraw?access_token=pk.abc",
    );
  });

  it("url-encodes the access token", () => {
    const u = customDemTilesUrl("mapbox://u.t", "pk a/b");
    expect(u).toContain("access_token=pk%20a%2Fb");
  });
});

describe("applyBasemap", () => {
  it("applies camera + terrain together", () => {
    const map = fakeMap();
    applyBasemap(map, OUTDOORS_TERRAIN);
    expect(map.setPitch).toHaveBeenCalledWith(45);
    expect(map.setTerrain).toHaveBeenCalledWith(
      expect.objectContaining({ source: MAPBOX_DEM_SOURCE_ID }),
    );
  });

  it("does not call setPitch when pitch is unset, but still touches terrain", () => {
    const map = fakeMap();
    const noPitch: BasemapEntry = {
      id: "x",
      name_it: "x",
      style_url: "mapbox://styles/mapbox/light-v11",
    };
    applyBasemap(map, noPitch);
    expect(map.setPitch).not.toHaveBeenCalled();
    expect(map.setTerrain).toHaveBeenCalledWith(null);
  });
});
