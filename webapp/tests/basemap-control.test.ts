import { describe, expect, it, vi } from "vitest";

import { BasemapControl } from "../src/ui/basemap-control";
import type { BasemapEntry } from "../src/types";

const BASEMAPS: BasemapEntry[] = [
  { id: "light", name_it: "Chiaro", style_url: "mapbox://styles/mapbox/light-v11", default: true },
  { id: "sat", name_it: "Satellite", style_url: "mapbox://styles/mapbox/satellite-v9" },
];

describe("BasemapControl", () => {
  it("renders a <select> with one <option> per basemap", () => {
    const ctrl = new BasemapControl({ basemaps: BASEMAPS, initialId: "light", onChange: vi.fn() });
    const root = ctrl.onAdd({} as never);
    const select = root.querySelector("select") as HTMLSelectElement;
    expect(select).not.toBeNull();
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["light", "sat"]);
    expect(select.value).toBe("light");
  });

  it("fires onChange with the matching basemap entry on select change", () => {
    const onChange = vi.fn();
    const ctrl = new BasemapControl({ basemaps: BASEMAPS, initialId: "light", onChange });
    const root = ctrl.onAdd({} as never);
    const select = root.querySelector("select") as HTMLSelectElement;
    select.value = "sat";
    select.dispatchEvent(new Event("change"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(BASEMAPS[1]);
  });

  it("does not fire onChange when the selected id is unknown", () => {
    const onChange = vi.fn();
    const ctrl = new BasemapControl({ basemaps: BASEMAPS, initialId: "light", onChange });
    const root = ctrl.onAdd({} as never);
    const select = root.querySelector("select") as HTMLSelectElement;
    // Force an invalid value without going through the <option> list.
    Object.defineProperty(select, "value", { configurable: true, get: () => "nope" });
    select.dispatchEvent(new Event("change"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("setSelected updates the <select> programmatically", () => {
    const ctrl = new BasemapControl({ basemaps: BASEMAPS, initialId: "light", onChange: vi.fn() });
    const root = ctrl.onAdd({} as never);
    const select = root.querySelector("select") as HTMLSelectElement;
    ctrl.setSelected("sat");
    expect(select.value).toBe("sat");
  });

  it("onRemove detaches the element", () => {
    const ctrl = new BasemapControl({ basemaps: BASEMAPS, initialId: "light", onChange: vi.fn() });
    const root = ctrl.onAdd({} as never);
    document.body.appendChild(root);
    ctrl.onRemove();
    expect(document.body.contains(root)).toBe(false);
  });
});
