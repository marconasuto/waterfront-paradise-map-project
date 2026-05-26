import { describe, expect, it } from "vitest";

import { loadedPopup, placeholderPopup } from "../src/ui/highlights";
import type { HighlightEntry } from "../src/types";

const H: HighlightEntry = {
  id: "grotta_scaloria",
  name_it: "Grotta Scaloria",
  category: "archeological",
  coord: [15.907, 41.648],
  style_token: "archeological",
  content_ref: "locations/grotta_scaloria.md",
};

describe("placeholderPopup", () => {
  it("includes the Italian title", () => {
    expect(placeholderPopup(H)).toContain("Grotta Scaloria");
  });

  it("renders a category chip with the style_token attribute", () => {
    const html = placeholderPopup(H);
    expect(html).toContain('data-token="archeological"');
    expect(html).toContain(">archeological<");
  });

  it("shows the Italian placeholder while content is loading", () => {
    expect(placeholderPopup(H)).toContain("Contenuto in arrivo");
  });

  it("escapes embedded HTML in the title", () => {
    const evil: HighlightEntry = { ...H, name_it: "<script>x()</script>" };
    expect(placeholderPopup(evil)).not.toContain("<script>");
    expect(placeholderPopup(evil)).toContain("&lt;script&gt;");
  });

  it("escapes embedded HTML in the style_token", () => {
    const evil: HighlightEntry = { ...H, style_token: 'a"b' };
    const html = placeholderPopup(evil);
    expect(html).toContain('data-token="a&quot;b"');
  });
});

describe("loadedPopup", () => {
  it("substitutes the rendered body in place of the placeholder", () => {
    const html = loadedPopup(H, "<p>Body</p>");
    expect(html).toContain("<p>Body</p>");
    expect(html).not.toContain("Contenuto in arrivo");
  });

  it("preserves the title + chip", () => {
    const html = loadedPopup(H, "<p>Body</p>");
    expect(html).toContain("Grotta Scaloria");
    expect(html).toContain("archeological");
  });
});
