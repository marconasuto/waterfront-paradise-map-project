import mapboxgl, { Map as MapboxMap, Marker, Popup } from "mapbox-gl";

import { loadContent } from "../content/loader";
import type { HighlightEntry, Palette } from "../types";

import { MARKER_ICON_PATHS, iconForCategory } from "./icons/marker-icons";

export interface HighlightOptions {
  highlights: HighlightEntry[];
  palette: Palette;
  /** Override the fetch implementation (used in tests). */
  fetchFn?: typeof fetch;
}

const PLACEHOLDER_HTML = "<p><em>Contenuto in arrivo.</em></p>";

/**
 * Drop a custom `mapboxgl.Marker` for each highlight. Each marker is a
 * tinted Phosphor icon picked by `category` (cf. `iconForCategory`).
 * Clicks open a popup with the title, a category badge, and an
 * asynchronously-loaded markdown body.
 */
export function attachHighlights(map: MapboxMap, opts: HighlightOptions): Marker[] {
  const markers: Marker[] = [];
  for (const h of opts.highlights) {
    const popup = new mapboxgl.Popup({ offset: 30, maxWidth: "320px" }).setHTML(
      placeholderPopup(h),
    );
    const element = renderMarkerElement(h);
    const marker = new mapboxgl.Marker({ element, anchor: "bottom" })
      .setLngLat(h.coord)
      .setPopup(popup)
      .addTo(map);
    void hydratePopup(popup, h, opts.fetchFn);
    markers.push(marker);
  }
  return markers;
}

/**
 * Build the DOM node Mapbox mounts as a marker. A button so it's
 * keyboard-focusable; the actual click → popup wiring is owned by
 * Mapbox via `setPopup()`.
 */
export function renderMarkerElement(h: HighlightEntry): HTMLElement {
  const root = document.createElement("button");
  root.type = "button";
  root.className = "highlight-marker";
  root.dataset["category"] = h.category;
  root.dataset["styleToken"] = h.style_token;
  root.setAttribute("aria-label", `${h.name_it} (${h.category})`);
  root.innerHTML = renderMarkerSvg(h.category);
  return root;
}

/**
 * Inline SVG for a marker. Glyph stroke uses `currentColor` so CSS can
 * recolor it. The marker pin (bottom point) is part of the SVG so the
 * `anchor: "bottom"` Mapbox option lines up with the geographic point.
 */
export function renderMarkerSvg(category: string): string {
  const iconName = iconForCategory(category);
  const innerPath = MARKER_ICON_PATHS[iconName];
  return (
    '<svg class="highlight-marker__svg" viewBox="0 0 256 320" width="44" height="55" ' +
    'aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">' +
    // Backdrop: tear-drop pin shape, filled with the brand cyan at 50% alpha.
    '<path class="highlight-marker__backdrop" d="M128 8c66.3 0 120 53.7 120 120 0 90-120 184-120 184S8 218 8 128C8 61.7 61.7 8 128 8z" />' +
    // Inner translucent disc for legibility on busy basemaps.
    '<circle class="highlight-marker__inner" cx="128" cy="128" r="92" />' +
    // Glyph: nested SVG keeps the icon's 0-256 viewBox intact.
    '<svg x="64" y="64" width="128" height="128" viewBox="0 0 256 256" class="highlight-marker__glyph">' +
    innerPath +
    "</svg>" +
    "</svg>"
  );
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
