import mapboxgl, { Map as MapboxMap, Marker, Popup } from "mapbox-gl";

import { loadContent } from "../content/loader";
import type { HighlightEntry, Palette } from "../types";

export interface HighlightOptions {
  highlights: HighlightEntry[];
  palette: Palette;
  /** Override the fetch implementation (used in tests). */
  fetchFn?: typeof fetch;
}

const PLACEHOLDER_HTML = "<p><em>Contenuto in arrivo.</em></p>";

/**
 * Drop an `mapboxgl.Marker` for each highlight, colored from the
 * palette via `style_token`. Clicks open a popup with the title, a
 * category badge, and an asynchronously-loaded markdown body.
 */
export function attachHighlights(map: MapboxMap, opts: HighlightOptions): Marker[] {
  const markers: Marker[] = [];
  for (const h of opts.highlights) {
    const color = opts.palette[h.style_token]?.fill ?? "#f8d030";
    const popup = new mapboxgl.Popup({ offset: 24, maxWidth: "320px" }).setHTML(
      placeholderPopup(h),
    );
    const marker = new mapboxgl.Marker({ color, anchor: "bottom" })
      .setLngLat(h.coord)
      .setPopup(popup)
      .addTo(map);
    void hydratePopup(popup, h, opts.fetchFn);
    markers.push(marker);
  }
  return markers;
}

/**
 * Initial HTML rendered while the markdown is still being fetched.
 * Carries title + category badge so the popup is useful even when
 * the content is missing or slow to load.
 */
export function placeholderPopup(h: HighlightEntry): string {
  return `
    <header class="highlight-popup__head">
      <span class="highlight-popup__chip" data-token="${escapeHtml(h.style_token)}">${escapeHtml(h.category)}</span>
      <h3 class="highlight-popup__title">${escapeHtml(h.name_it)}</h3>
    </header>
    <div class="highlight-popup__body">${PLACEHOLDER_HTML}</div>
  `;
}

/** Render the title + chip + actual markdown once it has loaded. */
export function loadedPopup(h: HighlightEntry, bodyHtml: string): string {
  return `
    <header class="highlight-popup__head">
      <span class="highlight-popup__chip" data-token="${escapeHtml(h.style_token)}">${escapeHtml(h.category)}</span>
      <h3 class="highlight-popup__title">${escapeHtml(h.name_it)}</h3>
    </header>
    <div class="highlight-popup__body">${bodyHtml}</div>
  `;
}

async function hydratePopup(
  popup: Popup,
  h: HighlightEntry,
  fetchFn?: typeof fetch,
): Promise<void> {
  const html = await loadContent(h.content_ref, fetchFn ?? fetch);
  popup.setHTML(loadedPopup(h, html ?? PLACEHOLDER_HTML));
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
