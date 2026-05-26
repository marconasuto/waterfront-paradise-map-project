import { loadBasemaps } from "./config/loader";
import { loadEnv } from "./env";
import { initMap } from "./map/init";
import {
  fetchBasemapStyle,
  mergeOverlay,
  pickDefaultBasemap,
} from "./map/style-merge";
import { loadStyle, styleLayerCount, styleSourceCount } from "./map/style-loader";
import { BasemapControl } from "./ui/basemap-control";

async function main(): Promise<void> {
  const container = document.getElementById("map");
  if (!container) {
    throw new Error("#map container not found in index.html");
  }
  const env = loadEnv();

  const [overlay, basemapsCfg] = await Promise.all([
    loadStyle("/style.json"),
    loadBasemaps("/basemaps.yaml"),
  ]);
  console.info(
    `[manfredonia-map] overlay: ${styleSourceCount(overlay)} sources, ${styleLayerCount(overlay)} layers; ${basemapsCfg.basemaps.length} basemaps`,
  );

  const initialBasemap = pickDefaultBasemap(basemapsCfg.basemaps);
  const initialBase = await fetchBasemapStyle(initialBasemap, env.mapboxPublicToken);
  const map = initMap({ container, style: mergeOverlay(initialBase, overlay), env });

  const switcher = new BasemapControl({
    basemaps: basemapsCfg.basemaps,
    initialId: initialBasemap.id,
    onChange: async (next) => {
      try {
        const base = await fetchBasemapStyle(next, env.mapboxPublicToken);
        map.setStyle(mergeOverlay(base, overlay));
      } catch (err) {
        console.error("[manfredonia-map] basemap swap failed:", err);
      }
    },
  });
  map.addControl(switcher, "top-left");
}

main().catch((err: unknown) => {
  console.error("[manfredonia-map] boot failed:", err);
  const container = document.getElementById("map");
  if (container) {
    container.innerHTML = `<pre style="padding:1rem;color:#f88;">${(err as Error).message}</pre>`;
  }
});
