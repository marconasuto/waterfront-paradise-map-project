import { loadContent, renderMarkdown } from "./loader";

export interface SlideCamera {
  center: [number, number];
  zoom: number;
  bearing?: number;
  pitch?: number;
}

export interface SlideMedia {
  type: "image" | "youtube";
  src: string;
  alt?: string;
  caption?: string;
}

/** Frontmatter shape emitted by `scripts/sync-config.mjs` into slides.json. */
export interface SlideMeta {
  id: string;
  title: string;
  camera: SlideCamera;
  /** Bare layer ids (e.g. `coastline`) — the engine prefixes `manfredonia-`. */
  layers_visible?: string[];
  highlights?: string[];
  media?: SlideMedia[];
  /** Path under `content/it/` to the source `.md` (set by the indexer). */
  body_ref: string;
}

export async function loadSlideIndex(
  url = "/slides.json",
  fetchFn: typeof fetch = fetch,
): Promise<SlideMeta[]> {
  const res = await fetchFn(url);
  if (!res.ok) {
    throw new Error(`failed to load ${url}: HTTP ${res.status}`);
  }
  const parsed = (await res.json()) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error(`${url}: expected an array of slides`);
  }
  return parsed.filter(isSlideMeta);
}

/** Fetch a slide's markdown body and render to HTML. */
export async function loadSlideBody(
  slide: SlideMeta,
  fetchFn: typeof fetch = fetch,
): Promise<string> {
  const html = await loadContent(slide.body_ref, fetchFn);
  return html ?? renderMarkdown("_Contenuto in arrivo._");
}

function isSlideMeta(v: unknown): v is SlideMeta {
  if (typeof v !== "object" || v === null) return false;
  const s = v as Partial<SlideMeta>;
  return (
    typeof s.id === "string" &&
    typeof s.title === "string" &&
    typeof s.body_ref === "string" &&
    typeof s.camera === "object" &&
    s.camera !== null &&
    Array.isArray((s.camera as SlideCamera).center) &&
    typeof (s.camera as SlideCamera).zoom === "number"
  );
}
