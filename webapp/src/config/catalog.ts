import { loadYaml } from "./loader";

export interface CatalogSource {
  source_id: string;
  publisher: string;
  dataset: string;
  license: string;
  year_data: number | null;
  url: string;
}

export interface CatalogVectorLayer {
  layer_id: string;
  source_id: string;
  feature_count: number;
  category: string;
  geom_types: string[];
}

export interface CatalogRasterLayer {
  layer_id: string;
  source_id: string;
}

export interface Catalog {
  generated_at: string;
  sources: CatalogSource[];
  vector_layers: CatalogVectorLayer[];
  raster_layers: CatalogRasterLayer[];
}

/**
 * Per-layer metadata needed by the layer-panel UI.
 *
 * Resolved by walking the catalog: for each vector/raster layer entry
 * we look up its `source_id` in the `sources` table to pull the
 * publisher, dataset, license and year.
 */
export interface LayerMeta {
  layer_id: string;
  layer_type: "vector" | "raster";
  feature_count: number | null;
  publisher: string;
  dataset: string;
  license: string;
  year: number | null;
}

export async function loadCatalog(
  url = "/catalog.yaml",
  fetchFn?: typeof fetch,
): Promise<Catalog> {
  const cat = await loadYaml<Catalog>(url, fetchFn);
  if (!Array.isArray(cat.sources)) {
    throw new Error(`${url}: missing or invalid sources`);
  }
  if (!Array.isArray(cat.vector_layers)) {
    throw new Error(`${url}: missing or invalid vector_layers`);
  }
  if (!Array.isArray(cat.raster_layers)) {
    throw new Error(`${url}: missing or invalid raster_layers`);
  }
  return cat;
}

/**
 * Resolve attribution metadata for every layer in the catalog.
 * Missing source rows fall back to a "Sconosciuto" placeholder so
 * the UI still renders.
 */
export function indexLayerMeta(cat: Catalog): Map<string, LayerMeta> {
  const sourceById = new Map(cat.sources.map((s) => [s.source_id, s]));
  const result = new Map<string, LayerMeta>();

  const unknown = {
    publisher: "Sconosciuto",
    dataset: "—",
    license: "—",
    year: null,
  };

  for (const vl of cat.vector_layers) {
    const src = sourceById.get(vl.source_id);
    result.set(vl.layer_id, {
      layer_id: vl.layer_id,
      layer_type: "vector",
      feature_count: vl.feature_count,
      publisher: src?.publisher ?? unknown.publisher,
      dataset: src?.dataset ?? unknown.dataset,
      license: src?.license ?? unknown.license,
      year: src?.year_data ?? unknown.year,
    });
  }
  for (const rl of cat.raster_layers) {
    const src = sourceById.get(rl.source_id);
    result.set(rl.layer_id, {
      layer_id: rl.layer_id,
      layer_type: "raster",
      feature_count: null,
      publisher: src?.publisher ?? unknown.publisher,
      dataset: src?.dataset ?? unknown.dataset,
      license: src?.license ?? unknown.license,
      year: src?.year_data ?? unknown.year,
    });
  }
  return result;
}
