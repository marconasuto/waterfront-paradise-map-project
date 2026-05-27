import { loadSlideBody, type SlideMeta } from "../content/slides";

export interface StoryPanelOptions {
  container: HTMLElement;
  slides: SlideMeta[];
  /** Fires when a slide enters the activation zone of the viewport. */
  onActivate: (slide: SlideMeta) => void;
  /** Override the IntersectionObserver constructor (used in tests). */
  observerFactory?: (cb: IntersectionObserverCallback) => IntersectionObserver;
  /** Override the body fetcher (used in tests). */
  fetchBody?: (slide: SlideMeta) => Promise<string>;
}

const HASH_PREFIX = "slide-";

/**
 * Render slide sections in `container` and wire scroll triggers.
 *
 * The first slide that crosses the activation threshold (50 % visible)
 * fires `onActivate`. A leading hash like `#slide-<id>` is honoured at
 * boot time so deep-links land on the right slide.
 */
export class StoryPanel {
  private readonly opts: StoryPanelOptions;
  private readonly elements = new Map<string, HTMLElement>();
  private activeId: string | null = null;
  private observer: IntersectionObserver | null = null;

  constructor(opts: StoryPanelOptions) {
    this.opts = opts;
    this.render();
    this.observe();
    this.honourInitialHash();
  }

  private render(): void {
    this.opts.container.innerHTML = "";
    const list = document.createElement("ol");
    list.className = "story-panel__list";
    for (const slide of this.opts.slides) {
      const sec = document.createElement("li");
      sec.className = "story-panel__slide";
      sec.id = `${HASH_PREFIX}${slide.id}`;
      sec.dataset["slideId"] = slide.id;

      const h2 = document.createElement("h2");
      h2.className = "story-panel__title";
      h2.textContent = slide.title;
      sec.appendChild(h2);

      const body = document.createElement("div");
      body.className = "story-panel__body";
      body.innerHTML = "<p><em>Caricamento…</em></p>";
      sec.appendChild(body);

      void (this.opts.fetchBody ?? loadSlideBody)(slide).then((html) => {
        body.innerHTML = html;
      });

      list.appendChild(sec);
      this.elements.set(slide.id, sec);
    }
    this.opts.container.appendChild(list);
  }

  private observe(): void {
    const factory =
      this.opts.observerFactory ??
      ((cb: IntersectionObserverCallback) =>
        new IntersectionObserver(cb, {
          root: this.opts.container,
          rootMargin: "0px",
          threshold: 0.5,
        }));
    this.observer = factory((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const id = (entry.target as HTMLElement).dataset["slideId"];
        if (id) this.activate(id);
      }
    });
    for (const el of this.elements.values()) {
      this.observer.observe(el);
    }
  }

  private honourInitialHash(): void {
    const h = typeof location === "undefined" ? "" : location.hash;
    if (!h.startsWith(`#${HASH_PREFIX}`)) return;
    const id = h.slice(`#${HASH_PREFIX}`.length);
    const el = this.elements.get(id);
    if (!el) return;
    // jsdom doesn't implement scrollIntoView; guard so tests don't blow up.
    if (typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "auto" });
    }
    this.activate(id);
  }

  private activate(id: string): void {
    if (id === this.activeId) return;
    this.activeId = id;
    const slide = this.opts.slides.find((s) => s.id === id);
    if (!slide) return;
    if (typeof history !== "undefined" && typeof history.replaceState === "function") {
      history.replaceState(null, "", `#${HASH_PREFIX}${id}`);
    }
    this.opts.onActivate(slide);
  }

  destroy(): void {
    this.observer?.disconnect();
    this.observer = null;
  }
}
