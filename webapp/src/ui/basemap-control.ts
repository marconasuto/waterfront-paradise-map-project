import type { IControl, Map as MapboxMap } from "mapbox-gl";

import type { BasemapEntry } from "../types";

export interface BasemapControlOptions {
  basemaps: BasemapEntry[];
  initialId: string;
  onChange: (basemap: BasemapEntry) => void | Promise<void>;
}

/**
 * Mapbox custom control: a small <select> that lets the user swap the
 * underlying basemap. The actual style swap is delegated to `onChange`
 * so this control stays purely about UI.
 */
export class BasemapControl implements IControl {
  private container: HTMLDivElement | null = null;
  private select: HTMLSelectElement | null = null;

  constructor(private readonly opts: BasemapControlOptions) {}

  /** Required by IControl. Returns the DOM node Mapbox will mount. */
  onAdd(_map: MapboxMap): HTMLElement {
    const root = document.createElement("div");
    root.className = "mapboxgl-ctrl mapboxgl-ctrl-group basemap-control";
    root.style.padding = "4px 6px";

    const label = document.createElement("label");
    label.htmlFor = "basemap-select";
    label.textContent = "Sfondo: ";
    label.style.fontSize = "12px";

    const sel = document.createElement("select");
    sel.id = "basemap-select";
    sel.setAttribute("aria-label", "Cambia sfondo della mappa");
    for (const b of this.opts.basemaps) {
      const opt = document.createElement("option");
      opt.value = b.id;
      opt.textContent = b.name_it;
      if (b.id === this.opts.initialId) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => {
      const next = this.opts.basemaps.find((b) => b.id === sel.value);
      if (next) void this.opts.onChange(next);
    });

    label.appendChild(sel);
    root.appendChild(label);
    this.container = root;
    this.select = sel;
    return root;
  }

  /** Required by IControl. Detach from the DOM. */
  onRemove(): void {
    this.container?.remove();
    this.container = null;
    this.select = null;
  }

  /** Programmatic update (e.g. after a deep-link hash sets the basemap). */
  setSelected(id: string): void {
    if (this.select) this.select.value = id;
  }
}
