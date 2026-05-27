/**
 * Read + validate a user-dropped file as a GeoJSON FeatureCollection.
 *
 * We accept either a `FeatureCollection` or a bare `Feature` (we wrap
 * the latter in a single-element collection for uniformity). Anything
 * else throws a clear, user-facing Italian error so the drop-zone can
 * surface it.
 */

// Minimal GeoJSON shape used here; full @types/geojson would add a dep
// for one type alias.
export interface GeoJsonGeometry {
  type: string;
  coordinates?: unknown;
}
export interface GeoJsonFeature {
  type: "Feature";
  geometry: GeoJsonGeometry | null;
  properties: Record<string, unknown> | null;
}
export interface FeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

const MAX_BYTES = 25 * 1024 * 1024; // 25 MB; refuse anything larger.

export interface ParsedDrop {
  name: string;
  collection: FeatureCollection;
  byteCount: number;
}

export async function readGeoJsonFile(file: File): Promise<ParsedDrop> {
  if (file.size > MAX_BYTES) {
    throw new Error(
      `Il file ${file.name} è troppo grande (${(file.size / 1e6).toFixed(1)} MB). Limite: 25 MB.`,
    );
  }
  if (!/\.(geo)?json$/i.test(file.name)) {
    throw new Error(`Formato non supportato: ${file.name}. Usa .geojson o .json.`);
  }
  const text = await readAsText(file);
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${file.name}: JSON non valido.`);
  }
  return {
    name: file.name,
    byteCount: file.size,
    collection: asFeatureCollection(parsed, file.name),
  };
}

/**
 * Read a File as UTF-8 text.
 *
 * `File.text()` (Blob API) is the modern path but jsdom (used by
 * vitest) does not implement it; FileReader works in both environments.
 */
function readAsText(file: File): Promise<string> {
  if (typeof (file as { text?: unknown }).text === "function") {
    return (file as Blob).text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (): void => resolve(String(reader.result ?? ""));
    reader.onerror = (): void => reject(reader.error ?? new Error("FileReader error"));
    reader.readAsText(file);
  });
}

export function asFeatureCollection(value: unknown, where: string): FeatureCollection {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${where}: non è un oggetto GeoJSON.`);
  }
  const v = value as { type?: string; features?: unknown };
  if (v.type === "FeatureCollection") {
    if (!Array.isArray(v.features)) {
      throw new Error(`${where}: FeatureCollection senza array \`features\`.`);
    }
    return value as FeatureCollection;
  }
  if (v.type === "Feature") {
    return { type: "FeatureCollection", features: [value as GeoJsonFeature] };
  }
  throw new Error(`${where}: tipo GeoJSON non supportato ("${String(v.type)}").`);
}
