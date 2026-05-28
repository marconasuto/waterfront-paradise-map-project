/**
 * SVG path data for highlight-marker icons.
 *
 * Source: Phosphor Icons (https://phosphoricons.com), `regular` weight, MIT.
 * One inline path string per category; the marker shell renders the icon
 * inside a tinted circular badge. Phosphor strokes use `currentColor`, so
 * the marker can recolor the glyph from CSS without touching the SVG.
 *
 *   archeological → columns
 *   beach         → waves
 *   wetland       → plant
 *   harbour       → anchor
 *   industrial    → factory
 *   default       → map-pin
 */

export type MarkerIconName =
  | "archeological"
  | "beach"
  | "wetland"
  | "harbour"
  | "industrial"
  | "default";

/**
 * Inner SVG markup for each icon (no outer <svg> wrapper).
 * Trimmed to the strokes only; the wrapper sets viewBox + size at render time.
 */
export const MARKER_ICON_PATHS: Record<MarkerIconName, string> = {
  archeological:
    '<rect x="-4" y="100" width="176" height="56" rx="8" transform="translate(212 44) rotate(90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<rect x="84" y="100" width="176" height="56" rx="8" transform="translate(300 -44) rotate(90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
  beach:
    '<path d="M40,185.61c72-59.69,104,56.47,176-3.22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M40,129.61c72-59.69,104,56.47,176-3.22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M40,73.61c72-59.69,104,56.47,176-3.22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
  wetland:
    '<path d="M138.54,149.46C106.62,96.25,149.18,43.05,239.63,48.37,245,138.82,191.75,181.38,138.54,149.46Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M88.47,160.47c22.8-38-7.6-76-72.21-72.21C12.46,152.87,50.47,183.27,88.47,160.47Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<line x1="56" y1="128" x2="120" y2="192" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M200,88l-61.25,61.25A64,64,0,0,0,120,194.51V224" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
  harbour:
    '<line x1="128" y1="232" x2="128" y2="80" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<circle cx="128" cy="56" r="24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<line x1="88" y1="120" x2="168" y2="120" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M216,144c0,64-88,24-88,88,0-64-88-24-88-88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
  industrial:
    '<line x1="80" y1="176" x2="108" y2="176" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<line x1="148" y1="176" x2="176" y2="176" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<polyline points="216 136 168 136 104 88 104 136 40 88 40 216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<line x1="24" y1="216" x2="232" y2="216" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M153.55,125.16,167,30.87A8,8,0,0,1,174.94,24h18.12A8,8,0,0,1,201,30.87L216,136v80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
  default:
    '<circle cx="128" cy="104" r="32" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>' +
    '<path d="M208,104c0,72-80,128-80,128S48,176,48,104a80,80,0,0,1,160,0Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>',
};

const CATEGORY_TO_ICON: Record<string, MarkerIconName> = {
  archeological: "archeological",
  beach: "beach",
  wetland: "wetland",
  harbour: "harbour",
  industrial: "industrial",
  sin: "industrial",
};

/** Resolve a highlight category to the icon it should render with. */
export function iconForCategory(category: string): MarkerIconName {
  return CATEGORY_TO_ICON[category] ?? "default";
}
