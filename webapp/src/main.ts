import { indexLayerMeta, loadCatalog } from "./config/catalog";
import { loadBasemaps } from "./config/loader";
import { loadEnv } from "./env";
import { initMap } from "./map/init";
import { loadStyle, styleLayerCount, styleSourceCount } from "./map/style-loader";
import {
  fetchBasemapStyle,
  mergeOverlay,
  pickDefaultBasemap,
} from "./map/style-merge";
import {
  applyLayerState,
  extractManfredoniaLayerIds,
  loadLayerState,
  reconcileLayerState,
  saveLayerState,
  type LayerState,
} from "./state/layer-state";
import { BasemapControl } from "./ui/basemap-control";
import { LayerPanel, defaultLayerLabel } from "./ui/layer-panel";

async function main(): Promise<void> {
  const mapContainer = document.getElementById("map");
  const panelContainer = document.getElementById("layer-panel");
  if (!mapContainer || !panelContainer) {
    throw new Error("required #map / #layer-panel containers not found");
  }
  const env = loadEnv();

  const [overlay, basemapsCfg, catalog] = await Promise.all([
    loadStyle("/style.json"),
    loadBasemaps("/basemaps.yaml"),
    loadCatalog("/catalog.yaml"),
  ]);
  console.info(
    `[manfredonia-map] overlay: ${styleSourceCount(overlay)} sources, ${styleLayerCount(overlay)} layers; ${basemapsCfg.basemaps.length} basemaps; ${catalog.sources.length} catalog sources`,
  );

  const layerIds = extractManfredoniaLayerIds(overlay);
  const meta = indexLayerMeta(catalog);
  let layerState = reconcileLayerState(layerIds, loadLayerState());

  const initialBasemap = pickDefaultBasemap(basemapsCfg.basemaps);
  const initialBase = await fetchBasemapStyle(initialBasemap, env.mapboxPublicToken);
  const map = initMap({
    container: mapContainer,
    style: mergeOverlay(initialBase, overlay),
    env,
  });
  map.on("style.load", () => {
    applyLayerState(map, layerState);
  });

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

  const persist = (next: LayerState[]): void => {
    layerState = next;
    try {
      saveLayerState(next);
    } catch (err) {
      console.warn("[manfredonia-map] could not persist layer state:", err);
    }
    applyLayerState(map, next);
  };

  new LayerPanel({
    container: panelContainer,
    state: layerState,
    meta,
    label: defaultLayerLabel,
    onChange: persist,
  });
}

main().catch((err: unknown) => {
  console.error("[manfredonia-map] boot failed:", err);
  const container = document.getElementById("map");
  if (container) {
    container.innerHTML = `<pre style="padding:1rem;color:#f88;">${(err as Error).message}</pre>`;
  }
});
