import type { LayerMeta } from "../config/catalog";
import { moveLayerStateEntry, type LayerState } from "../state/layer-state";

export interface LayerPanelOptions {
  container: HTMLElement;
  state: LayerState[];
  meta: Map<string, LayerMeta>;
  /** Display label for a layer id. */
  label: (layerId: string) => string;
  /** Fired on visibility / opacity / order change. */
  onChange: (next: LayerState[]) => void;
}

const DATA_KEY = "application/x-mfd-layer";

/**
 * Right-docked panel listing every overlay layer.
 *
 * Each row: drag handle (mouse + keyboard reorder), visibility checkbox,
 * label, opacity slider, attribution chip. The panel owns the DOM;
 * state is held by the caller and pushed back in via `setState()`
 * (e.g. after a basemap swap reapplies the saved state).
 */
export class LayerPanel {
  private container: HTMLElement;
  private state: LayerState[];
  private readonly meta: Map<string, LayerMeta>;
  private readonly label: (layerId: string) => string;
  private readonly onChange: (next: LayerState[]) => void;
  private dragFromIndex: number | null = null;

  constructor(opts: LayerPanelOptions) {
    this.container = opts.container;
    this.state = opts.state;
    this.meta = opts.meta;
    this.label = opts.label;
    this.onChange = opts.onChange;
    this.render();
  }

  /** Replace state and re-render. */
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
    li.dataset["index"] = String(index);

    const checkboxId = `layer-vis-${entry.layerId}`;
    const sliderId = `layer-op-${entry.layerId}`;

    // --- drag handle (also keyboard target) ---
    const handle = document.createElement("button");
    handle.type = "button";
    handle.className = "layer-panel__handle";
    handle.setAttribute(
      "aria-label",
      `Trascina per riordinare il livello ${this.label(entry.layerId)} (frecce su e giù)`,
    );
    handle.draggable = true;
    handle.textContent = "⋮⋮";
    handle.addEventListener("dragstart", (ev) => this.onDragStart(ev, index));
    handle.addEventListener("dragend", () => this.onDragEnd());
    handle.addEventListener("keydown", (ev) => this.onHandleKey(ev, index));

    // The row itself accepts drops so the user can drop anywhere over it.
    li.addEventListener("dragover", (ev) => this.onRowDragOver(ev, li));
    li.addEventListener("dragleave", () => li.classList.remove("layer-panel__row--drop-target"));
    li.addEventListener("drop", (ev) => this.onRowDrop(ev, index, li));

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

    li.appendChild(handle);
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

  // --- mutations -----------------------------------------------------

  private updateEntry(index: number, patch: Partial<LayerState>): void {
    const prev = this.state[index];
    if (!prev) return;
    const updated: LayerState = { ...prev, ...patch };
    this.state = this.state.map((e, i) => (i === index ? updated : e));
    this.onChange(this.state);
  }

  private moveEntry(from: number, to: number): void {
    const next = moveLayerStateEntry(this.state, from, to);
    if (next === this.state) return;
    this.state = next;
    this.onChange(this.state);
    // Focus the moved row's handle after re-render so keyboard nav can continue.
    queueMicrotask(() => {
      const moved = this.container.querySelector<HTMLElement>(
        `.layer-panel__row[data-index="${Math.max(0, Math.min(this.state.length - 1, to))}"] .layer-panel__handle`,
      );
      moved?.focus();
    });
  }

  // --- drag handlers -------------------------------------------------

  private onDragStart(ev: DragEvent, index: number): void {
    this.dragFromIndex = index;
    ev.dataTransfer?.setData(DATA_KEY, String(index));
    if (ev.dataTransfer) ev.dataTransfer.effectAllowed = "move";
    (ev.currentTarget as HTMLElement)?.closest(".layer-panel__row")?.classList.add(
      "layer-panel__row--dragging",
    );
  }

  private onDragEnd(): void {
    this.dragFromIndex = null;
    this.container
      .querySelectorAll(".layer-panel__row--dragging, .layer-panel__row--drop-target")
      .forEach((el) => {
        el.classList.remove("layer-panel__row--dragging");
        el.classList.remove("layer-panel__row--drop-target");
      });
  }

  private onRowDragOver(ev: DragEvent, row: HTMLElement): void {
    if (this.dragFromIndex === null) return;
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "move";
    row.classList.add("layer-panel__row--drop-target");
  }

  private onRowDrop(ev: DragEvent, dropIndex: number, row: HTMLElement): void {
    ev.preventDefault();
    row.classList.remove("layer-panel__row--drop-target");
    const fromStr = ev.dataTransfer?.getData(DATA_KEY) ?? "";
    const from = fromStr === "" ? this.dragFromIndex : Number.parseInt(fromStr, 10);
    if (from === null || Number.isNaN(from)) return;
    this.moveEntry(from, dropIndex);
  }

  private onHandleKey(ev: KeyboardEvent, index: number): void {
    if (ev.key === "ArrowUp") {
      ev.preventDefault();
      this.moveEntry(index, index - 1);
    } else if (ev.key === "ArrowDown") {
      ev.preventDefault();
      this.moveEntry(index, index + 1);
    }
  }
}

/** Pretty-print a `manfredonia-*` layer id. */
export function defaultLayerLabel(layerId: string): string {
  return layerId.replace(/^manfredonia-/, "").replace(/_/g, " ");
}
