// Headless inspection of the running dev server.
// Loads the app in system Chrome, waits for the map, then reports:
//   - console errors / warnings
//   - terrain state (map.getTerrain())
//   - whether the DEM source + tiles loaded
//   - overlay layer visibility before/after a toggle
//   - screenshots at a low pitch for visual confirmation
//
// Usage: node scripts/inspect-map.mjs [url]

import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const TARGET = process.argv[2] ?? "http://localhost:5173/";
const OUT = fileURLToPath(new URL("../.inspect/", import.meta.url));
mkdirSync(OUT, { recursive: true });

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function log(...a) {
  console.log("[inspect]", ...a);
}

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: [
    "--enable-unsafe-swiftshader",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--ignore-gpu-blocklist",
  ],
});

const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

const consoleMsgs = [];
page.on("console", (m) => {
  const t = m.type();
  if (t === "error" || t === "warning") consoleMsgs.push(`${t}: ${m.text()}`);
});
page.on("pageerror", (e) => consoleMsgs.push(`pageerror: ${e.message}`));

log("loading", TARGET);
await page.goto(TARGET, { waitUntil: "networkidle", timeout: 60000 });

// Wait for the map object + first idle.
await page.waitForFunction(() => !!window.__mfdMap, { timeout: 30000 });
await page.evaluate(
  () =>
    new Promise((res) => {
      const m = window.__mfdMap;
      if (m.loaded() && m.isStyleLoaded()) return res();
      m.once("idle", res);
      setTimeout(res, 8000);
    }),
);
// Dismiss the intro curtain so it doesn't cover the map.
await page.evaluate(() => {
  document.getElementById("intro-curtain-close")?.click();
});
await page.waitForTimeout(2500);

async function snapshot(label) {
  return page.evaluate(() => {
    const m = window.__mfdMap;
    const terrain = m.getTerrain ? m.getTerrain() : "no getTerrain";
    const style = m.getStyle();
    const sourceIds = Object.keys(style.sources || {});
    const demSources = sourceIds.filter(
      (id) => style.sources[id].type === "raster-dem",
    );
    // Layer visibility for our overlays.
    const overlays = (style.layers || [])
      .filter((l) => l.id.startsWith("manfredonia-"))
      .map((l) => {
        let vis = "?";
        try {
          vis = m.getLayoutProperty(l.id, "visibility") ?? "visible";
        } catch {
          vis = "ERR";
        }
        return { id: l.id, slot: l.slot ?? null, vis };
      });
    // Is the DEM source's tiles actually loaded?
    let demLoaded = null;
    if (demSources.length) {
      try {
        demLoaded = m.isSourceLoaded(demSources[0]);
      } catch {
        demLoaded = "ERR";
      }
    }
    return {
      pitch: m.getPitch(),
      zoom: +m.getZoom().toFixed(2),
      terrain,
      demSources,
      demLoaded,
      overlayCount: overlays.length,
      overlaysSample: overlays.slice(0, 4),
      hiddenOverlays: overlays.filter((o) => o.vis === "none").map((o) => o.id),
    };
  });
}

log("=== INITIAL (default basemap = standard_3d) ===");
const init = await snapshot();
console.log(JSON.stringify(init, null, 2));

log("=== STYLE STRUCTURE ===");
const structure = await page.evaluate(() => {
  const m = window.__mfdMap;
  const style = m.getStyle();
  const allLayerIds = (style.layers || []).map((l) => l.id);
  const allSourceIds = Object.keys(style.sources || {});
  return {
    imports: (style.imports || []).map((i) => ({ id: i.id, url: i.url })),
    rootLayerCount: allLayerIds.length,
    rootLayerIds: allLayerIds,
    rootSourceIds: allSourceIds,
    manfredoniaSources: allSourceIds.filter((s) => s.startsWith("manfredonia-")),
    // Probe via getLayer (which resolves into imports too in v3).
    getLayerProbe: ["manfredonia-coastline", "manfredonia-wetlands"].map((id) => ({
      id,
      exists: !!m.getLayer(id),
    })),
  };
});
console.log(JSON.stringify(structure, null, 2));

// Query the terrain MESH elevation at known points — the definitive
// proof the DEM is feeding the 3D engine. The Gargano rises inland
// (NW); the coast/sea should be ~0 m.
async function terrainProbe() {
  return page.evaluate(() => {
    const m = window.__mfdMap;
    const pts = {
      sea: [16.02, 41.6],
      coast_port: [15.92, 41.628],
      inland_hill_nw: [15.87, 41.66],
      inland_far_nw: [15.84, 41.68],
    };
    const out = {};
    for (const [k, ll] of Object.entries(pts)) {
      const e = m.queryTerrainElevation
        ? m.queryTerrainElevation(ll, { exaggerated: false })
        : null;
      out[k] = e == null ? null : +e.toFixed(1);
    }
    return out;
  });
}

// Move to a low oblique angle looking NW toward the hills.
await page.evaluate(() => {
  const m = window.__mfdMap;
  m.jumpTo({ center: [15.92, 41.63], zoom: 12, pitch: 78, bearing: -55 });
});
await page.waitForTimeout(3500);
await page.screenshot({ path: `${OUT}01_standard3d_lowangle.png` });
log("screenshot → .inspect/01_standard3d_lowangle.png");
const lowAngle = await snapshot();
console.log("low-angle terrain:", JSON.stringify(lowAngle.terrain), "demLoaded:", lowAngle.demLoaded);
log("=== TERRAIN ELEVATION PROBE (m, unexaggerated) ===");
console.log(JSON.stringify(await terrainProbe(), null, 2));

// Toggle the first overlay layer off, check it actually hides.
const toggleResult = await page.evaluate(async () => {
  const before = [];
  const after = [];
  const m = window.__mfdMap;
  // Find the first visibility checkbox in the layer panel.
  const cb = document.querySelector('#layer-panel-list input[type="checkbox"]');
  const layerId = cb
    ? cb.id.replace(/^layer-vis-/, "")
    : null;
  const vis = (id) => {
    try {
      return m.getLayoutProperty(id, "visibility") ?? "visible";
    } catch {
      return "ERR";
    }
  };
  if (layerId) before.push({ layerId, vis: vis(layerId), checked: cb.checked });
  cb?.click();
  await new Promise((r) => setTimeout(r, 600));
  if (layerId) after.push({ layerId, vis: vis(layerId), checked: cb.checked });
  return { layerId, before, after };
});
log("=== LAYER TOGGLE TEST ===");
console.log(JSON.stringify(toggleResult, null, 2));

log("=== CONSOLE (errors/warnings) ===");
console.log(consoleMsgs.length ? consoleMsgs.join("\n") : "(none)");

await browser.close();
log("done. artifacts in", OUT);
