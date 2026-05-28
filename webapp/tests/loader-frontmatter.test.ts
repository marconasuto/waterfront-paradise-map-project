import { describe, expect, it } from "vitest";

import { renderMarkdown, stripFrontmatter } from "../src/content/loader";

describe("stripFrontmatter", () => {
  it("removes a leading YAML frontmatter block", () => {
    const md =
      "---\nid: 01_wetlands\ntitle: \"Lago Salso\"\n---\n\nBody text.\n";
    expect(stripFrontmatter(md)).toBe("\nBody text.\n");
  });

  it("handles CRLF line endings", () => {
    const md = "---\r\nid: x\r\n---\r\nBody.";
    expect(stripFrontmatter(md)).toBe("Body.");
  });

  it("strips multi-line block content (camera, arrays, etc.)", () => {
    const md =
      "---\n" +
      "id: 00_intro\n" +
      "title: \"La costa di Manfredonia\"\n" +
      "camera: { center: [15.92, 41.62], zoom: 10.5, bearing: 0, pitch: 0 }\n" +
      "layers_visible: [coastline, hydrography_surface, admin_boundaries]\n" +
      "highlights: []\n" +
      "---\n" +
      "\nReal body.\n";
    const out = stripFrontmatter(md);
    expect(out).not.toMatch(/^---/);
    expect(out).not.toContain("layers_visible");
    expect(out).not.toContain("camera:");
    expect(out).toContain("Real body.");
  });

  it("leaves markdown without frontmatter untouched", () => {
    const md = "# Heading\n\nParagraph.\n";
    expect(stripFrontmatter(md)).toBe(md);
  });

  it("does not strip a `---` separator that appears mid-document", () => {
    const md = "Intro.\n\n---\n\nA section.\n";
    expect(stripFrontmatter(md)).toBe(md);
  });
});

describe("renderMarkdown with frontmatter", () => {
  it("does not leak frontmatter keys into rendered HTML", () => {
    const md =
      '---\nid: 01_wetlands\ntitle: "Lago Salso"\n---\n\nA sud-est di Manfredonia.\n';
    const html = renderMarkdown(md);
    expect(html).not.toContain("id:");
    expect(html).not.toContain("title:");
    expect(html).toContain("A sud-est di Manfredonia");
  });

  it("still renders headings after the frontmatter block", () => {
    const md = "---\nid: x\n---\n\n# Heading\n\nBody.\n";
    const html = renderMarkdown(md);
    expect(html).toContain("<h1");
    expect(html).toContain("Heading");
  });
});
