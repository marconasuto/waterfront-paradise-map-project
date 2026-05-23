# Subplan — Web app

> Owns `webapp/`. Mapbox GL JS static app; storymap-aware.

## Research

- [ ] **Framework decision** (OPEN-WEB-1):
  - Vanilla TS + Vite — minimal, no framework lock-in.
  - Astro — content-first; markdown slides land natively; good for Italian.
  - SvelteKit — best DX for interactive UI.
  Default proposal: **Astro** (content-first matches our editing model);
  revisit after research.
- [ ] Map control libraries: built-in vs `mapbox-gl-controls`, custom panel.
- [ ] Drag-and-drop client parsing of `.geojson`, `.gpkg` (via `wa-sqlite` or
      a WASM build of GDAL), `.zip` shapefile (via `shpjs`).

## Implementation tasks

- [ ] Scaffold app, set token, render base map at AOI center.
- [ ] Build-time loader for `webapp/public/catalog.json` (copy of
      `data/catalog.yaml`) + `content/it/**`.
- [ ] **Layer panel**: visibility, opacity, drag-reorder, attribution chip
      showing publisher + year (from catalog).
- [ ] **Basemap switcher**: from `config/basemaps.yaml`.
- [ ] **Highlights**: from `config/highlights.yaml` with marker icons
      colored from `config/color_scheme.yaml`.
- [ ] **Popups**: feature data + linked content from
      `content/it/locations/<id>.md`.
- [ ] **Drag-and-drop overlay**: ephemeral client-side layers, never uploaded.
- [ ] **A11y**: keyboard navigation, focus rings, color contrast checked
      against the palette tokens.
- [ ] Build outputs to `webapp/dist/`; size budget < 2 MB JS gzipped.

## Acceptance

- [ ] All v1 layers render; popups show source year and publisher.
- [ ] Layer order is editable and persists in `localStorage`.
- [ ] Drag-and-drop accepts the three formats and shows useful errors on bad
      input.
- [ ] Lighthouse ≥ 90 (perf), ≥ 95 (a11y, best practices, SEO) on a fresh
      load.
