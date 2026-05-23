# Research — CRS choices

> Resolves OPEN-CRS-1 in `SPECIFICATIONS.md`. Conclusions fold back into §7.

## Question

For analysis-grade buffering / distance / area near Manfredonia (≈ 41.6°N,
15.9°E), what is the right working CRS?

- **EPSG:32633** — WGS 84 / UTM zone 33N
- **EPSG:25833** — ETRS89 / UTM zone 33N (INSPIRE-aligned)

## Considerations

- Italian official data tends to ship in **ETRS89 / UTM 33N (25833)** for
  INSPIRE-aligned releases, but legacy datasets remain in **WGS84 / UTM 33N
  (32633)**. We will use whichever matches the dominant CRS of our sources.
- Difference between the two is sub-meter for any post-2000 epoch — does
  not affect map cartography, but matters for INSPIRE compliance.

## Decision

⏳ to be sealed after `docs/research/data_sources.md` enumerates the
predominant CRS across our actual sources.
