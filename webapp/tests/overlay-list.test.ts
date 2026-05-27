import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OverlayHandle } from "../src/state/overlays";
import { OverlayList } from "../src/ui/overlay-list";

describe("OverlayList", () => {
  let container: HTMLDivElement;
  let onRemove: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    container = document.createElement("div");
    onRemove = vi.fn();
  });

  it("shows the empty-state hint when no overlays are present", () => {
    new OverlayList({ container, onRemove });
    const hint = container.querySelector(".overlay-list__hint");
    expect(hint).not.toBeNull();
    expect(hint!.textContent).toMatch(/Trascina/);
  });

  it("renders one row per overlay with name + feature count + swatch", () => {
    const list = new OverlayList({ container, onRemove });
    const overlays: OverlayHandle[] = [
      { id: "user-overlay-0", name: "a.geojson", color: "#abc", featureCount: 3 },
      { id: "user-overlay-1", name: "b.geojson", color: "#def", featureCount: 1 },
    ];
    list.setOverlays(overlays);
    const rows = container.querySelectorAll(".overlay-list__row");
    expect(rows).toHaveLength(2);
    expect(rows[0]!.textContent).toContain("a.geojson");
    expect(rows[0]!.textContent).toContain("(3)");
  });

  it("clicking remove calls onRemove with the overlay id", () => {
    const list = new OverlayList({ container, onRemove });
    list.setOverlays([
      { id: "user-overlay-7", name: "c.geojson", color: "#000", featureCount: 0 },
    ]);
    const btn = container.querySelector(".overlay-list__remove") as HTMLButtonElement;
    btn.click();
    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onRemove).toHaveBeenCalledWith("user-overlay-7");
  });

  it("setOverlays back to empty restores the hint", () => {
    const list = new OverlayList({ container, onRemove });
    list.setOverlays([
      { id: "user-overlay-0", name: "a", color: "#abc", featureCount: 0 },
    ]);
    list.setOverlays([]);
    expect(container.querySelector(".overlay-list__hint")).not.toBeNull();
  });
});
