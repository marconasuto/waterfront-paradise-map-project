/**
 * Lightweight drag-and-drop file zone.
 *
 * Attaches DOM listeners to `element` so the user can drop GeoJSON
 * files anywhere on the map. The visible state ("drop active") is
 * applied as a CSS class on the element. The drop callback receives
 * every dropped file individually; ignored types should be filtered
 * by the caller.
 */

export interface DropZoneOptions {
  element: HTMLElement;
  onDrop: (file: File) => void | Promise<void>;
  /** CSS class toggled while a drag is hovering over the element. */
  activeClass?: string;
}

export interface DropZoneHandle {
  destroy: () => void;
}

export function attachDropZone(opts: DropZoneOptions): DropZoneHandle {
  const cls = opts.activeClass ?? "drop-zone--active";
  let depth = 0;

  const onEnter = (ev: DragEvent): void => {
    ev.preventDefault();
    depth += 1;
    opts.element.classList.add(cls);
  };
  const onLeave = (ev: DragEvent): void => {
    ev.preventDefault();
    depth = Math.max(0, depth - 1);
    if (depth === 0) opts.element.classList.remove(cls);
  };
  const onOver = (ev: DragEvent): void => {
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "copy";
  };
  const onDrop = (ev: DragEvent): void => {
    ev.preventDefault();
    depth = 0;
    opts.element.classList.remove(cls);
    const dt = ev.dataTransfer;
    if (!dt) return;
    for (const file of Array.from(dt.files)) {
      void opts.onDrop(file);
    }
  };

  opts.element.addEventListener("dragenter", onEnter);
  opts.element.addEventListener("dragleave", onLeave);
  opts.element.addEventListener("dragover", onOver);
  opts.element.addEventListener("drop", onDrop);

  return {
    destroy: () => {
      opts.element.removeEventListener("dragenter", onEnter);
      opts.element.removeEventListener("dragleave", onLeave);
      opts.element.removeEventListener("dragover", onOver);
      opts.element.removeEventListener("drop", onDrop);
    },
  };
}
