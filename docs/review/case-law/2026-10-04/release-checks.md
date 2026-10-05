# Case-library release checks

## Backend

- PASS: `uv lock --check`.
- PASS: Ruff check and format, including retrieval-wrapper Python files.
- PASS: `uv run mypy src` (352 files after the quota fix).
- PASS: case/importer, existing library/research and OpenAPI tests: 30 passed.
- PASS: covering billing, case and contract tests after review fixes: 110 passed.
- PASS: real PostgreSQL quota/header checks: 9 passed. The regression test first
  reproduced two distinct searches succeeding with one query remaining; shared
  billing usage locking now permits one and rejects the other. Concurrent release
  and retry checks also pass.
- PASS: CI suite `uv run pytest tests/unit tests/contract tests/conformance -q`:
  1,122 passed, 3 expected failures after review fixes. An upstream Starlette/httpx deprecation
  warning remains in the existing test-client dependency.
- BASELINE FAILURE: full `uv run pytest -q` has 9 failed, 2,455 passed,
  207 skipped and 4 expected failures. All nine failures belong to the existing
  matter-agent integration fixture, whose table list omits `agent_conversations`.
  A representative failure reproduces on clean main commit `6177ea6`; the fixture
  and matter-agent implementation are unchanged by this PR.

The full suite also reports an existing Alembic `path_separator` configuration
deprecation. Dependencies and unrelated fixture configuration are unchanged.

See [integration checks](integration.md) for the actual corpus and read-only
retrieval image validation. Full text remains gated by a separately recorded
display approval; dense search remains opt-in.

## Frontend

- PASS: `pnpm test` (457 tests in 45 files).
- PASS: `pnpm typecheck`, `pnpm lint`, `pnpm build` after the contrast fix.
- PASS: focused case and gazette URL-shape checks (20 tests in 3 files).
- PASS: [synthetic browser checks](checklist.md), including both viewports,
  English/Sinhala, zoom, keyboard, safe rendering and accessibility.

An initial cold build emitted a webpack cache serialization performance
diagnostic; the final build passed without warnings.

## Existing visual-spec discrepancy

Main already uses the navy/gold refresh documented in
[its review](../../ui-refresh/checklist.md); `docs/plan.md` still describes older
tokens. This feature reuses the current shared tokens and applies 6 px radii and
no shadows to new case components. It does not restyle the shared shell. Human
visual review may require a later token adjustment.
