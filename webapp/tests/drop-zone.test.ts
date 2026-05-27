import { beforeEach, describe, expect, it, vi } from "vitest";

import { attachDropZone } from "../src/ui/drop-zone";

function dragEvent(type: string, files: File[] = []): DragEvent {
  const ev = new Event(type, { bubbles: true, cancelable: true }) as DragEvent;
  Object.defineProperty(ev, "dataTransfer", {
    value: {
      files,
      dropEffect: "none",
      effectAllowed: "all",
      types: [],
    },
  });
  return ev;
}

describe("attachDropZone", () => {
  let element: HTMLElement;

  beforeEach(() => {
    element = document.createElement("div");
    document.body.appendChild(element);
  });

  it("adds the active class on dragenter and removes it on dragleave", () => {
    attachDropZone({ element, onDrop: vi.fn() });
    element.dispatchEvent(dragEvent("dragenter"));
    expect(element.classList.contains("drop-zone--active")).toBe(true);
    element.dispatchEvent(dragEvent("dragleave"));
    expect(element.classList.contains("drop-zone--active")).toBe(false);
  });

  it("balances enter/leave depth so child elements do not flicker", () => {
    attachDropZone({ element, onDrop: vi.fn() });
    element.dispatchEvent(dragEvent("dragenter"));
    element.dispatchEvent(dragEvent("dragenter")); // child element entered
    element.dispatchEvent(dragEvent("dragleave")); // child left
    expect(element.classList.contains("drop-zone--active")).toBe(true);
    element.dispatchEvent(dragEvent("dragleave")); // parent left
    expect(element.classList.contains("drop-zone--active")).toBe(false);
  });

  it("fires onDrop once per file", () => {
    const onDrop = vi.fn();
    attachDropZone({ element, onDrop });
    const f1 = new File(["{}"], "a.geojson");
    const f2 = new File(["{}"], "b.geojson");
    element.dispatchEvent(dragEvent("drop", [f1, f2]));
    expect(onDrop).toHaveBeenCalledTimes(2);
    expect(onDrop).toHaveBeenNthCalledWith(1, f1);
    expect(onDrop).toHaveBeenNthCalledWith(2, f2);
  });

  it("clears the active class after a drop", () => {
    attachDropZone({ element, onDrop: vi.fn() });
    element.dispatchEvent(dragEvent("dragenter"));
    element.dispatchEvent(dragEvent("drop", [new File(["{}"], "x.geojson")]));
    expect(element.classList.contains("drop-zone--active")).toBe(false);
  });

  it("destroy detaches listeners (no further onDrop calls)", () => {
    const onDrop = vi.fn();
    const handle = attachDropZone({ element, onDrop });
    handle.destroy();
    element.dispatchEvent(dragEvent("drop", [new File(["{}"], "x.geojson")]));
    expect(onDrop).not.toHaveBeenCalled();
  });
});
