# Subplan — Testing

> Covers `tests/`. Spec reference: `SPECIFICATIONS.md` §16.

## Hard requirements

- Coverage ≥ **95 %** on `src/manfredonia_map/` (line + branch).
- Zero flaky tests. `pytest-randomly` is mandatory; if a flake appears it
  is a P0 bug.
- **No network in unit tests.** Enforced by a session-scoped fixture that
  monkey-patches `socket.socket` to raise.
- **No real Mapbox calls in unit tests.** `respx` mocks every HTTP call to
  `api.mapbox.com`.

## Layout

```
tests/
  unit/
    test_aoi.py
    test_catalog.py
    test_acquisition_http.py
    test_acquisition_wfs.py
    test_acquisition_overpass.py
    test_processing_*.py        ← one per layer normalizer
    test_publishing_*.py
    test_content_*.py
    test_mcp_bridges.py
  integration/
    test_pipeline_end_to_end.py ← uses fixture corpus only
    test_mapbox_publish_sandbox.py   ← @pytest.mark.network, opt-in
  fixtures/
    raw/                        ← tiny sampled inputs
    expected/                   ← expected outputs
```

## Determinism patterns

- All time functions go through `manfredonia_map.utils.now()` and are
  patched in tests.
- All random sources use a seeded `numpy.random.Generator` injected via
  function parameter.
- All HTTP via `respx` (sync or async); every test asserts its mocks were
  hit.
- File paths via `tmp_path`; no test writes outside its tmp dir.

## Property tests

- Use `hypothesis` for geometry validity (every processed polygon must be
  `is_valid`), schema preservation, and catalog round-trip.

## Tasks

- [ ] Add the no-network and no-mapbox fixtures.
- [ ] Write a `tests/conftest.py` with the canonical fixtures.
- [ ] Build a tiny fixture corpus per source (one polygon, one line, one
      point per layer, all inside the AOI).
- [ ] CI: a separate matrix entry runs the `network` job nightly only.

## Acceptance

- [ ] `pytest -q` is green on a randomized order.
- [ ] `pytest --cov-fail-under=95` passes on `main`.
- [ ] No test takes longer than 1 s by default; longer ones are `@slow`.
