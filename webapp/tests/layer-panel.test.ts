import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LayerMeta } from "../src/config/catalog";
import type { LayerState } from "../src/state/layer-state";
import { LayerPanel, defaultLayerLabel } from "../src/ui/layer-panel";

const STATE: LayerState[] = [
  { layerId: "manfredonia-wetlands", visible: true, opacity: 0.6 },
  { layerId: "manfredonia-coastline", visible: false, opacity: 1 },
];

const META = new Map<string, LayerMeta>([
  [
    "manfredonia-wetlands",
    {
      layer_id: "manfredonia-wetlands",
      layer_type: "vector",
      feature_count: 12,
      publisher: "OSM contributors",
      dataset: "OSM wetlands",
      license: "ODbL-1.0",
      year: null,
    },
  ],
  [
    "manfredonia-coastline",
    {
      layer_id: "manfredonia-coastline",
      layer_type: "vector",
      feature_count: 4,
      publisher: "ISPRA",
      dataset: "Coastline",
      license: "CC-BY-4.0",
      year: 2024,
    },
  ],
]);

describe("LayerPanel", () => {
  let container: HTMLDivElement;
  let onChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    container = document.createElement("div");
    onChange = vi.fn();
  });

  it("renders one row per state entry, with checkbox + slider + info", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const rows = container.querySelectorAll(".layer-panel__row");
    expect(rows).toHaveLength(2);
    const first = rows[0] as HTMLLIElement;
    expect(first.dataset["layerId"]).toBe("manfredonia-wetlands");
    expect(first.querySelector('input[type="checkbox"]')).not.toBeNull();
    expect(first.querySelector('input[type="range"]')).not.toBeNull();
    expect(first.querySelector(".layer-panel__info")).not.toBeNull();
  });

  it("checkbox change fires onChange with the toggled entry", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const cbx = container.querySelector(
      '#layer-vis-manfredonia-wetlands',
    ) as HTMLInputElement;
    cbx.checked = false;
    cbx.dispatchEvent(new Event("change"));
    expect(onChange).toHaveBeenCalledTimes(1);
    const arg = onChange.mock.calls[0]![0] as LayerState[];
    expect(arg[0]).toEqual({ layerId: "manfredonia-wetlands", visible: false, opacity: 0.6 });
    expect(arg[1]).toEqual(STATE[1]);
  });

  it("slider input fires onChange with the new opacity (0-1)", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const slider = container.querySelector(
      '#layer-op-manfredonia-coastline',
    ) as HTMLInputElement;
    slider.value = "25";
    slider.dispatchEvent(new Event("input"));
    expect(onChange).toHaveBeenCalledTimes(1);
    const arg = onChange.mock.calls[0]![0] as LayerState[];
    expect(arg[1]!.opacity).toBeCloseTo(0.25);
  });

  it("info button title carries publisher + license + year", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const info = container.querySelector(
      '.layer-panel__row[data-layer-id="manfredonia-coastline"] .layer-panel__info',
    ) as HTMLButtonElement;
    expect(info.title).toContain("ISPRA");
    expect(info.title).toContain("2024");
    expect(info.title).toContain("CC-BY-4.0");
  });

  it("info button shows fallback when meta is missing", () => {
    const stateUnknown: LayerState[] = [
      { layerId: "manfredonia-mystery", visible: true, opacity: 1 },
    ];
    new LayerPanel({
      container,
      state: stateUnknown,
      meta: META,
      label: defaultLayerLabel,
      onChange,
    });
    const info = container.querySelector(".layer-panel__info") as HTMLButtonElement;
    expect(info.title).toMatch(/provenienza/i);
  });

  it("setState re-renders with the new state", () => {
    const panel = new LayerPanel({
      container,
      state: STATE,
      meta: META,
      label: defaultLayerLabel,
      onChange,
    });
    panel.setState([{ layerId: "manfredonia-coastline", visible: true, opacity: 0.1 }]);
    const rows = container.querySelectorAll(".layer-panel__row");
    expect(rows).toHaveLength(1);
    expect((rows[0] as HTMLLIElement).dataset["layerId"]).toBe("manfredonia-coastline");
  });

  it("defaultLayerLabel strips the manfredonia- prefix and underscores", () => {
    expect(defaultLayerLabel("manfredonia-hydrography_surface")).toBe("hydrography surface");
  });

  // --- drag + keyboard reorder -------------------------------------

  it("ArrowDown on a handle moves the entry down by one", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const handle = container.querySelector(
      '.layer-panel__row[data-index="0"] .layer-panel__handle',
    ) as HTMLButtonElement;
    handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(onChange).toHaveBeenCalledTimes(1);
    const arg = onChange.mock.calls[0]![0] as LayerState[];
    expect(arg.map((e) => e.layerId)).toEqual([
      "manfredonia-coastline",
      "manfredonia-wetlands",
    ]);
  });

  it("ArrowUp on the first handle is a no-op", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const handle = container.querySelector(
      '.layer-panel__row[data-index="0"] .layer-panel__handle',
    ) as HTMLButtonElement;
    handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("ArrowDown on the last handle is a no-op", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const handle = container.querySelector(
      '.layer-panel__row[data-index="1"] .layer-panel__handle',
    ) as HTMLButtonElement;
    handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("renders draggable handles with an aria-label", () => {
    new LayerPanel({ container, state: STATE, meta: META, label: defaultLayerLabel, onChange });
    const handles = container.querySelectorAll<HTMLButtonElement>(".layer-panel__handle");
    expect(handles).toHaveLength(STATE.length);
    expect(handles[0]!.draggable).toBe(true);
    expect(handles[0]!.getAttribute("aria-label")).toMatch(/Trascina/);
  });
});
