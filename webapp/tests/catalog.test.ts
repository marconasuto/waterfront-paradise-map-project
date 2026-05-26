import { describe, expect, it, vi } from "vitest";

import { indexLayerMeta, loadCatalog, type Catalog } from "../src/config/catalog";

function fakeFetch(status: number, body: string): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

const CATALOG_YAML = `
generated_at: '2026-05-26T00:00:00Z'
sources:
  - source_id: osm_coastline
    publisher: OpenStreetMap contributors
    dataset: OSM natural=coastline
    license: ODbL-1.0
    year_data: null
    url: https://example.com
  - source_id: ispra_hydro
    publisher: ISPRA
    dataset: Idrografia
    license: CC-BY-4.0
    year_data: 2024
    url: https://example.com
vector_layers:
  - layer_id: coastline
    source_id: osm_coastline
    feature_count: 4
    category: physical
    geom_types: [LineString]
  - layer_id: hydrography_surface
    source_id: ispra_hydro
    feature_count: 123
    category: hydro
    geom_types: [LineString]
raster_layers:
  - layer_id: tinitaly_dtm
    source_id: tinitaly_x
`;

describe("loadCatalog", () => {
  it("returns parsed catalog", async () => {
    const cat = await loadCatalog("/catalog.yaml", fakeFetch(200, CATALOG_YAML));
    expect(cat.sources).toHaveLength(2);
    expect(cat.vector_layers).toHaveLength(2);
    expect(cat.raster_layers).toHaveLength(1);
  });

  it("rejects missing sources", async () => {
    await expect(
      loadCatalog("/c.yaml", fakeFetch(200, "vector_layers: []\nraster_layers: []\n")),
    ).rejects.toThrow(/sources/);
  });

  it("rejects missing vector_layers", async () => {
    await expect(
      loadCatalog("/c.yaml", fakeFetch(200, "sources: []\nraster_layers: []\n")),
    ).rejects.toThrow(/vector_layers/);
  });

  it("rejects missing raster_layers", async () => {
    await expect(
      loadCatalog("/c.yaml", fakeFetch(200, "sources: []\nvector_layers: []\n")),
    ).rejects.toThrow(/raster_layers/);
  });
});

describe("indexLayerMeta", () => {
  it("resolves publisher + year per layer", async () => {
    const cat = await loadCatalog("/catalog.yaml", fakeFetch(200, CATALOG_YAML));
    const meta = indexLayerMeta(cat);
    expect(meta.size).toBe(3);

    const coast = meta.get("coastline")!;
    expect(coast.layer_type).toBe("vector");
    expect(coast.publisher).toBe("OpenStreetMap contributors");
    expect(coast.year).toBeNull();

    const hydro = meta.get("hydrography_surface")!;
    expect(hydro.publisher).toBe("ISPRA");
    expect(hydro.year).toBe(2024);

    const dtm = meta.get("tinitaly_dtm")!;
    expect(dtm.layer_type).toBe("raster");
    expect(dtm.feature_count).toBeNull();
  });

  it("falls back to 'Sconosciuto' when source_id is missing", () => {
    const cat: Catalog = {
      generated_at: "x",
      sources: [],
      vector_layers: [
        {
          layer_id: "orphan",
          source_id: "missing",
          feature_count: 0,
          category: "x",
          geom_types: [],
        },
      ],
      raster_layers: [],
    };
    const meta = indexLayerMeta(cat);
    expect(meta.get("orphan")!.publisher).toBe("Sconosciuto");
  });
});
