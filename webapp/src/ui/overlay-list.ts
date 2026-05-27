import type { OverlayHandle } from "../state/overlays";

export interface OverlayListOptions {
  container: HTMLElement;
  onRemove: (id: string) => void;
}

/**
 * Tiny widget that shows one chip per ephemeral overlay with a "✕"
 * remove button. Re-renders on every `setOverlays()` call so we never
 * worry about partial DOM updates.
 */
export class OverlayList {
  private overlays: OverlayHandle[] = [];

  constructor(private readonly opts: OverlayListOptions) {
    this.render();
  }

  setOverlays(overlays: OverlayHandle[]): void {
    this.overlays = overlays;
    this.render();
  }

  private render(): void {
    this.opts.container.innerHTML = "";
    if (this.overlays.length === 0) {
      const hint = document.createElement("p");
      hint.className = "overlay-list__hint";
      hint.textContent = "Trascina un file .geojson sulla mappa per aggiungerlo.";
      this.opts.container.appendChild(hint);
      return;
    }
    const ul = document.createElement("ul");
    ul.className = "overlay-list";
    for (const o of this.overlays) {
      const li = document.createElement("li");
      li.className = "overlay-list__row";

      const swatch = document.createElement("span");
      swatch.className = "overlay-list__swatch";
      swatch.style.background = o.color;
      swatch.setAttribute("aria-hidden", "true");

      const name = document.createElement("span");
      name.className = "overlay-list__name";
      name.textContent = `${o.name} (${o.featureCount})`;

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "overlay-list__remove";
      remove.setAttribute("aria-label", `Rimuovi overlay ${o.name}`);
      remove.textContent = "✕";
      remove.addEventListener("click", () => this.opts.onRemove(o.id));

      li.appendChild(swatch);
      li.appendChild(name);
      li.appendChild(remove);
      ul.appendChild(li);
    }
    this.opts.container.appendChild(ul);
  }
}
