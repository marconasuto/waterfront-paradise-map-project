import { describe, expect, it, vi } from "vitest";

import type { SlideMeta } from "../src/content/slides";
import type { LayerState } from "../src/state/layer-state";
import { applySlide, deriveSlideState } from "../src/state/story-controller";

const BASELINE: LayerState[] = [
  { layerId: "manfredonia-coastline", visible: true, opacity: 1 },
  { layerId: "manfredonia-wetlands", visible: true, opacity: 0.5 },
  { layerId: "manfredonia-roads", visible: false, opacity: 0.8 },
];

describe("deriveSlideState", () => {
  it("returns baseline unchanged when layers_visible is missing", () => {
    expect(deriveSlideState(BASELINE, undefined)).toEqual(BASELINE);
  });

  it("returns baseline unchanged when layers_visible is empty", () => {
    expect(deriveSlideState(BASELINE, [])).toEqual(BASELINE);
  });

  it("hides everything not in the list while preserving opacity", () => {
    const out = deriveSlideState(BASELINE, ["coastline"]);
    expect(out).toEqual([
      { layerId: "manfredonia-coastline", visible: true, opacity: 1 },
      { layerId: "manfredonia-wetlands", visible: false, opacity: 0.5 },
      { layerId: "manfredonia-roads", visible: false, opacity: 0.8 },
    ]);
  });

  it("prefixes the bare ids with `manfredonia-`", () => {
    const out = deriveSlideState(BASELINE, ["wetlands", "roads"]);
    expect(out.find((s) => s.layerId === "manfredonia-wetlands")!.visible).toBe(true);
    expect(out.find((s) => s.layerId === "manfredonia-coastline")!.visible).toBe(false);
  });
});

describe("applySlide", () => {
  it("calls flyTo with the slide camera and pushes the derived state to the map", () => {
    const slide: SlideMeta = {
      id: "x",
      title: "X",
      body_ref: "slides/x.md",
      camera: { center: [15, 41], zoom: 12, bearing: 30, pitch: 45 },
      layers_visible: ["coastline"],
    };
    const flyTo = vi.fn();
    const getLayer = vi.fn((id: string) => ({ id, type: id.endsWith("roads") ? "line" : "fill" }));
    const setLayoutProperty = vi.fn();
    const setPaintProperty = vi.fn();
    const map = { getLayer, setLayoutProperty, setPaintProperty } as never;

    const out = applySlide({ map, baseline: BASELINE, slide, flyTo });

    expect(flyTo).toHaveBeenCalledWith(slide.camera);
    expect(out.find((s) => s.layerId === "manfredonia-coastline")!.visible).toBe(true);
    expect(setLayoutProperty).toHaveBeenCalledWith(
      "manfredonia-wetlands",
      "visibility",
      "none",
    );
  });

  it("defaults bearing+pitch to 0 when omitted (real flyTo path)", () => {
    const slide: SlideMeta = {
      id: "y",
      title: "Y",
      body_ref: "slides/y.md",
      camera: { center: [15, 41], zoom: 12 },
    };
    const flyTo = vi.fn();
    const map = {
      flyTo: (cam: { bearing?: number; pitch?: number }) => flyTo(cam),
      getLayer: () => undefined,
      setLayoutProperty: vi.fn(),
      setPaintProperty: vi.fn(),
    } as never;
    applySlide({ map, baseline: BASELINE, slide });
    const arg = flyTo.mock.calls[0]![0] as { bearing: number; pitch: number };
    expect(arg.bearing).toBe(0);
    expect(arg.pitch).toBe(0);
  });
});
