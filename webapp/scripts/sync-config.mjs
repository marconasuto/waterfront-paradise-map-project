#!/usr/bin/env node
/**
 * Copy pipeline outputs into webapp/public/ at dev/build time.
 *
 * The Python pipeline owns the canonical files under data/ and config/.
 * The webapp is a static site and can only load files from its own
 * publicDir, so we mirror what it needs here. Mirrors:
 *
 *   data/processed/style.json   -> public/style.json   (gitignored)
 *   data/catalog.yaml           -> public/catalog.yaml
 *   config/basemaps.yaml        -> public/basemaps.yaml
 *   config/highlights.yaml      -> public/highlights.yaml
 *   config/color_scheme.yaml    -> public/color_scheme.yaml
 *   config/layers.yaml          -> public/layers.yaml
 *
 * Missing files are logged as warnings (e.g. style.json may not exist
 * until `pixi run publish-style` has been run); the build still proceeds.
 */

import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..", "..");
const WEBAPP_PUBLIC = resolve(__dirname, "..", "public");

const MAPPINGS = [
  { src: "data/processed/style.json", dst: "style.json", required: true },
  { src: "data/catalog.yaml", dst: "catalog.yaml", required: false },
  { src: "config/basemaps.yaml", dst: "basemaps.yaml", required: true },
  { src: "config/highlights.yaml", dst: "highlights.yaml", required: true },
  { src: "config/color_scheme.yaml", dst: "color_scheme.yaml", required: true },
  { src: "config/layers.yaml", dst: "layers.yaml", required: true },
];

mkdirSync(WEBAPP_PUBLIC, { recursive: true });

let missing = 0;
for (const { src, dst, required } of MAPPINGS) {
  const absSrc = join(REPO_ROOT, src);
  const absDst = join(WEBAPP_PUBLIC, dst);
  if (!existsSync(absSrc)) {
    const level = required ? "WARN " : "INFO ";
    console.warn(`[sync-config] ${level} skip ${src} (not found)`);
    if (required) missing += 1;
    continue;
  }
  copyFileSync(absSrc, absDst);
  const { size } = statSync(absDst);
  console.info(`[sync-config] ok    ${src} -> public/${dst}  (${size} B)`);
}

if (missing > 0) {
  console.warn(
    `[sync-config] ${missing} required file(s) missing. The app may not render correctly.`,
  );
}
