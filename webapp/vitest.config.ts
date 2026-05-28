import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: false,
    include: ["tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.ts"],
      // `main.ts` and `map/init.ts` boot the app + Mapbox GL JS — no way to
      // unit-test without a real browser. `env.ts` reads `import.meta.env`
      // which is only populated at Vite build time. `types.ts` is pure type
      // declarations (no runtime). Each is exercised end-to-end in the dev
      // server smoke test; we keep them out of unit coverage on purpose.
      exclude: [
        "src/main.ts",
        "src/env.ts",
        "src/map/init.ts",
        "src/types.ts",
        "src/**/*.d.ts",
      ],
      thresholds: {
        lines: 90,
        functions: 90,
        statements: 90,
        branches: 85,
      },
    },
  },
});
