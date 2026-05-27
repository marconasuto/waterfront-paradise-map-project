import { indexLayerMeta, loadCatalog } from "./config/catalog";
import { loadBasemaps, loadColorScheme, loadHighlights } from "./config/loader";
import { loadSlideIndex } from "./content/slides";
import { loadEnv } from "./env";
import { readGeoJsonFile } from "./io/geojson-file";
import { initMap } from "./map/init";
import { loadStyle, styleLayerCount, styleSourceCount } from "./map/style-loader";
import {
  fetchBasemapStyle,
  mergeOverlay,
  pickDefaultBasemap,
} from "./map/style-merge";
import { assetUrl } from "./paths";
import {
  applyLayerState,
  extractManfredoniaLayerIds,
  loadLayerState,
  reconcileLayerState,
  saveLayerState,
  type LayerState,
} from "./state/layer-state";
import { OverlayManager } from "./state/overlays";
import { applySlide } from "./state/story-controller";
import { BasemapControl } from "./ui/basemap-control";
import { attachDropZone } from "./ui/drop-zone";
import { attachHighlights } from "./ui/highlights";
import { LayerPanel, defaultLayerLabel } from "./ui/layer-panel";
import { OverlayList } from "./ui/overlay-list";
import { StoryPanel } from "./ui/story-panel";

async function main(): Promise<void> {
  const mapContainer = document.getElementById("map");
  const layerListContainer = document.getElementById("layer-panel-list");
  const overlayListContainer = document.getElementById("overlay-list");
  const storyContainer = document.getElementById("story-panel");
  if (!mapContainer || !layerListContainer || !overlayListContainer || !storyContainer) {
    throw new Error(
      "required #map / #layer-panel-list / #overlay-list / #story-panel containers not found",
    );
  }
  const env = loadEnv();

  const [overlay, basemapsCfg, catalog, highlightsCfg, colorScheme, slides] = await Promise.all([
    loadStyle(assetUrl("style.json")),
    loadBasemaps(assetUrl("basemaps.yaml")),
    loadCatalog(assetUrl("catalog.yaml")),
    loadHighlights(assetUrl("highlights.yaml")),
    loadColorScheme(assetUrl("color_scheme.yaml")),
    loadSlideIndex(assetUrl("slides.json")),
  ]);
  console.info(
    `[manfredonia-map] overlay: ${styleSourceCount(overlay)} sources, ${styleLayerCount(overlay)} layers; ${basemapsCfg.basemaps.length} basemaps; ${catalog.sources.length} catalog sources; ${highlightsCfg.highlights.length} highlights; ${slides.length} slides`,
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

  const layerPanel = new LayerPanel({
    container: layerListContainer,
    state: layerState,
    meta,
    label: defaultLayerLabel,
    onChange: persist,
  });

  const overlays = new OverlayManager(map);
  const overlayList = new OverlayList({
    container: overlayListContainer,
    onRemove: (id) => {
      overlays.remove(id);
      overlayList.setOverlays(overlays.list());
    },
  });
  attachDropZone({
    element: mapContainer,
    onDrop: async (file) => {
      try {
        const parsed = await readGeoJsonFile(file);
        overlays.add(parsed.name, parsed.collection);
        overlayList.setOverlays(overlays.list());
      } catch (err) {
        console.warn("[manfredonia-map] dropped file rejected:", err);
        alert((err as Error).message);
      }
    },
  });

  map.on("load", () => {
    attachHighlights(map, {
      highlights: highlightsCfg.highlights,
      palette: colorScheme.palette,
    });
  });

  if (slides.length > 0) {
    new StoryPanel({
      container: storyContainer,
      slides,
      onActivate: (slide) => {
        const next = applySlide({ map, baseline: layerState, slide });
        layerState = next;
        layerPanel.setState(next);
      },
    });
  } else {
    storyContainer.innerHTML =
      '<p class="story-panel__empty">Nessuna slide ancora pubblicata.</p>';
  }

  const appRoot = document.getElementById("app");
  const toggleBtn = document.getElementById("layer-panel-toggle");
  if (appRoot && toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const collapsed = appRoot.classList.toggle("layer-panel-collapsed");
      toggleBtn.setAttribute(
        "aria-label",
        collapsed ? "Apri pannello dei livelli" : "Chiudi pannello dei livelli",
      );
      map.resize();
    });
  }
}

main().catch((err: unknown) => {
  console.error("[manfredonia-map] boot failed:", err);
  const container = document.getElementById("map");
  if (container) {
    container.innerHTML = `<pre style="padding:1rem;color:#f88;">${(err as Error).message}</pre>`;
  }
});
