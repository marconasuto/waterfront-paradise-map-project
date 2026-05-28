import { beforeEach, describe, expect, it, vi } from "vitest";

// `vi.mock` is hoisted to the top of the file; using `vi.hoisted` keeps
// the FakeMarker / FakePopup classes alive in that same hoisted scope
// so the mock factory can reach them.
const fakes = vi.hoisted(() => {
  class FakePopup {
    static instances: FakePopup[] = [];
    options: Record<string, unknown>;
    html = "";
    constructor(options: Record<string, unknown>) {
      this.options = options;
      fakes.FakePopup.instances.push(this);
    }
    setHTML(html: string): this {
      this.html = html;
      return this;
    }
  }

  class FakeMarker {
    static instances: FakeMarker[] = [];
    element: HTMLElement | undefined;
    lngLat: [number, number] | null = null;
    popup: FakePopup | null = null;
    added = false;
    constructor(options: { element?: HTMLElement; anchor?: string }) {
      this.element = options.element;
      fakes.FakeMarker.instances.push(this);
    }
    setLngLat(c: [number, number]): this {
      this.lngLat = c;
      return this;
    }
    setPopup(p: FakePopup): this {
      this.popup = p;
      return this;
    }
    addTo(_map: unknown): this {
      this.added = true;
      return this;
    }
  }

  return { FakeMarker, FakePopup };
});

vi.mock("mapbox-gl", () => ({
  default: {
    Marker: fakes.FakeMarker,
    Popup: fakes.FakePopup,
  },
  Marker: fakes.FakeMarker,
  Popup: fakes.FakePopup,
}));

import {
  attachHighlights,
  loadedPopup,
  placeholderPopup,
  renderMarkerElement,
  renderMarkerSvg,
} from "../src/ui/highlights";
import { MARKER_ICON_PATHS, iconForCategory } from "../src/ui/icons/marker-icons";
import type { HighlightEntry, Palette } from "../src/types";

beforeEach(() => {
  fakes.FakeMarker.instances = [];
  fakes.FakePopup.instances = [];
});

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

describe("iconForCategory", () => {
  it.each([
    ["archeological", "archeological"],
    ["beach", "beach"],
    ["wetland", "wetland"],
    ["harbour", "harbour"],
    ["industrial", "industrial"],
    ["sin", "industrial"],
  ])("%s -> %s", (category, expected) => {
    expect(iconForCategory(category)).toBe(expected);
  });

  it("falls back to the default pin for unknown categories", () => {
    expect(iconForCategory("unknown-xyz")).toBe("default");
    expect(iconForCategory("")).toBe("default");
  });
});

describe("renderMarkerSvg", () => {
  it("inlines the category-specific Phosphor glyph", () => {
    const svg = renderMarkerSvg("archeological");
    expect(svg).toContain(MARKER_ICON_PATHS.archeological);
  });

  it("falls back to the default pin glyph for unknown categories", () => {
    const svg = renderMarkerSvg("nope");
    expect(svg).toContain(MARKER_ICON_PATHS.default);
  });

  it("renders a teardrop backdrop + inner disc + glyph layer", () => {
    const svg = renderMarkerSvg("harbour");
    expect(svg).toContain("highlight-marker__backdrop");
    expect(svg).toContain("highlight-marker__inner");
    expect(svg).toContain("highlight-marker__glyph");
  });

  it("uses a viewBox that lets `anchor: bottom` line up with the pin tip", () => {
    expect(renderMarkerSvg("beach")).toContain('viewBox="0 0 256 320"');
  });

  it("delegates color choices to CSS (no inline hex codes)", () => {
    const svg = renderMarkerSvg("wetland");
    expect(svg).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });
});

describe("renderMarkerElement", () => {
  it("returns a focusable <button> with category metadata", () => {
    const el = renderMarkerElement(H);
    expect(el.tagName).toBe("BUTTON");
    expect(el.getAttribute("type")).toBe("button");
    expect(el.classList.contains("highlight-marker")).toBe(true);
    expect(el.dataset["category"]).toBe("archeological");
    expect(el.dataset["styleToken"]).toBe("archeological");
  });

  it("carries an aria-label combining name and category for screen readers", () => {
    expect(renderMarkerElement(H).getAttribute("aria-label")).toBe(
      "Grotta Scaloria (archeological)",
    );
  });

  it("mounts the matching SVG glyph in the DOM", () => {
    const el = renderMarkerElement({ ...H, category: "harbour", style_token: "harbour" });
    const svg = el.querySelector("svg.highlight-marker__svg");
    expect(svg).not.toBeNull();
    // jsdom rewrites self-closing tags into open/close pairs, so we
    // assert on a stable path-fragment unique to the harbour anchor.
    const glyph = el.querySelector("svg.highlight-marker__glyph");
    expect(glyph).not.toBeNull();
    expect(glyph?.innerHTML).toContain("M216,144c0,64-88,24-88,88");
  });

  it("MARKER_ICON_PATHS is keyed by every category the resolver yields", () => {
    for (const cat of ["archeological", "beach", "wetland", "harbour", "industrial", "sin"]) {
      const key = iconForCategory(cat);
      expect(MARKER_ICON_PATHS[key]).toBeTruthy();
    }
  });
});

describe("attachHighlights", () => {
  const PALETTE: Palette = {
    archeological: { fill: "#b0054b" },
    wetland: { fill: "#679098" },
  };

  const HIGHLIGHTS: HighlightEntry[] = [
    {
      id: "grotta_scaloria",
      name_it: "Grotta Scaloria",
      category: "archeological",
      coord: [15.9059, 41.6403],
      style_token: "archeological",
      content_ref: "locations/grotta_scaloria.md",
    },
    {
      id: "lago_salso",
      name_it: "Lago Salso",
      category: "wetland",
      coord: [15.8714, 41.555],
      style_token: "wetland",
      content_ref: "locations/lago_salso.md",
    },
  ];

  function okFetch(body: string): typeof fetch {
    return vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(body),
    }) as unknown as typeof fetch;
  }

  function fakeMap(): unknown {
    return {};
  }

  it("creates one marker per highlight and adds it to the map", () => {
    const markers = attachHighlights(fakeMap() as never, {
      highlights: HIGHLIGHTS,
      palette: PALETTE,
      fetchFn: okFetch("body"),
    });
    expect(markers).toHaveLength(HIGHLIGHTS.length);
    expect(fakes.FakeMarker.instances).toHaveLength(HIGHLIGHTS.length);
    for (const m of fakes.FakeMarker.instances) {
      expect(m.added).toBe(true);
      expect(m.popup).not.toBeNull();
      expect(m.element?.classList.contains("highlight-marker")).toBe(true);
    }
  });

  it("places each marker at its highlight coordinate", () => {
    attachHighlights(fakeMap() as never, {
      highlights: HIGHLIGHTS,
      palette: PALETTE,
      fetchFn: okFetch("body"),
    });
    expect(fakes.FakeMarker.instances[0]?.lngLat).toEqual(HIGHLIGHTS[0]?.coord);
    expect(fakes.FakeMarker.instances[1]?.lngLat).toEqual(HIGHLIGHTS[1]?.coord);
  });

  it("renders a placeholder popup synchronously and hydrates with fetched markdown", async () => {
    attachHighlights(fakeMap() as never, {
      highlights: [HIGHLIGHTS[0] as HighlightEntry],
      palette: PALETTE,
      fetchFn: okFetch("Body **text**."),
    });
    const popup = fakes.FakePopup.instances[0];
    expect(popup).toBeDefined();
    expect(popup?.html).toContain("Contenuto in arrivo");
    // Flush the microtask queue so hydratePopup completes.
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    expect(popup?.html).toContain("<strong>text</strong>");
  });

  it("hydration falls back to the placeholder body on a 404", async () => {
    const fn = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve(""),
    }) as unknown as typeof fetch;
    attachHighlights(fakeMap() as never, {
      highlights: [HIGHLIGHTS[0] as HighlightEntry],
      palette: PALETTE,
      fetchFn: fn,
    });
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    const popup = fakes.FakePopup.instances[0];
    expect(popup?.html).toContain("Contenuto in arrivo");
  });
});
