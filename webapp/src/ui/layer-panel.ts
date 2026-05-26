import type { LayerMeta } from "../config/catalog";
import type { LayerState } from "../state/layer-state";

export interface LayerPanelOptions {
  container: HTMLElement;
  state: LayerState[];
  meta: Map<string, LayerMeta>;
  /** Display label for a layer id. */
  label: (layerId: string) => string;
  /** Fired on visibility or opacity change. Caller decides how to persist + apply. */
  onChange: (next: LayerState[]) => void;
}

/**
 * Right-docked panel listing every overlay layer.
 *
 * Each row: checkbox (visibility) + opacity slider + small "info"
 * disclosure showing publisher / dataset / license / year from the
 * catalog. The panel owns the DOM; state is held by the caller and
 * pushed back in via `setState()` (e.g. after a basemap swap reapplies
 * the saved state).
 */
export class LayerPanel {
  private container: HTMLElement;
  private state: LayerState[];
  private readonly meta: Map<string, LayerMeta>;
  private readonly label: (layerId: string) => string;
  private readonly onChange: (next: LayerState[]) => void;

  constructor(opts: LayerPanelOptions) {
    this.container = opts.container;
    this.state = opts.state;
    this.meta = opts.meta;
    this.label = opts.label;
    this.onChange = opts.onChange;
    this.render();
  }

  /** Replace state and re-render. Use after basemap swap or external mutation. */
  setState(state: LayerState[]): void {
    this.state = state;
    this.render();
  }

  private render(): void {
    this.container.innerHTML = "";
    const heading = document.createElement("h2");
    heading.className = "layer-panel__title";
    heading.textContent = "Livelli";
    this.container.appendChild(heading);

    const list = document.createElement("ul");
    list.className = "layer-panel__list";
    list.setAttribute("role", "list");

    for (let i = 0; i < this.state.length; i++) {
      const entry = this.state[i];
      if (!entry) continue;
      list.appendChild(this.renderRow(entry, i));
    }
    this.container.appendChild(list);
  }

  private renderRow(entry: LayerState, index: number): HTMLLIElement {
    const li = document.createElement("li");
    li.className = "layer-panel__row";
    li.dataset["layerId"] = entry.layerId;

    const checkboxId = `layer-vis-${entry.layerId}`;
    const sliderId = `layer-op-${entry.layerId}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = checkboxId;
    checkbox.checked = entry.visible;
    checkbox.setAttribute("aria-label", `Mostra livello ${this.label(entry.layerId)}`);
    checkbox.addEventListener("change", () => {
      this.updateEntry(index, { visible: checkbox.checked });
    });

    const label = document.createElement("label");
    label.htmlFor = checkboxId;
    label.className = "layer-panel__label";
    label.textContent = this.label(entry.layerId);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = sliderId;
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = String(Math.round(entry.opacity * 100));
    slider.setAttribute("aria-label", `Opacità livello ${this.label(entry.layerId)}`);
    slider.addEventListener("input", () => {
      const pct = Number.parseInt(slider.value, 10);
      this.updateEntry(index, { opacity: pct / 100 });
    });

    const info = document.createElement("button");
    info.type = "button";
    info.className = "layer-panel__info";
    info.setAttribute("aria-label", `Informazioni sul livello ${this.label(entry.layerId)}`);
    info.textContent = "ⓘ";
    info.title = this.attributionTooltip(entry.layerId);

    li.appendChild(checkbox);
    li.appendChild(label);
    li.appendChild(slider);
    li.appendChild(info);
    return li;
  }

  private attributionTooltip(layerId: string): string {
    const m = this.meta.get(layerId);
    if (!m) return "Nessuna informazione di provenienza.";
    const yr = m.year !== null ? ` (${m.year})` : "";
    return `${m.dataset} — ${m.publisher}${yr}. Licenza: ${m.license}`;
  }

  private updateEntry(index: number, patch: Partial<LayerState>): void {
    const prev = this.state[index];
    if (!prev) return;
    const updated: LayerState = { ...prev, ...patch };
    this.state = this.state.map((e, i) => (i === index ? updated : e));
    this.onChange(this.state);
  }
}

/** Pretty-print a `manfredonia-*` layer id. */
export function defaultLayerLabel(layerId: string): string {
  return layerId.replace(/^manfredonia-/, "").replace(/_/g, " ");
}
