// Capture low-angle screenshots aimed at the Gargano hills (NW corner of
// the AOI, ~530 m) on each 3D basemap, to visually confirm relief.

import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const TARGET = process.argv[2] ?? "http://localhost:5173/";
const OUT = fileURLToPath(new URL("../.inspect/", import.meta.url));
mkdirSync(OUT, { recursive: true });
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(TARGET, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForFunction(() => !!window.__mfdMap, { timeout: 30000 });
await page.evaluate(() => new Promise((r) => { window.__mfdMap.once("idle", r); setTimeout(r, 8000); }));
await page.evaluate(() => document.getElementById("intro-curtain-close")?.click());

async function shoot(basemapId, label) {
  await page.evaluate((id) => {
    const sel = document.getElementById("basemap-select");
    if (sel && sel.value !== id) {
      sel.value = id;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }, basemapId);
  await page.waitForTimeout(2500);
  // Very low angle, camera south of the NW hills looking NNW at them.
  await page.evaluate(() => {
    window.__mfdMap.jumpTo({ center: [15.9, 41.6], zoom: 12.3, pitch: 84, bearing: -25 });
  });
  await page.evaluate(() => new Promise((r) => { window.__mfdMap.once("idle", r); setTimeout(r, 5000); }));
  const e = await page.evaluate(() => {
    const m = window.__mfdMap;
    const q = (ll) => {
      const v = m.queryTerrainElevation(ll, { exaggerated: true });
      return v == null ? null : +v.toFixed(0);
    };
    return {
      terrain: m.getTerrain(),
      hi: q([15.86, 41.66]),
      lo: q([15.95, 41.6]),
    };
  });
  console.log(`${label}: terrain=${JSON.stringify(e.terrain)} exaggerated hi=${e.hi}m lo=${e.lo}m`);
  await page.screenshot({ path: `${OUT}shoot_${basemapId}.png` });
  console.log(`  → .inspect/shoot_${basemapId}.png`);
}

await shoot("standard_3d", "Standard 3D");
await shoot("satellite_3d", "Satellite 3D");

await browser.close();
