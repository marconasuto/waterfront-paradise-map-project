# Subplan — Deployment

> Spec reference: `SPECIFICATIONS.md` §17. Static-site deployment.

## Targets

- **Default**: GitHub Pages from `gh-pages` branch (free, no extra account).
- **Alternative**: Vercel or Netlify if custom domain + edge needed later.

## Tasks

- [ ] `.github/workflows/ci.yml` — lint, mypy, tests on every PR.
- [ ] `.github/workflows/deploy.yml` — on tag `v*`: build `webapp/dist/`,
      run `mfd-map publish` against Mapbox using `MAPBOX_SECRET_TOKEN`
      from secrets, push to `gh-pages`.
- [ ] `webapp/` build reads `MAPBOX_PUBLIC_TOKEN` at build time only;
      token is URL-restricted to the deploy domain.
- [ ] Lighthouse CI gate on PRs that touch `webapp/`.

## Acceptance

- [ ] First tag `v0.1.0` deploys a live storymap.
- [ ] Token rotation is documented in `README.md`.
- [ ] No secret ever appears in `webapp/dist/` (CI grep gate).
