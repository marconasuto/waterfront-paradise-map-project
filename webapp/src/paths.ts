/**
 * Compose an asset URL relative to the Vite `base`.
 *
 * `import.meta.env.BASE_URL` is `/` in dev and `/<repo>/` on a GitHub
 * Pages subpath build. Asset paths must be composed at runtime so the
 * same code works in both environments.
 */
export function assetUrl(relative: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const stripped = relative.replace(/^\/+/, "");
  return base.endsWith("/") ? base + stripped : `${base}/${stripped}`;
}
