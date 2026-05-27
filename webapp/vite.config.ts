import { defineConfig } from "vite";

// GitHub Pages serves the site under `/<repo-name>/`, so the bundled
// asset URLs need that prefix. Locally we still want `/`. CI sets
// `VITE_BASE_PATH=/manfredonia-map/` (or wherever) at build time.
const BASE_PATH = process.env["VITE_BASE_PATH"] ?? "/";

export default defineConfig({
  root: ".",
  publicDir: "public",
  base: BASE_PATH,
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: {
          mapbox: ["mapbox-gl"],
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
