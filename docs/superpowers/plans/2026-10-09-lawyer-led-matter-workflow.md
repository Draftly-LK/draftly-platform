# Lawyer-led matter workflow implementation plan

> **For agentic workers:** Use superpowers:executing-plans with superpowers:subagent-driven-development for sequential implementation and independent review. Track each checkbox and atomic commit.

**Goal:** Connect persistent ingestion, reviewed scoped facts, conversation,
requirements, checks, and optional Form 8 drafting through real application APIs.

**Architecture:** Extend the current modular monolith and published contracts.
Keep lifecycle ownership with its existing service; use explicit transaction
and subject scope, immutable history, and fail-closed eligibility projections.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy/Alembic, PostgreSQL;
Next.js 15, strict TypeScript, pnpm, next-intl, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-lawyer-led-matter-workflow-design.md`.

## Global constraints

- V0 user/matter isolation; organization support explicitly deferred by user.
- All user-facing strings use next-intl and English/Sinhala localization.
- Preserve originals and append decision/fact history; machine candidates never
  self-verify. Only current eligible reviewed facts feed approved outputs.
- Use public cross-module contracts, existing authorization, audit and unit of
  work; no new framework or production provider/configuration changes.
- No real client values/images, credentials, or identifying logs in artifacts.
- No statutory, template legal, approval, or waiver wording changes.
- Branch `dev/codex/lawyer-led-matter-workflow`; human merges.

## Execution and evidence

Use TDD per behavior: add an independently derived failing regression, run and
record its expected failure, implement, then run the owning suites. Update the
task's report in `docs/review/matter-flow/2026-10-09/` with only synthetic evidence.
Run relevant quality gates and inspect the staged diff before each commit.
Task interfaces below are additive unless a contract-migration entry documents
a required semantic change. Serial execution avoids overlapping file edits.

### Task 1: Truthful persisted processing and recovery

**Files:** `backend/src/modules/document/{application/ingestion_service.py,infrastructure/repository.py,api/ingestion_router.py,api/schemas.py}`;
`frontend/src/{components/matter/processing-screen.tsx,lib/api/documents.ts,types/rta.ts,lib/i18n/messages/{en,si}.json}`;
owning document tests and a new `processing-screen.test.tsx`.

**Interfaces:** Consume existing SourceFile/ProcessingRun. Produce additive
latest-run read data/API with state/failure details and authorized retry using
the refreshed source version. Keep source-file processing contract compatible.

- [ ] Add regression: failed run with a source ID displays failure/recovery;
  refresh preserves reason; processing cannot continue as successful.
- [ ] Run regression and record the expected failure.
- [ ] Implement latest persistent run read, terminal-state rendering, partial
  page/manual-review display, safe retry, pagination and remove visual delay.
- [ ] Test success, failure, unavailable provider, partial page failure, refresh,
  retry, empty/paginated lists, and stale source version.
- [ ] Run frontend typecheck/lint/tests/build and owning backend checks; review
  and commit `fix(e8-7): preserve processing outcomes and recovery`.

### Task 2: Canonical scoped fact backend

**Files:** `backend/src/modules/{matter,verification,document}` scoped contracts,
domain/API/repository files; `backend/src/bootstrap.py`; additive migration;
verification and cross-service integration/security tests; OpenAPI and service docs.

**Interfaces:** Matter-owned subject and transaction references; verification
list/history and accept/correct/reject/manual/association commands. Extend
ConfirmedFactValue with scope and FactTierSummary with scoped values; its legacy
confirmed projection must withhold ambiguous types. Version by scope.

- [ ] Add regression: two subjects keep distinct values; conflicting values
  within a scope remain unbound; unrelated users/matters cannot reference scopes.
- [ ] Record red; implement typed scope records and additive migrations with
  explicit legacy-unassigned handling, canonical commands, evidence validation,
  concurrency, idempotency, audit and preserved originals/history.
- [ ] Test manual unverified input, rejection, accepted correction successors,
  role/practice refusal, foreign evidence, retry and stale writes.
- [ ] Migrate up/down on disposable PostgreSQL; run verification/matter/document
  contract and security suites; review and commit `feat(e8-7): review scoped matter facts`.

### Task 3: Canonical fact register and point-of-need input

**Files:** `frontend/src/components/matter/{facts-screen.tsx,document-review-screen.tsx}`
and focused fact-review components; `frontend/src/lib/api/facts.ts`, `types/rta.ts`,
messages; component/API tests and fact-register review evidence.

**Interfaces:** Consume Task 2 facts, scope and decision APIs. Produce form-free
register, subject assignment and missing/conflicting input paths.

- [ ] Add regression: reviewed facts are visible and editable without a form,
  original/current values differ after correction, history survives reload.
- [ ] Record red; implement scope filtering, candidate decisions, manual entry,
  original/source page access, review history and honest precision labels.
- [ ] Test two subjects, conflict/rejection, unavailable source/API, permission
  refusal, correction and refresh; localize both languages.
- [ ] Run frontend gates and browser accessibility/layout checks; independent
  review and commit `feat(e8-7): expose the canonical matter fact register`.

### Task 4: Corrected grouping and extraction invalidation

**Files:** document ingestion/review/processing application and repository,
domain/API/ORM; verification/check/task/draft public invalidation contracts;
bootstrap; migration; `document-decisions.tsx`; owning/integration tests and docs.

**Interfaces:** Interpretation generation pinned by candidates and evidence;
correction marks downstream eligibility stale and extraction retry rebuilds
using confirmed type/fragments. Historical rows remain readable.

- [ ] Add regression: changing type or ranges makes old candidates unapprovable
  and dependent reviewed facts/output ineligible before extraction refresh.
- [ ] Record red; implement versioned interpretation, persistent refresh state,
  corrected-fragment extraction and scoped invalidation via owning contracts.
- [ ] Expose editable page ranges; validate bounds/overlap and foreign source IDs.
- [ ] Test correction, partial refresh failure/retry, unchanged confirmations,
  multi-file grouping, historical review and stopped stale output.
- [ ] Run affected backend/frontend/migration gates; review and commit
  `fix(e5): refresh extraction after document corrections`.

### Task 5: Requirements, manual tasks, checks and next action

**Files:** task/check/matter application, domain, contracts, APIs and repositories;
bootstrap/migrations as needed; frontend documents/checks/dashboard, shell nav,
workflow route, API clients/types/messages; integration/security/UI tests.

**Interfaces:** Authorized idempotent links and requirement decisions; governed
manual task completion; exact input-version check state; backend readiness with
blocker references and unknown/unavailable state.

- [ ] Add regression: foreign document link refused; upload is receipt rather
  than sufficiency; manual completion cannot satisfy evidence policy.
- [ ] Record red; validate link/evidence scope, synchronize changed dependencies,
  preserve decisions, add manual completion governed by existing definitions.
- [ ] Show missing requirements within Documents; separate automated/manual work
  in Checks; redirect legacy live demo workflow and missing-document routes.
- [ ] Add readiness regressions for pending grouping/facts/checks, failures and
  unavailable checklist; implement backend-owned progress and next actions.
- [ ] Run affected suites and frontend/backend gates; review and commit coherent
  requirement, manual-task and readiness changes separately.

### Task 6: Persistent Overview conversation and confirmed tools

**Files:** matter-agent service/contracts/domain/API/ORM/bootstrap and migration;
assistant-screen and shared conversation component; dashboard, API agent,
types/messages/tests; agent docs and OpenAPI.

**Interfaces:** Integrate existing uncommitted assistant recovery patch from the
other worktree selectively. Proposals pin target/scope/version; confirmation
rechecks authorization and delegates to Tasks 2/5 commands idempotently.

- [ ] Add/run regressions for initial/terminal SSE snapshots, failed send replay,
  persisted transcript and refresh without duplicated messages.
- [ ] Inspect and port existing recovery work with its migration/tests, excluding
  unrelated landing-page changes. Rebase semantics against this branch.
- [ ] Add/run proposal regressions for authorization, stale versions, decline,
  replay and audited execution; implement only the selected working tools.
- [ ] Embed reusable conversation in Overview; preserve full view/session;
  show usable provider/evidence unavailable states and supporting citations.
- [ ] Run agent integration/security, UI/browser and quality gates; review and
  commit recovery separately from Overview/proposal additions.

### Task 7: Explicitly scoped optional Form 8

**Files:** draft and approval/export affected public contracts, domain/API/ORM,
repositories/bootstrap/migration; drafting UI/client/types/messages; tests/docs.

**Interfaces:** Draft request pins selected transaction and parcel/party bindings;
field resolver consumes Task 2 scoped facts. Existing legal wording and approval
policies remain unchanged.

- [ ] Add/run regression: two parcels/parties cannot bind by matter-wide latest
  value; unresolved role or stale/conflicting fact yields an explained field gap.
- [ ] Implement scope selection, exact fact-version bindings, missing-field
  cause display and successor refresh retaining historical approved snapshots.
- [ ] Test review/approval/export refusal for unreviewed/stale/missing facts,
  successful supported draft, refresh/retry and foreign scope IDs.
- [ ] Run affected backend/frontend/migration gates; review and commit
  `feat(e7): bind Form 8 to reviewed transaction facts`.

### Task 8: Synthetic reference and persistent integrated journey

**Files:** independent synthetic fixture generator/reference/evaluation under
`backend/tests/fixtures/matter_flow/`; `backend/tests/integration/test_matter_flow_api.py`;
frontend Playwright journey; `docs/review/matter-flow/2026-10-09/` coverage,
walkthrough, review, gates and delivery records.

**Interfaces:** Exercise real APIs, PostgreSQL persistence, local object storage,
and provider doubles. Provider accuracy evaluation is separately labelled.

- [ ] Create mixed/rotated/scanned synthetic fixtures with independent identifiers,
  multiple subjects, conflict/missing/unsupported fields and expected page text.
- [ ] Obtain owner review of reference and numerical extraction target before
  making any improvement claim. Identify provider approval availability without
  changing flags or sending client material.
- [ ] Execute upload -> grouping -> fact review -> conversation -> requirement
  and manual decision -> optional Form 8 through persistence, then refresh.
- [ ] Test conflict, multiple subjects, correction invalidation, partial failure,
  retry, concurrency, missing information and cross-user/matter isolation.
- [ ] Run all quality/migration/browser gates, independent integrated review,
  focused fixes and re-review. Commit tests/evidence separately from fixes.
- [ ] Report measured coverage and outstanding real-case/provider decisions;
  map ordered commits to objectives and open a feature PR when ready.
