# Subplan — Storymap

> Sits inside `webapp/`; content lives in `content/it/slides/`.

## Slide model (recap, authoritative version is `SPECIFICATIONS.md` §11)

```yaml
---
id: 03_sin_enichem
title: "La SIN di Manfredonia"
camera: { center: [15.91, 41.62], zoom: 13.5, bearing: 0, pitch: 30 }
layers_visible: [sin_manfredonia, hydrography_underground, coastline]
highlights: [grotta_scaloria, acqua_di_cristo]
media:
  - type: image
    src: media/sin_aerial_2023.jpg
    alt: "Vista aerea dell'area SIN"
---
Italian markdown content here.
```

## Initial slide list (v1 — to be confirmed with user before authoring)

- [ ] `01_intro.md` — what this map is, the AOI, how to use it.
- [ ] `02_hydrography.md` — surface + underground waters; aquifers; risk.
- [ ] `03_sin_enichem.md` — the SIN site, history, current status.
- [ ] `04_wetlands.md` — Lago Salso, Oasi Laguna del Re, Natura 2000.
- [ ] `05_archeology.md` — Grotta Scaloria, Siponto, vincoli.
- [ ] `06_beaches.md` — Acqua di Cristo and the coast.
- [ ] `07_harbours_industry.md` — port, industrial areas, ASI.
- [ ] `08_mobility.md` — roads, cycle paths, walkable links.
- [ ] `09_outlook.md` — open questions, citizen-science possibilities.

## Engine choice (research)

- [ ] **Fork `mapbox/storytelling`** — fastest path to "good enough" but
      forces their HTML/CSS conventions.
- [ ] **Custom slide engine** — IntersectionObserver-based scroll triggers,
      drives a single GL map with `flyTo`. Cleaner home for our layer
      controls.

Default proposal: **custom**, kept thin (≤ 300 lines TS). Lock in research.

## Tasks

- [ ] Build engine + per-slide content rendering.
- [ ] Visited-slide bookmarking via URL hash (deep link to a slide).
- [ ] **Media support** (closes OPEN-MEDIA-1):
  - Images committed under `content/it/media/<slug>/`; lazy-loaded; alt-text
    required by schema.
  - YouTube videos embedded via `youtube-nocookie.com/embed/<id>` with
    `loading="lazy"` and a click-to-play poster so we do not hit YouTube
    on every page load (privacy + perf).
- [ ] Authoring docs in `content/it/README.md` (how to add a slide).

## Acceptance

- [ ] Storymap renders all v1 slides on mobile + desktop.
- [ ] Deep links open at the right slide and camera.
- [ ] Adding a new slide is a one-file Markdown edit; no code change required.
