# Final case-library branch review

## Scope and evidence

Reviewed base `6177ea6f78990ba12450621f1979ec1d80a96ceb` through head
`d5a6adeaa4fff50f4cbd042d532841024cce3d1a` against the implementation plan,
repository conventions, task reviews, integration evidence and release checks.
The final pass concentrated on display-policy enforcement, authenticated
HTTP boundaries, pagination, UI request state, native retrieval integration,
quota locking, replay and audit privacy. Focused reads of unchanged pagination,
transaction, billing, audit and native-engine code checked those seams.

No suites were rerun. `git diff --check 6177ea6..d5a6ade` passed, and the tracked
worktree was clean at the reviewed head. This review changed only this report.

## Strengths

- Full-text publication is closed by default and requires the authenticated
  actor, approved audience, record-specific checksum and approval reference.
  Browse/search projections remain text-free; the backend also checks display
  policy and text integrity (`deploy/retrieval/case_catalogue.py:149`,
  `backend/src/modules/library/wire_contracts.py:53`).
- Catalogue pagination binds signed cursors to actor, filters, route and corpus
  version. Keyset ordering supports the complete frozen collection without
  downloading it into the browser
  (`backend/src/modules/library/application/cases.py:24`,
  `deploy/retrieval/case_catalogue.py:198`).
- Similarity search reuses the native pipeline, enforces lexical-or-graph
  corroboration, bounds results/excerpts and distinguishes unavailable retrieval
  from a valid empty result. Reader membership and source links agree across
  the service and UI (`deploy/retrieval/case_catalogue.py:250`,
  `backend/src/modules/research/api/case_schemas.py:40`,
  `backend/src/modules/research/infrastructure/retrieval/case_http.py:23`,
  `frontend/src/components/library/case-law.tsx:366`).
- The reviewed quota race fix acquires the shared billing transaction lock
  before reading allowance and ledger state. Search replay, consumption and
  privacy-safe audit commit together; failed retrieval rolls back
  (`backend/src/modules/billing/application/billing_service.py:652`,
  `backend/src/modules/research/infrastructure/case_operations.py:34`,
  `backend/src/modules/research/infrastructure/case_operations.py:84`).
- The frontend retains a search idempotency key on retry, guards duplicate
  pending requests, handles stale cursors and renders approved text as escaped,
  whitespace-preserving content
  (`frontend/src/components/library/case-law.tsx:165`,
  `frontend/src/components/library/case-law.tsx:437`,
  `frontend/src/components/library/case-law.tsx:620`,
  `frontend/src/components/library/case-law.tsx:696`).
- Recorded verification includes all 9,601 original parsed texts, the actual
  read-only retrieval image and HTTP adapters, real PostgreSQL race regression,
  frontend 457 tests, backend CI 1,122 passes plus 3 expected failures, static
  checks and production build. Evidence clearly distinguishes the nine existing
  matter-agent integration failures from this change
  (`docs/review/case-law/2026-10-04/integration.md:7`,
  `docs/review/case-law/2026-10-04/release-checks.md:3`).

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

None found.

### Minor (Nice to Have)

None found in this final cross-boundary review.

## Recommendations

- Retain the documented baseline test failures and explicit release limits in
  the PR. Human visual identity, Sinhala terminology and real full-text
  publication approval remain pending; this technical review does not satisfy
  them (`docs/review/case-law/2026-10-04/release-checks.md:17`,
  `docs/review/case-law/2026-10-04/checklist.md:45`).
- Preserve the default metadata-only deployment and optional dense-provider
  approval requirements when an operator later prepares a release
  (`docs/case-law-library.md:40`).

## Assessment

**Ready to merge? Yes, from the code-review perspective.**

The implementation matches the standalone catalogue and conveyancing-search
scope, and this final pass found no material correctness or cross-boundary gap.
The documented palette reuse and minimal gazette slug repair are consistent
with the recorded rulings. Human merge and release decisions remain with their
owners; no deployment or merge was performed.
