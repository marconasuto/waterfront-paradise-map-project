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

import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parse as parseYaml } from "yaml";

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

// Italian content (locations + slides + media). The tree may not exist
// yet (Phase 7); copy recursively when it does.
const CONTENT_SRC = join(REPO_ROOT, "content", "it");
const CONTENT_DST = join(WEBAPP_PUBLIC, "content", "it");
if (existsSync(CONTENT_SRC)) {
  cpSync(CONTENT_SRC, CONTENT_DST, { recursive: true });
  console.info(`[sync-config] ok    content/it/  -> public/content/it/  (recursive)`);
  buildSlideIndex(CONTENT_SRC, WEBAPP_PUBLIC);
} else {
  console.warn(`[sync-config] INFO  skip content/it/ (not yet authored — Phase 7)`);
  writeFileSync(join(WEBAPP_PUBLIC, "slides.json"), "[]\n");
}

if (missing > 0) {
  console.warn(
    `[sync-config] ${missing} required file(s) missing. The app may not render correctly.`,
  );
}

/**
 * Scan `<contentSrc>/slides/*.md`, parse YAML frontmatter from each
 * file, and write `<publicDir>/slides.json` as an ordered list of slide
 * metadata. The frontmatter shape mirrors plans/06_storymap.md:
 * `{ id, title, camera, layers_visible, highlights, media }`.
 *
 * Slides without frontmatter are skipped with a warning. The order is
 * by filename so `00_intro.md` → `99_outlook.md` naturally orders.
 */
function buildSlideIndex(contentSrc, publicDir) {
  const slidesDir = join(contentSrc, "slides");
  if (!existsSync(slidesDir)) {
    writeFileSync(join(publicDir, "slides.json"), "[]\n");
    console.warn(`[sync-config] INFO  skip slides.json (no content/it/slides/ yet)`);
    return;
  }
  const files = readdirSync(slidesDir)
    .filter((f) => f.toLowerCase().endsWith(".md"))
    .sort();
  const out = [];
  for (const f of files) {
    const md = readFileSync(join(slidesDir, f), "utf-8");
    const fm = extractFrontmatter(md);
    if (!fm) {
      console.warn(`[sync-config] WARN  skip slides/${f} (no YAML frontmatter)`);
      continue;
    }
    if (!fm.id) fm.id = f.replace(/\.md$/i, "");
    fm.body_ref = `slides/${f}`;
    out.push(fm);
  }
  writeFileSync(join(publicDir, "slides.json"), JSON.stringify(out, null, 2) + "\n");
  console.info(`[sync-config] ok    slides/ index -> public/slides.json  (${out.length} slides)`);
}

function extractFrontmatter(md) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(md);
  if (!match) return null;
  const parsed = parseYaml(match[1]);
  if (typeof parsed !== "object" || parsed === null) return null;
  return parsed;
}
