import { describe, expect, it, vi } from "vitest";

import { loadContent, renderMarkdown } from "../src/content/loader";

function fakeFetch(status: number, body: string): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body),
  }) as unknown as typeof fetch;
}

describe("renderMarkdown", () => {
  it("renders inline markdown to HTML", () => {
    const html = renderMarkdown("**bold** and _italic_");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>italic</em>");
  });

  it("renders block markdown to paragraphs", () => {
    const html = renderMarkdown("# Title\n\nFirst paragraph.\n");
    expect(html).toContain("<h1>");
    expect(html).toContain("<p>First paragraph.</p>");
  });
});

describe("loadContent", () => {
  it("returns rendered HTML on a 200 response", async () => {
    const html = await loadContent(
      "locations/x.md",
      fakeFetch(200, "# Hello\n"),
      "/content/it/",
    );
    expect(html).toContain("<h1>");
  });

  it("requests the right URL", async () => {
    const fn = fakeFetch(200, "ok");
    await loadContent("locations/y.md", fn, "/content/it/");
    expect(fn).toHaveBeenCalledWith("/content/it/locations/y.md");
  });

  it("strips leading slashes on the ref", async () => {
    const fn = fakeFetch(200, "ok");
    await loadContent("/locations/y.md", fn, "/content/it/");
    expect(fn).toHaveBeenCalledWith("/content/it/locations/y.md");
  });

  it("returns null on a 404 response", async () => {
    expect(await loadContent("missing.md", fakeFetch(404, ""), "/content/it/")).toBeNull();
  });

  it("returns null when fetch rejects", async () => {
    const fn = vi.fn().mockRejectedValue(new Error("network")) as unknown as typeof fetch;
    expect(await loadContent("x.md", fn, "/content/it/")).toBeNull();
  });
});
