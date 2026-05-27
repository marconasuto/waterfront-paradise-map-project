import { describe, expect, it } from "vitest";

import { asFeatureCollection, readGeoJsonFile } from "../src/io/geojson-file";

function makeFile(name: string, body: string): File {
  return new File([body], name, { type: "application/geo+json", lastModified: 0 });
}

describe("asFeatureCollection", () => {
  it("returns FeatureCollections unchanged", () => {
    const fc = { type: "FeatureCollection", features: [] };
    expect(asFeatureCollection(fc, "x")).toEqual(fc);
  });

  it("wraps a bare Feature in a single-element collection", () => {
    const feat = { type: "Feature", geometry: null, properties: {} };
    const fc = asFeatureCollection(feat, "x");
    expect(fc.type).toBe("FeatureCollection");
    expect(fc.features).toEqual([feat]);
  });

  it("rejects non-objects", () => {
    expect(() => asFeatureCollection("nope", "f")).toThrow(/oggetto GeoJSON/);
    expect(() => asFeatureCollection(null, "f")).toThrow(/oggetto GeoJSON/);
  });

  it("rejects unknown GeoJSON types", () => {
    expect(() => asFeatureCollection({ type: "Topology" }, "f")).toThrow(
      /tipo GeoJSON non supportato/,
    );
  });

  it("rejects FeatureCollections without features array", () => {
    expect(() => asFeatureCollection({ type: "FeatureCollection" }, "f")).toThrow(
      /senza array.*features/,
    );
  });
});

describe("readGeoJsonFile", () => {
  it("parses a valid .geojson file", async () => {
    const body = JSON.stringify({ type: "FeatureCollection", features: [] });
    const out = await readGeoJsonFile(makeFile("x.geojson", body));
    expect(out.name).toBe("x.geojson");
    expect(out.collection.features).toEqual([]);
  });

  it("accepts .json as well", async () => {
    const body = JSON.stringify({ type: "Feature", geometry: null, properties: {} });
    const out = await readGeoJsonFile(makeFile("x.json", body));
    expect(out.collection.features).toHaveLength(1);
  });

  it("rejects non-json extensions", async () => {
    await expect(readGeoJsonFile(makeFile("x.shp", ""))).rejects.toThrow(
      /Formato non supportato/,
    );
  });

  it("rejects invalid JSON", async () => {
    await expect(readGeoJsonFile(makeFile("x.geojson", "{not-json"))).rejects.toThrow(
      /JSON non valido/,
    );
  });

  it("rejects files larger than 25 MB", async () => {
    const big = new File([new ArrayBuffer(26 * 1024 * 1024)], "huge.geojson", {
      type: "application/geo+json",
    });
    await expect(readGeoJsonFile(big)).rejects.toThrow(/troppo grande/);
  });
});
