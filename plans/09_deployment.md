# Subplan — Deployment

> Spec reference: `SPECIFICATIONS.md` §17. Static-site deployment.

## Target

**GitHub Pages**, native to the repo. Free for public repos; private
repos require GitHub Pro / Team / Enterprise. Built and pushed by
`.github/workflows/deploy.yml` on every commit to `main` that touches
`webapp/`, `config/`, `content/`, `data/catalog.yaml`, or
`data/processed/style.json`.

If GH Pages is unavailable (free plan + private repo), the same
`webapp/dist/` artifact deploys 1:1 to Vercel, Netlify or Cloudflare
Pages without webapp code changes.

## One-time setup

1. **Create + push the GitHub repo.**
   ```bash
   gh repo create manfredonia-map --private --source=. --remote=origin
   git push -u origin main
   ```
2. **Create the public Mapbox token.** Mapbox dashboard → Access Tokens
   → Create. Default public scopes are enough
   (`styles:tiles`, `styles:read`, `fonts:read`, `datasets:read`).
3. **Add the token as a repo secret.** GitHub repo Settings → Secrets
   and variables → Actions → New repository secret:
   - `MAPBOX_PUBLIC_TOKEN` = the `pk.*` token.
4. **Enable Pages.** Repo Settings → Pages → Source: **GitHub Actions**.
5. **First deploy.** Push to `main` or trigger
   `Deploy webapp to GitHub Pages` via Actions → Run workflow. The job
   prints the live URL when it finishes.
6. **URL-restrict the public token.** Once the live URL is known,
   Mapbox dashboard → that token → URL restrictions → add
   `https://<user>.github.io/<repo>/*`. Without this, a token leaked
   in `dist/` could be used from any origin.

## What the workflow does

`.github/workflows/deploy.yml`:

1. Checkout the repo.
2. `actions/configure-pages` to compute the subpath base.
3. Install pnpm 10 + Node 22 with cached `webapp/pnpm-lock.yaml`.
4. `pnpm install --frozen-lockfile` inside `webapp/`.
5. `pnpm run typecheck` (tsc strict).
6. `pnpm run test` (vitest, all suites must pass).
7. `pnpm run build` with `VITE_MAPBOX_PUBLIC_TOKEN` from secrets and
   `VITE_BASE_PATH` set to the GH Pages subpath. The `prebuild` hook
   runs `scripts/sync-config.mjs` to mirror `data/processed/style.json`,
   `data/catalog.yaml`, `config/*.yaml`, `content/it/**` and the slide
   index into `webapp/public/`.
8. `actions/upload-pages-artifact` packages `webapp/dist/`.
9. `actions/deploy-pages` publishes it.

## Notes

- **`data/processed/style.json` is tracked in git** (small, deterministic,
  ~6 KB) so CI does not need the Python pipeline. Regenerate after any
  palette / layer-id change with `pixi run publish-style`.
- **Tiles are hosted by Mapbox**, not GH Pages — only the bundle (HTML,
  JS, CSS, style.json, the config YAMLs, and the content tree) ships
  to Pages.
- **No secret ever lands in `dist/`.** The public token is injected at
  build time and bundled into the JS, which is the expected pattern for
  Mapbox GL JS. Restrict the token by URL.

## Future tasks (post-v1)

- `.github/workflows/ci.yml` separate from deploy: pytest + ruff + mypy
  on the Python side, plus vitest + tsc on the JS side. Runs on every
  PR.
- Lighthouse CI gate (perf ≥ 90, a11y ≥ 95) on PRs that touch
  `webapp/`.
- Optional custom domain on Pages.

## Acceptance

- [ ] Repo pushed to GitHub.
- [ ] First workflow run deploys the site and the run summary
      includes the live URL.
- [ ] Live URL renders Manfredonia at AOI center with all 14 overlays,
      6 highlights, 2 placeholder slides.
- [ ] Mapbox public token is URL-restricted to the deploy domain.
