import { marked } from "marked";

/**
 * Fetch a markdown document from `webapp/public/content/it/<ref>` and
 * render it to HTML.
 *
 * Returns `null` when the file is missing — Phase 6 ships the marker
 * plumbing before Phase 7 fills the markdown bodies, so a 404 must
 * gracefully degrade to the "Contenuto in arrivo" placeholder rather
 * than crash the popup.
 */
import { assetUrl } from "../paths";

export async function loadContent(
  ref: string,
  fetchFn: typeof fetch = fetch,
  baseDir = "content/it/",
): Promise<string | null> {
  const url = assetUrl(baseDir + ref.replace(/^\/+/, ""));
  let res: Response;
  try {
    res = await fetchFn(url);
  } catch {
    return null; // network / CORS errors map to "missing".
  }
  if (!res.ok) return null;
  const md = await res.text();
  return renderMarkdown(md);
}

/** Synchronous render. Exported for tests + the placeholder fallback. */
export function renderMarkdown(md: string): string {
  // `marked.parse()` returns a string when called without async option.
  return marked.parse(stripFrontmatter(md), { async: false }) as string;
}

/** Strip a leading `---\n...\n---` YAML frontmatter block, if present. */
export function stripFrontmatter(md: string): string {
  return md.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "");
}
