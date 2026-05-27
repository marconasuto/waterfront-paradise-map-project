import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SlideMeta } from "../src/content/slides";
import { StoryPanel } from "../src/ui/story-panel";

const SLIDES: SlideMeta[] = [
  {
    id: "00_intro",
    title: "Intro",
    body_ref: "slides/00_intro.md",
    camera: { center: [15.92, 41.62], zoom: 10.5 },
  },
  {
    id: "01_wetlands",
    title: "Wetlands",
    body_ref: "slides/01_wetlands.md",
    camera: { center: [15.94, 41.6], zoom: 12 },
  },
];

class FakeObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin = "0px";
  readonly thresholds = [0.5];
  private targets: Element[] = [];
  constructor(public callback: IntersectionObserverCallback) {}
  observe(target: Element): void {
    this.targets.push(target);
  }
  unobserve(): void {
    /* no-op */
  }
  disconnect(): void {
    this.targets = [];
  }
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
  /** Fire an intersection for the section with the given slide id. */
  fire(slideId: string): void {
    const target = this.targets.find(
      (t) => (t as HTMLElement).dataset["slideId"] === slideId,
    );
    if (!target) throw new Error(`no target for ${slideId}`);
    this.callback(
      [{ isIntersecting: true, target } as unknown as IntersectionObserverEntry],
      this,
    );
  }
}

describe("StoryPanel", () => {
  let container: HTMLDivElement;
  let observer: FakeObserver;
  const observerFactory = (cb: IntersectionObserverCallback): IntersectionObserver => {
    observer = new FakeObserver(cb);
    return observer;
  };
  const fetchBody = vi.fn(async (s: SlideMeta) => `<p>body of ${s.id}</p>`);

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    location.hash = "";
    fetchBody.mockClear();
  });

  it("renders one section per slide", () => {
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate: vi.fn(),
      observerFactory,
      fetchBody,
    });
    const sections = container.querySelectorAll(".story-panel__slide");
    expect(sections).toHaveLength(2);
    expect((sections[0] as HTMLElement).id).toBe("slide-00_intro");
  });

  it("fires onActivate when a section intersects", async () => {
    const onActivate = vi.fn();
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate,
      observerFactory,
      fetchBody,
    });
    observer.fire("01_wetlands");
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate.mock.calls[0]![0].id).toBe("01_wetlands");
  });

  it("does not refire onActivate for the same slide", () => {
    const onActivate = vi.fn();
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate,
      observerFactory,
      fetchBody,
    });
    observer.fire("00_intro");
    observer.fire("00_intro");
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it("updates location.hash on activation", () => {
    const onActivate = vi.fn();
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate,
      observerFactory,
      fetchBody,
    });
    observer.fire("01_wetlands");
    expect(location.hash).toBe("#slide-01_wetlands");
  });

  it("honours a deep-link hash on boot", () => {
    location.hash = "#slide-01_wetlands";
    const onActivate = vi.fn();
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate,
      observerFactory,
      fetchBody,
    });
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate.mock.calls[0]![0].id).toBe("01_wetlands");
  });

  it("kicks off body loading for every slide", () => {
    new StoryPanel({
      container,
      slides: SLIDES,
      onActivate: vi.fn(),
      observerFactory,
      fetchBody,
    });
    expect(fetchBody).toHaveBeenCalledTimes(2);
  });

  it("destroy disconnects the observer", () => {
    const panel = new StoryPanel({
      container,
      slides: SLIDES,
      onActivate: vi.fn(),
      observerFactory,
      fetchBody,
    });
    const spy = vi.spyOn(observer, "disconnect");
    panel.destroy();
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
