import { loadEnv } from "./env";
import { initMap } from "./map/init";
import { loadStyle, styleLayerCount, styleSourceCount } from "./map/style-loader";

async function main(): Promise<void> {
  const container = document.getElementById("map");
  if (!container) {
    throw new Error("#map container not found in index.html");
  }
  const env = loadEnv();
  const style = await loadStyle("/style.json");
  console.info(
    `[manfredonia-map] style loaded: ${styleSourceCount(style)} sources, ${styleLayerCount(style)} layers`,
  );
  initMap({ container, style, env });
}

main().catch((err: unknown) => {
  console.error("[manfredonia-map] boot failed:", err);
  const container = document.getElementById("map");
  if (container) {
    container.innerHTML = `<pre style="padding:1rem;color:#f88;">${(err as Error).message}</pre>`;
  }
});
