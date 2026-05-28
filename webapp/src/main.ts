import { indexLayerMeta, loadCatalog } from "./config/catalog";
import { loadBasemaps, loadColorScheme, loadHighlights } from "./config/loader";
import { loadSlideIndex } from "./content/slides";
import { loadEnv } from "./env";
import { readGeoJsonFile } from "./io/geojson-file";
import { applyBasemap } from "./map/basemap-apply";
import { initMap } from "./map/init";
import { loadStyle, styleLayerCount, styleSourceCount } from "./map/style-loader";
import { addOverlayLayers, pickDefaultBasemap } from "./map/style-merge";
import { assetUrl } from "./paths";
import {
  applyLayerOrder,
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
import {
  attachIntroCurtain,
  attachMenuDrawer,
  attachPanelToggle,
} from "./ui/chrome";
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
  // Set the style by URL so Mapbox resolves it natively — crucial for
  // Standard, whose `imports`-based document does not survive a manual
  // JSON merge. Overlay sources + layers are added after `style.load`.
  const map = initMap({
    container: mapContainer,
    style: initialBasemap.style_url,
    env,
    ...(typeof initialBasemap.pitch === "number" ? { pitch: initialBasemap.pitch } : {}),
  });
  let currentBasemap = initialBasemap;
  // Debug hook: lets a headless browser inspect terrain/layer state.
  // Debug hook: lets a headless browser / devtools inspect map state.
  (window as unknown as { __mfdMap?: unknown }).__mfdMap = map;
  map.on("style.load", () => {
    // style.load fires on boot and after every setStyle — re-add the
    // overlay, then re-apply per-layer state + camera/terrain for the
    // active basemap (a swap, e.g. dark → standard_3d, resets all of it).
    // Guard so one failing step can't silently abort the rest.
    try {
      addOverlayLayers(map, overlay);
      applyLayerState(map, layerState);
      applyLayerOrder(map, layerState);
      applyBasemap(map, currentBasemap, { accessToken: env.mapboxPublicToken });
    } catch (err) {
      console.error("[manfredonia-map] style.load setup failed:", err);
    }
  });

  const switcher = new BasemapControl({
    basemaps: basemapsCfg.basemaps,
    initialId: initialBasemap.id,
    onChange: (next) => {
      currentBasemap = next;
      // setStyle by URL; the `style.load` handler re-adds the overlay.
      map.setStyle(next.style_url);
    },
  });
  map.addControl(switcher, "bottom-left");

  const persist = (next: LayerState[]): void => {
    layerState = next;
    try {
      saveLayerState(next);
    } catch (err) {
      console.warn("[manfredonia-map] could not persist layer state:", err);
    }
    applyLayerState(map, next);
    applyLayerOrder(map, next);
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
  const layerToggleBtn = document.getElementById("layer-panel-toggle");
  if (appRoot && layerToggleBtn) {
    attachPanelToggle({
      root: appRoot,
      button: layerToggleBtn,
      collapsedClass: "layer-panel-collapsed",
      expandedLabel: "Chiudi pannello dei livelli",
      collapsedLabel: "Apri pannello dei livelli",
      onResize: () => map.resize(),
    });
  }

  const storyToggleBtn = document.getElementById("story-panel-toggle");
  if (appRoot && storyToggleBtn) {
    attachPanelToggle({
      root: appRoot,
      button: storyToggleBtn,
      collapsedClass: "story-panel-collapsed",
      expandedLabel: "Chiudi pannello della storia",
      collapsedLabel: "Apri pannello della storia",
      onResize: () => map.resize(),
    });
  }

  const introCurtain = document.getElementById("intro-curtain");
  const introCloseBtn = document.getElementById("intro-curtain-close");
  if (introCurtain && introCloseBtn) {
    attachIntroCurtain({
      curtain: introCurtain,
      closeBtn: introCloseBtn,
      onDismissed: () => map.resize(),
    });
  }

  const menuToggleBtn = document.getElementById("menu-toggle");
  const menuCloseBtn = document.getElementById("menu-close");
  const menuDrawer = document.getElementById("menu-drawer");
  if (menuToggleBtn && menuCloseBtn && menuDrawer) {
    attachMenuDrawer({
      toggleBtn: menuToggleBtn,
      closeBtn: menuCloseBtn,
      drawer: menuDrawer,
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
