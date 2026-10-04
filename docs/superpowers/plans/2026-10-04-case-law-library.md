# Judgment Library and Similar-Case Search Implementation Plan

**Goal:** Browse the supplied LKCA/LKSC collection, read policy-permitted full
judgments, and search similar conveyancing cases independently of the assistant.

**Architecture:** A build-time importer packages a frozen judgment catalogue into
the private retrieval container. Typed backend ports access the catalogue and
existing case-retrieval engine over internal HTTP. The Legal sources screen adds
a case-law tab and reader without changing statute or assistant behavior.

**Global constraints:** Follow CLAUDE.md, approved service plans, pnpm and uv;
do not modify draftly-research, commit source dumps, or push directly to main.
All frontend copy uses next-intl. Machine extraction is never legal approval.
Full-text access requires a recorded approval reference and its audience.
No approval reference has been supplied in this session; fail closed until one
is recorded. Use only synthetic content in tests and screen-review evidence.

## Task 1: Frozen corpus and backend interfaces

- [x] Write failing tests for import fidelity, policy filtering, pagination,
  HTTP failure handling, corroboration, and metering/idempotency.
- [x] Build a catalogue from the two supplied judgment JSONL files, preserving
  original parsed text, collection, deciding court, citation, dates, provenance,
  extraction warnings and stable IDs. Prefix IDs with commonlii- to join search.
- [x] Package the corpus into the existing private retrieval image with a
  versioned manifest and input checksums; never read research paths at runtime.
- [x] Add versioned internal catalogue and search interfaces. Reuse existing
  conveyancing BM25, graph, optional dense, RRF and corroboration behavior.
- [x] Add authenticated GET /api/v1/library/cases and /cases/{caseId}, and
  POST /api/v1/research/cases/search. Return signed cursor pagination with
  default 25, year descending and stable ID. Expose corpus version and coverage.
- [x] Separate unknown/unavailable corpus errors from valid no-similar-cases;
  enforce research.enabled and research_queries.monthly with replay safety.
  Record privacy-safe audits. Dense remains opt-in under provider approval.
- [x] Preserve the current statute endpoints; keep routers thin with application
  services and ports. Generate the OpenAPI contract after API changes.
- [x] Run backend checks and importer tests; document the exact frontend contract
  and local/deployment startup in the task report.

## Task 2: Case catalogue, reader and fact-pattern search

- [x] Write failing frontend boundary and interaction tests against Task 1's
  contract, then implement typed API accessors and separate case models.
- [x] Add a Case law tab to Legal sources. Browse every imported judgment with
  name/citation search, court-collection and year filters, and cursor navigation.
- [x] Open a judgment in a dedicated navigable reader with metadata, source link,
  verification and extraction warnings. Render text safely and preserve breaks.
  Metadata-only records explain that full text awaits display approval.
- [x] Add a standalone fact-pattern search with up to eight cited results,
  excerpts, matching signals, optional-channel degradation, explicit no-results
  and retryable failure states. Search results outside the reader corpus use
  source links. Keep assistant APIs and behavior unchanged.
- [x] Localize English/Sinhala controls and states; review responsive and keyboard
  behavior, and save synthetic review evidence under docs/review/case-law.
- [x] Run frontend tests, typecheck, lint and build. Update affected service and
  deployment documentation with the implemented contract and release limits.

## Task 3: Integration, review and PR

- [x] Import the actual collection into an ignored local artifact and check
  7,439 LKCA plus 2,162 LKSC records, IDs, text fidelity and filters.
- [x] Verify API-to-engine integration, full-text gating, search/reader joins,
  unavailable-engine and dense-only outcomes, and idempotent quota use.
- [x] Run all available backend/frontend quality gates and Markdown lint.
- [x] Review the whole change, fix material findings, and recheck changed paths.
- [ ] Push dev/codex/case-law-library and open a PR targeting main, with test
  evidence and explicit display-approval and optional-embedding requirements.
  Do not merge or deploy.
