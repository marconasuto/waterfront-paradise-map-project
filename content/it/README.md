# Contenuti italiani

Tutti i testi visibili nell'applicazione si trovano qui. Modificarli non richiede
toccare il codice.

## Struttura

- `slides/` — Le slide della storymap. Ogni file `.md` è una sezione che scorre nel
  pannello a sinistra. L'ordine alfabetico del nome file determina l'ordine sullo
  schermo, quindi i prefissi `00_`, `01_`, `02_` … sono il modo più semplice di
  ordinarle.
- `locations/` — Brevi schede legate agli highlight di `config/highlights.yaml`.
  Compaiono nei popup dei marker, una volta cliccati.
- `media/` — Immagini referenziate dalle slide o dalle locations.

## Formato delle slide

Ogni slide è un file Markdown con un blocco YAML in testa (frontmatter):

```yaml
---
id: 03_sin_enichem
title: "La SIN di Manfredonia"
camera: { center: [15.91, 41.62], zoom: 13.5, bearing: 0, pitch: 30 }
layers_visible: [sin_manfredonia, hydrography_surface, coastline]
highlights: [sin_manfredonia]
media:
  - type: image
    src: media/sin_aerial_2023.jpg
    alt: "Vista aerea dell'area SIN"
---

Qui inizia il corpo della slide in italiano. Markdown standard.
```

### Campi del frontmatter

- `id` — identificativo univoco (kebab-case o snake_case). Diventa l'ancora URL
  (`#slide-03_sin_enichem`). Se omesso si usa il nome file senza estensione.
- `title` — titolo mostrato in testa alla slide.
- `camera` — destinazione del `flyTo` quando la slide entra in vista.
  - `center` — `[lon, lat]` in WGS84.
  - `zoom` — 0 (mondo) … 22 (massimo).
  - `bearing` (opzionale) — rotazione in gradi (0 = nord in alto).
  - `pitch` (opzionale) — inclinazione 0–60 gradi.
- `layers_visible` (opzionale) — ID base dei livelli da mostrare (senza il
  prefisso `manfredonia-`). Tutti gli altri livelli vengono nascosti
  temporaneamente. Omettere = non cambiare lo stato dei livelli.
- `highlights` (opzionale) — ID degli highlight da evidenziare. Lasciato a future
  implementazioni.
- `media` (opzionale) — Lista di immagini/video; il rendering attuale è inline
  nel body, schede dedicate arriveranno in versioni successive.

## Formato delle locations

Stesso `loadContent` dei popup. Markdown puro: nessun frontmatter richiesto.

## Pubblicazione

Dopo aver modificato un file qui:

```bash
pixi run -e web web-build
```

Lo script `webapp/scripts/sync-config.mjs` copia ricorsivamente `content/it/`
in `webapp/public/content/it/` e genera `webapp/public/slides.json` con il
frontmatter di ciascuna slide.
