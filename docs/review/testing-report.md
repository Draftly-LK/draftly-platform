# Draftly Platform — Test Completion Report

| Field | Value |
|---|---|
| Report identifier | DRAFTLY-TCR-001 |
| Version | 1.0 |
| Date | 2026-09-19 |
| Author | Praveen De Silva |
| Branch | `platform/praveen` (repository `draftly-platform`) |
| Test period | 2026-09-18 to 2026-09-19 |
| Governing test plan | `docs/TESTING_PLAN.md` (the test plan, referred to below as "the plan") |
| Structure | ISO/IEC/IEEE 29119-3, Test Completion Report; section 15 maps it to IEEE 829 |

## 1. Introduction

### 1.1 Purpose

This report records the testing carried out against the plan, the results,
the defects found and fixed, and the risks that remain. It gives the reader
enough evidence to judge whether the testing met its objectives, and states
plainly where it did not.

It covers three things: the software testing of the platform (sections 2 to
8), the evaluation of the data-science components (section 9), and an error
analysis of those components (section 10).

### 1.2 The system under test

Draftly is a legal-drafting platform for Sri Lankan notaries. A lawyer opens a
matter, uploads title documents, reviews facts that the system extracts from
them, works through a statutory checklist, and produces a registration form
(for example Form 8, a transfer of land) that the lawyer approves and exports.

The system has three parts:

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async) and PostgreSQL, with an
  outbox and background worker for asynchronous jobs.
- **Frontend:** Next.js 15 (React 19, TypeScript), with an offline demo mode
  backed by a local state store.
- **Database:** PostgreSQL 16, with schema migrations managed by Alembic.

The domain is regulated. A wrong fact in a land-transfer form, or one client's
data shown to another lawyer, is a legal and professional failure, not a
cosmetic one. The plan therefore puts safety rules and refusals ahead of happy
paths.

### 1.3 Scope

In scope:

- backend unit, integration, security (authentication, authorisation, tenancy),
  contract and conformance testing;
- database testing on real PostgreSQL (repositories, migrations, concurrency,
  data-at-rest privacy);
- frontend unit and component testing, and browser end-to-end journeys that
  run in the offline demo;
- the CI pipeline, coverage measurement and coverage gates.

Out of scope for this cycle:

- performance, load and stress testing;
- penetration testing and automated vulnerability scanning;
- user acceptance testing with practising lawyers;
- tests that call paid external services (AI extraction, OCR, cloud storage).
  These are marked `live` and excluded from routine runs. The data-science
  components behind them are evaluated separately, in the research repository;
  sections 9 and 10 report those results and analyse their errors;
- verifying the legal wording of form templates. That is a human task owned by
  the legal team, and no test may author or alter it.

### 1.4 Test data

All test data is synthetic and labelled as such, for example the matter
reference `SYN/SMOKE/0001 (synthetic)` and fixed identifiers such as
`usr_synthetic`. Factories use fixed seeds and a fixed clock
(2026-08-17 09:00 UTC), and never use the system clock or random numbers, so
every run produces the same data. No real client data was used.

## 2. Testing performed

### 2.1 Starting point

The plan began with an audit that found 22 weaknesses in the existing testing
(F1 to F22 in the plan: 4 Critical, 8 High, 7 Medium, 3 Low). The most serious
were:

- CI ran only 245 backend tests (three folders) and none of the frontend unit
  tests. Security, integration and module suites existed but never ran.
- No coverage was measured in either stack.
- The real login path (token validation) was never executed by any test.
- The background worker and the signed pagination cursors had no tests.
- The frontend's 806-line demo state store had no unit tests.

### 2.2 Stages

The work followed the plan's eight commits, grouped into four stages. Each
piece was committed separately; each stage was pushed once it was complete.

| Stage | Plan commits | What was done |
|---|---|---|
| 1. CI and harness | 1 | CI runs the whole backend suite and the frontend unit tests; a PostgreSQL service in CI; coverage measured in both stacks; browser tests can sign in; retries and reports in CI |
| 2. Test foundations | 2 | Shared test factories; a per-test PostgreSQL session that runs the real migrations and rolls back after each test; a synthetic seed script |
| 3. Backend depth | 3–7 | Authentication, authorisation, tenancy, worker and outbox, database repositories, migrations, privacy at rest, domain policies, API conventions, contract and conformance tests |
| 4. Frontend and gates | 8 | Demo store, draft building, labels, the seven API client modules, extracted intake helpers, component tests, a browser refusal journey, coverage floors, random-order runs |

### 2.3 Test levels and types

| Level | Tools | What it covers |
|---|---|---|
| Unit | pytest, Vitest | Pure domain policies, routing, cursors, signature checks, the demo store, API clients, label maps |
| Component | Vitest, happy-dom, Testing Library | React components rendered with the real translation catalogue |
| Integration (database) | pytest, PostgreSQL 16 in Docker | Repositories, services, migrations, concurrency, the audit chain |
| API and security | pytest, httpx, the real FastAPI app | Every route, driven from the OpenAPI description: login, roles, tenancy, version headers, error format |
| Contract and conformance | pytest | Committed API and rule-pack contracts, the service registry, event and job declarations |
| End-to-end | Playwright (Chromium) | Browser journeys through the offline demo |

### 2.4 Test design techniques

- **Equivalence partitioning and boundary values:** list limits (0, 1, default,
  over the maximum), version numbers (current, stale, missing, malformed),
  confidence scores, the New Year boundary in the Asia/Colombo time zone.
- **State-transition testing:** matter states, draft approval and export,
  checklist item decisions, outbox job states (claimed, retried, dead-lettered).
- **Decision tables:** the checklist's three safety rules were tested across
  every combination of statuses; intake routing was tested against the whole
  question catalogue.
- **Route sweeps:** rather than hand-picking routes, tests read the public
  OpenAPI description and check every route of a kind. A new route is covered
  automatically, and a route that breaks a rule fails the build.
- **Concurrency testing:** two real database sessions racing on the audit chain
  and the usage quota.
- **Fault injection:** forged and truncated cursors and signatures, non-ASCII
  and non-UTF-8 input on public webhooks, an unreachable database.
- **Mutation-style checks:** after each fix or new safety test, the protected
  code was broken on purpose, the test was run and seen to fail, and the code
  was restored. This shows that each test can actually fail.
- **Known-gap tests:** where the system has a gap that needs a team decision, a
  strict expected-failure test (`xfail(strict=True)`) records it. If someone
  fixes the gap, the test starts passing unexpectedly and the build tells them
  to promote it to a normal test.

### 2.5 Test environment

| Item | Version or setting |
|---|---|
| Operating system (local) | Windows 11 |
| CI | GitHub Actions, `ubuntu-latest`, PostgreSQL 16 service |
| Python and packages | Python 3.12 managed with `uv`; pytest 9, pytest-asyncio 1.4, pytest-cov 7, pytest-randomly 5 |
| Node and packages | Node 22, pnpm 10.23; Vitest 3.1.2 with v8 coverage; happy-dom 20; Testing Library (React) 16 |
| Browser tests | Playwright 1.55, Chromium, dev server on port 4310 with the development-only auth bypass |
| Test database | `postgres:16` in Docker on port 55432; each test gets its own migrated schema |
| Assistance | Claude Code (an AI coding assistant) was used under the author's direction to write and run tests. Every result in this report was run and checked on the machine described above. |

## 3. Deviations from the plan

| Planned | What happened | Reason |
|---|---|---|
| API-bound browser journeys: matter isolation, error recovery, upload and review (plan §7.2) | Not written | These screens only render with a configured Clerk sign-in, and the project has no Clerk test keys yet. Tenancy is tested instead at the API layer (section 7). |
| Five refusal journeys in the browser (§7.2) | One journey written (blocked workflow step needs a reason) | Approval and export refusals live on API-bound screens (as above). The rich-text editor that offers fact chips is not mounted on any page. The demo has no 95%-confidence unreviewed fact. |
| Full lawyer workflow up to an approved export (Appendix A happy path) | Refusals tested; happy path stops before export | Every form template is an unverified transcription, so the system correctly refuses a registration-ready export. Verifying the wording is a human gate. |
| Per-router tests for a stale version (412) | Covered by sweeps and selected routers; not one file per router | Deferred to keep the cycle on the plan's critical items. |
| Document-to-fact flow test (§4.2) | Deferred | Depends on the extraction pipeline, which calls paid services. |
| Plan's coverage targets (§11.3 step 2) | Floors set at today's numbers instead | The plan itself says to ratchet from a measured number rather than start from a fixed target, which fails the next change and gets switched off. |

## 4. Test measures

### 4.1 Test execution

Final runs on 2026-09-19:

| Suite | Run | Passed | Failed | Skipped or excluded | Expected failures |
|---|---|---|---|---|---|
| Backend (pytest, real PostgreSQL) | 3922 collected | 3906 | 0 | 1 skipped, 5 `live` excluded | 10 |
| Frontend unit and component (Vitest) | 348 | 348 | 0 | 0 | 1 (see 6.2) |
| Browser: refusal journey (Playwright, new) | 3 | 3 | 0 | 0 | 0 |

The expected failures are the known-gap tests described in section 2.4 and
listed in section 6.2. None of them hides a failure: each would fail the build
if it started to pass.

**Growth over the test period:**

| Measure | Before | After |
|---|---|---|
| Backend tests run by CI | 245 | 3906 |
| Frontend unit tests run by CI | 0 (13 files existed) | 348 (30 files) |
| Backend suites run by CI | 3 folders | all (`-m "not live"`) |
| Tests on real PostgreSQL in CI | 0 | the whole `tests/db` and `tests/security` suites |

### 4.2 Stability

- **Random order.** The backend suite passed three runs in a row with seeds
  1111, 2222 and 3333 (3906 passed each time). The frontend passed three
  shuffled runs with the same seeds (348 passed each time). No test depends on
  another test running first. Random order is now the default on every
  backend run.
- **Retries.** Backend tests have no retries. Browser tests retry twice in CI
  only, to absorb infrastructure noise; a test that passes only on retry is
  treated as a defect.
- **Run time.** The full backend suite takes about 6 minutes without coverage
  and about 11 minutes with coverage on the local machine.

### 4.3 Coverage

Measured with pytest-cov (backend) and Vitest's v8 provider (frontend).

| Area | Metric | Before (2026-09-18) | After (2026-09-19) | Plan target | Target met |
|---|---|---|---|---|---|
| Backend `src/` | Lines | 77.1% (13802 / 17905) | **85.4%** (15326 / 17945) | 80% | Yes |
| Backend `src/` | Branches | 51.0% (1466 / 2876) | **63.9%** (1846 / 2888) | 70% | No |
| Backend `src/` | Lines and branches combined | 73% | **82.4%** | — | — |
| Frontend `src/` | Lines | 2.4% (292 / 12419) | **27.0%** (3352 / 12424) | 70% | No |
| Frontend `src/lib/` | Lines | not measured | **93.3%** | 85% | Yes |
| Frontend `src/components/` | Lines | not measured | **3.1%** | 50% | No |

Frontend branch coverage is not reported, because v8 only counts branches in
files that a test loads, so the figure overstates coverage while few
components are loaded.

The logic layers (`src/lib/` in the frontend and the domain and platform code
in the backend) are well covered. The gap is the React screens: the plan says
most of their value is better tested in the browser, and those browser tests
are blocked on the Clerk keys (section 5).

**Coverage gates.** CI now fails if coverage falls below a floor set one point
under the numbers above: backend combined 81%; frontend lines 26% overall,
92% in `src/lib/`, 2% in `src/components/`. Each floor is raised when the
suite beats it, so coverage can rise but never fall. Both gates were checked by
raising a floor above the real number and confirming that the run failed.

### 4.4 Defect measures

| Severity | Definition used | Found | Fixed | Open |
|---|---|---|---|---|
| Critical | Breaks a core workflow for every user, or breaks one of the seven safety rules | 2 | 2 | 0 |
| High | Breaks a feature, or allows wrong or unsafe data under realistic conditions | 8 | 8 | 0 |
| Medium | Wrong result or crash in an edge case, or only in the offline demo | 4 | 4 | 0 |
| Low | Wording or display | 1 | 1 | 0 |
| **Total** | | **15** | **15** | **0** |

Twelve of the fifteen defects were found by tests running against real
PostgreSQL. Earlier tests used fakes or SQLite, which do not enforce foreign
keys the same way and do not run concurrent transactions, so these defects
could not show up there.

## 5. Factors that blocked progress

1. **No Clerk test keys.** The API-bound screens need a real sign-in provider to
   render. Without test keys, the browser journeys for approval, export, matter
   isolation, error recovery and upload cannot run, and the browser suite cannot
   run in CI.
2. **Human-gated legal wording.** The form templates have not been verified by
   the legal team, so the full workflow cannot reach an approved export. This is
   intended behaviour and must not be worked around by a test.
3. **Open team decisions.** Four decisions in the plan (A6.1 to A6.4) and several
   policy questions found during testing (section 6.2) need an owner's answer
   before the related tests can be finalised.
4. **Pre-existing browser failures.** In the last full local run, 11 of the 12
   older browser spec files had failures. The causes are outside the test code:
   specs that need the backend running, specs written for older screens, and a
   background-colour mismatch between the design plan (`#F4F3EF`) and the code
   (`#f4f6f8`). The team has since chosen `#f4f6f8`, the colour the frontend
   uses now, and the design plan and design-audit test were updated to match.
5. **Tooling on Windows.** The async test loop needed a selector event loop for
   the PostgreSQL driver, and `pnpm`/`uv` were not on the default path. Both
   were solved without changing production code.

## 6. Defects and residual risks

### 6.1 Defects found and fixed

Each fix has a test that failed before the fix and passes after it.

| # | Severity | Defect | Fix commit |
|---|---|---|---|
| 1 | Critical | Creating a party crashed every time: the event log passed a keyword argument the logger reserves | `d353f36` |
| 2 | Critical | Concurrent writes could fork a user's tamper-evident audit hash chain | `a163270` |
| 3 | High | The worker reclaimed long-running jobs too early and could run an assistant turn twice | `d02ce0a` |
| 4 | High | The migration environment did not register every model, so an autogenerated migration would have dropped 8 tables | `403db93` |
| 5 | High | Party and matter-assistant list cursors were not signed, so a client could forge one | `f93f827` |
| 6 | High | Five more list cursors (matters, approvals, checks, documents, drafts) were unsigned or crashed on bad input | `261d50a` |
| 7 | High | Creating a billing plan failed with a foreign-key error | `b107f97` |
| 8 | High | Concurrent usage could overspend a quota or refund it twice (safety rule 7) | `975ee72` |
| 9 | High | Creating an obligation failed with a foreign-key error | `867313a` |
| 10 | High | Saving a party screening result failed with a foreign-key error | `8edf8bd` |
| 11 | Medium | A payment webhook with a non-ASCII signature crashed (500) instead of being refused | `9852ec1` |
| 12 | Medium | An email webhook with a non-UTF-8 body crashed before its signature was checked | `b747d1c` |
| 13 | Medium | Notarial attestations near New Year were numbered in the wrong register year (UTC instead of Sri Lanka time) | `b4e8a35` |
| 14 | Medium | The offline demo exported a draft that had never been approved | `eed5fa7` |
| 15 | Low | One activity event ("processing not configured") showed the generic text "Activity updated" | `0ef0c76` |

### 6.2 Known gaps recorded as expected-failure tests

These are real gaps in the product, not in the tests. Each is held by a strict
expected-failure test so it cannot be forgotten or silently fixed.

| Gap | Risk | Needs |
|---|---|---|
| Three declared background jobs have no handler (subscription reconciliation, obligation reminders, month-end register close) | High: scheduled work never runs | Implementation, and decision A6.4 (the missing scheduler) |
| Obligation reminders are kept in memory and never reach the outbox | High: reminders are lost on restart | Implementation |
| Old stream events are never purged | Medium: storage grows without limit | A caller and a schedule |
| 14 differences between the database models and the migrations | Medium: the next autogenerated migration may be wrong | Model or migration fixes |
| Notarial register writes take no version header, unlike the rest of the API | Medium: concurrent edits can overwrite each other | An API contract change agreed with the register's owners |
| Four intake questions activate modules that no answer can reach | Medium: some checklist modules can never apply | A rule-pack correction by the legal team |
| When an intake answer and a confirmed fact disagree, the code and its comment disagree on which wins | Medium: a legal rule is ambiguous | A legal decision |
| Demo only: correcting a fact does not reopen an approved draft (refusal 2) | Low: the real server enforces this | A "stale" state in the demo store |

### 6.3 Other residual risks

| Risk | Rating | Owner |
|---|---|---|
| Browser journeys for approval, export, tenancy and errors are not automated | High | Team: provide Clerk test keys |
| The approval step does not ask for a fresh sign-in (step-up), and the policy is undecided | Medium | Product and security owner |
| The readiness health check has no timeout on the database call | Medium | Backend |
| `MatterService.transition` has no permission check (it currently has no callers) | Medium | Backend |
| The "blocking requirements" query returns an empty list when a matter has no checklist, which could read as "nothing blocks" | Medium | Backend |
| A malformed version header gets 412 from some routes and 428 from others | Low | Backend |
| The approval screen has English text written into the code instead of the translation catalogue, and approving accepts every warning at once | Low | Frontend |
| CORS origins are hardcoded (plan F20); unknown in-app paths never reach the 404 page (F21) | Low | Not addressed in this cycle |
| Some demo fixtures should be re-checked to confirm that every name and number in them is synthetic | Medium | Team (privacy rule) |

## 7. Traceability

### 7.1 Findings from the plan's audit

| ID | Sev. | Finding (short) | Test evidence | Result |
|---|---|---|---|---|
| F1 | Crit. | Real login path never tested | `tests/security/test_auth_http.py` | Pass |
| F2 | Crit. | Worker and outbox untested | `tests/db/test_outbox_repository.py`, `tests/db/test_worker_runner.py`, `tests/unit/test_worker_leases.py` | Pass; defect 3 fixed |
| F3 | Crit. | Browser tests could not sign in | `frontend/playwright.config.ts`, `frontend/playwright.auth.config.ts` | Done; Clerk-signed run needs keys |
| F4 | Crit. | Signed cursors untested | `tests/unit/test_pagination_cursor.py`, `tests/unit/test_repository_cursors.py` | Pass; defects 5 and 6 fixed |
| F5 | High | No coverage measured | Coverage in both stacks, gated in CI | Done |
| F6 | High | Frontend unit tests not in CI | `.github/workflows/ci.yml` runs `pnpm check` | Done |
| F7 | High | Most backend suites not in CI | CI runs `pytest -m "not live"` | Done |
| F8 | High | Matter and checklist services untested | `tests/db/test_matter_service.py`, `tests/db/test_checklist_service.py`, `src/modules/matter/tests/test_routing.py` | Pass; 2 known gaps |
| F9 | High | Fact promotion policy untested | `src/modules/verification/tests/test_policies.py` | Pass |
| F10 | High | Demo store untested | `frontend/src/lib/store/demo-store.test.ts` | Pass; defect 14 fixed |
| F11 | High | No PostgreSQL in CI | CI PostgreSQL service, `tests/db/` | Done |
| F12 | High | Payment webhook signature untested | `tests/unit/test_payhere_adapter.py` | Pass; defect 11 fixed |
| F13 | Med. | Routers' status codes untested | `tests/security/test_if_match_sweep.py`, `test_tenancy_sweep.py`, `test_unauthenticated_surfaces.py` | Partly: sweeps done, per-router files deferred |
| F14 | Med. | Repositories untested | `tests/db/test_*_repository.py` (matter, checklist, check, draft, approval, verification, auth, billing, obligations, party, outbox) | Done for the listed repositories |
| F15 | Med. | No DOM for component tests | `frontend/src/test/render.tsx`, `status-badge.test.tsx`, `activity-timeline.test.tsx` | Done; two components covered so far |
| F16 | Med. | Duplicated fakes | `tests/factories/` | Done |
| F17 | Med. | No seed script | `scripts/seed_synthetic_matter.py`, `tests/db/test_seed_synthetic_matter.py` | Done |
| F18 | Med. | No retries or reports in browser CI | `frontend/playwright.config.ts` | Done |
| F19 | Med. | Service registry unenforced | `tests/conformance/` | Pass; 1 known gap |
| F20 | Low | CORS hardcoded | — | Not addressed |
| F21 | Low | 404 page unreachable | — | Not addressed |
| F22 | Low | Sinhala specs switched off | `frontend/playwright.config.ts` | Done |

### 7.2 The seven safety rules

| Rule | Test evidence | Result |
|---|---|---|
| 1. A lawyer cannot see another organisation's data | `tests/security/test_tenancy_sweep.py` (every matter-scoped route), `tests/db/test_matter_service.py` | Pass |
| 2. Every material change is in the audit log | `tests/db/test_audit_chain.py`, audit assertions in the service and store tests | Pass; defect 2 fixed |
| 3. Client identifiers never appear in plaintext | `tests/db/test_party_privacy_at_rest.py` (dumps the real database and searches it) | Pass |
| 4. Only the right lawyer can act | `tests/security/test_capability_http.py`, `tests/security/test_auth_http.py` | Pass; step-up policy open (6.3) |
| 5. The API behaves the same way everywhere | `tests/security/test_if_match_sweep.py`, `tests/security/test_obligation_versions.py`, `tests/unit/test_conditional.py` | Pass; notarial gap (6.2) |
| 6. Messages between services are reliable | `tests/db/test_outbox_repository.py`, `tests/db/test_worker_runner.py`, `tests/db/test_notification_idempotency.py`, `tests/conformance/test_event_registry.py` | Pass; 3 known gaps (6.2) |
| 7. Quota and metering work | `tests/db/test_billing_quota.py` | Pass; defect 8 fixed |

### 7.3 The lawyer workflow refusals (plan Appendix A)

| Refusal | Test evidence | Result |
|---|---|---|
| No draft before the lawyer confirms the instrument | `tests/db/test_lawyer_workflow.py` | Pass |
| 1. An open statutory blocker stops draft generation | `tests/db/test_lawyer_workflow.py` | Pass |
| 2. A fact correction makes dependent drafts stale | Server rules tested in the draft module; demo store gap recorded | Partly |
| 3. No approved export before approval | `tests/db/test_lawyer_workflow.py`, `demo-store.test.ts` | Pass |
| 5. Machine confidence is never enough | `tests/db/test_lawyer_workflow.py`, `src/modules/verification/tests/test_policies.py` | Pass |
| A blocked mandatory step needs a reason | `frontend/tests/e2e/refusal-paths.spec.ts` (browser) | Pass |

## 8. Test completion evaluation

### 8.1 Exit criteria (plan Appendix D)

| Criterion | Status | Evidence or reason |
|---|---|---|
| All Critical findings (F1–F4) have passing tests | Met | Section 7.1; the Clerk-signed browser run for F3 needs keys |
| All High findings (F5–F12) have passing tests or an owned exception | Met | Section 7.1 |
| CI runs every suite, with no vacuous path | Partly met | All backend and frontend unit suites run; browser tests are not in CI (Clerk keys) |
| A coverage number exists, is published and ratchets | Met | Section 4.3; plan §A1 updated |
| Each of the seven safety rules maps to a named test file | Met | Section 7.2 |
| No new fake duplicates the shared factories | Met for this cycle | New tests use `tests/factories/` |
| Random-order runs pass three times in a row | Met | Section 4.2 |

**Summary:** of the criteria assessed this cycle, 6 are met and 1 is partly
met. Four further criteria from Appendix D are carried to the next phase, for
the reasons in sections 5 and 6.

### 8.2 Overall assessment

All eight planned commits were delivered. The backend is now tested at every
level on a real database, and every Critical and High finding from the audit
has passing tests. Fifteen defects were found and fixed, two of them Critical,
and every fix is protected by a test that was shown to fail without it.

The testing is **not yet complete** against the plan's sign-off list. The
remaining items are mostly outside the test code: sign-in test keys for
browser automation, the legal team's verification of the form templates, and
decisions that belong to named owners.

**Recommendation:** accept this cycle as complete for the backend and the
frontend logic layer. Keep the plan open until the Clerk keys are provided
and the browser journeys run in CI, and until each known gap in section 6.2
has an owner and a date.

## 9. Evaluation of the data-science parts

Draftly's data-science components are evaluated in the research repository
(`evaluation/runs/`, `ocr-benchmark/`), separately from the platform. This
section reports their measured results as they stand on 2026-09-20. Every
number below comes from a committed metrics file in that repository.

**In one line:** the retrieval components have real numbers and they are low;
the document-reading components have no accuracy number at all, because the
paid runs are blocked on credentials.

### 9.1 Components and how each is measured

| Component | What it does | Evaluation method | Gold standard |
|---|---|---|---|
| Statute retrieval (BM25 baseline) | Finds the statute sections a legal question depends on | IR metrics: recall@k, MRR, nDCG@10 | Derived, unverified |
| Statute retrieval (LSR variant) | Same task, larger question set, no reranking | IR metrics, sliced by the statute's temporal status | Derived, unverified |
| Similar-case retrieval (v1 to v8) | Finds comparable decided cases for a fact pattern | Binary correct or incorrect, graded by 20 independent LLM subagents, one per query | None; appropriateness graded, not matched |
| LawChain reproduction | Reimplements a published retrieval method for comparison | IR metrics on the same 4 questions | Derived, unverified |
| Headnote rule recovery | Extracts the legal rule from a case headnote | Rule-based extractor with an LLM-bounded fallback; outputs flagged for review | None; all outputs unverified |
| OCR and field extraction | Reads scanned deeds and pulls registry fields | Exact-match field accuracy, invented-value rate, cross-run agreement, provenance | 37 labelled fields in 1 of 4 matters |

Two rules in that harness decide what counts as correct, and both are strict on
purpose:

- **Critical identifiers are exact-match only, never fuzzy.** A cadastral
  number read as `00030085091` instead of `00030085090` is a failure whatever
  the string similarity says, because the legal result is completely wrong.
- **A stub run must score 100% with zero character error.** A synthetic page
  with known text is read back by a deterministic reader; if that run is not
  perfect, the harness itself is wrong and no model result from it is believed.

### 9.2 Retrieval results

| Run | Questions | Recall@1 | Recall@5 | Recall@10 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|
| Statute retrieval, BM25 baseline | 10 | 0.250 | 0.540 | 0.590 | 0.616 | 0.520 |
| Statute retrieval, LSR variant (no rerank) | 462 | 0.110 | 0.206 | 0.238 | 0.148 | 0.169 |
| LawChain, reimplemented | 4 | 0.000 | 0.083 | 0.542 | 0.194 | 0.241 |
| LawChain, existing BM25 engine, same questions | 4 | 0.375 | 0.833 | 0.833 | 0.633 | 0.670 |
| LawChain, figures published in the paper | not stated | not stated | 0.936 | not stated | not stated | not stated |

The LSR variant is sliced by whether the statute a judgment relied on is still
in force:

| Slice | Questions | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|
| Applicable | 282 | 0.220 | 0.245 | 0.152 |
| Superseded since judgment | 145 | 0.152 | 0.186 | 0.116 |
| History unknown | 35 | 0.314 | 0.400 | 0.249 |

### 9.3 Similar-case retrieval, by variant

Graded by LLM subagents on the same 20 exam fact patterns. The toggles are
ranking features: verified-only edges, lexical IDF weighting, graph fan-out,
catchword edges, and catchword-to-statute links.

| Variant | Feature under test | Correct out of 20 | Accuracy |
|---|---|---|---|
| v1 | Baseline | 14 | 0.70 |
| v1 rebaseline | Baseline again, different corpus snapshot | 10 | 0.50 |
| v2 | Verified-only edges | 11 | 0.55 |
| v3 | Lexical IDF | 6 | 0.30 |
| v4 | Verified-only and lexical IDF | 5 | 0.25 |
| v5 | Catchword edges | 13 | 0.65 |
| v6 | Graph fan-out weight | 12 | 0.60 |
| v7 | Catchword-to-statute links | 13 | 0.65 |
| v8 | Fan-out, catchword edges and statute links together | 12 | 0.60 |

### 9.4 Document reading

The OCR and field-extraction benchmark defines six runs over 4 matters, 38
documents and 282 pages. On the last recorded run:

- runs A, B, D, E and F, the Gemini routes, **failed** with `401
  UNAUTHENTICATED`: the configured key is not an AI Studio key, and the Vertex
  route is not enabled on the project;
- run C, the open-source box engine, was **skipped**: the candidate engine is
  GPL-3.0 and the licence question is unresolved;
- so **no field-accuracy figure exists yet** for any pipeline.

What has been measured is a full-page vision pass over one matter:

| Measure | Value |
|---|---|
| Pages read | 26 of 26, none failed |
| Mean confidence | 0.904 |
| Characters per page | 1220.7 |
| Script mix | Latin 63.7%, Sinhala 21.7%, Tamil 7.0%, digits 7.6% |
| Seconds per page | 3.38 (maximum 6.74) |
| Estimated cost, full corpus | USD 0.04 |

### 9.5 How far these results can be trusted

Every run in the research repository is labelled development-only, and the
label is accurate:

- gold answers are **derived, not lawyer-verified**, for every retrieval run;
- similar-case accuracy is **graded by an LLM**, which is an appropriateness
  judgement, not an IR measurement against known-relevant documents;
- the question sets are small: 20 queries for similar-case work, 10 for the
  BM25 baseline, 4 for the LawChain comparison;
- only 1 of 4 matters in the OCR corpus is labelled, with 37 fields;
- every headnote rule output is marked unverified.

Under the platform's own rule that only lawyer-verified facts may reach an
approved output, none of these components is fit to fill a legal form
unattended today. The platform enforces that rule independently of the models,
and the tests in section 7.3 hold it.

## 10. Error analysis of the data-science parts

The failures are concentrated, not spread evenly: the same questions fail in
every configuration, and the weakest slice is statutes that changed after the
judgment was written.

### 10.1 Statute retrieval: most questions return nothing usable

Of 462 questions, **352 (76.2%)** have no relevant result in the top 10, and
only 110 (23.8%) reach full recall@10.

| Slice | Questions | No relevant result in top 10 | Share |
|---|---|---|---|
| Applicable | 282 | 213 | 75.5% |
| Superseded since judgment | 145 | 118 | 81.4% |
| History unknown | 35 | 21 | 60.0% |

**Reading:** the system is weakest exactly where the law has moved on. That is
also where a wrong answer is most dangerous, because a lawyer shown a repealed
section may rely on it.

### 10.2 Small question sets flattered the baseline

The BM25 baseline scored recall@10 of 0.590 on 10 questions. Retrieval on 462
questions scores 0.238. The 10-question figure was not wrong, it was
unrepresentative: a difference of more than two times, produced by sample size
alone. Any decision taken on a 10-question result should be taken again.

### 10.3 A hard core of similar-case queries

Across all nine similar-case runs, four queries (`scr-03`, `scr-05`, `scr-15`,
`scr-16`) fail in **every** configuration, and three more fail in eight of
nine. No ranking feature moved them.

| Queries | Failed in |
|---|---|
| scr-03, scr-05, scr-15, scr-16 | 9 of 9 runs |
| scr-04, scr-19, scr-20 | 8 of 9 runs |
| scr-02, scr-09 | 5 of 9 runs |
| 8 other queries | 1 or 2 runs each |

**Reading:** a stable failing core that re-ranking never touches usually means
the right case is missing from the corpus, or the query needs reasoning the
index cannot express. More ranking work is unlikely to pay; the next experiment
should check whether the answer is in the corpus at all.

### 10.4 Two features made the results worse

Lexical IDF weighting dropped accuracy from 0.70 to 0.30, and combining it with
verified-only edges dropped it to 0.25. Catchword edges and statute links were
the only features that stayed near the baseline. This negative result is worth
recording: the intuitive improvement was the harmful one.

### 10.5 The grader itself is unstable

The baseline was graded 0.70 in one run and 0.50 in a repeat of the same
configuration. The corpus fingerprint also changed between the two, so the
experiment cannot separate grader variance from corpus change. Either way, a
20-point swing on an unchanged pipeline is larger than most of the differences
the variants are trying to measure, so no ranking of these variants is safe.

### 10.6 Where the headnote extractor gives up

182 cases needed the LLM-bounded fallback because the rule-based extractor
abstained. The reasons name the shapes it cannot parse:

| Abstain reason | Cases |
|---|---|
| Rule text too short | 63 |
| Catchword block too long | 59 |
| Catchwords are not a topic list | 39 |
| No catchword terminator | 18 |
| Rule is itself a catchword list | 2 |
| Rule has too few words | 1 |

All 175 graded outputs remain unverified, so none may feed an approved output.

### 10.7 Document reading: the error is in the experiment, not the model

The dominant failure is environmental, not statistical: five of six pipelines
never ran. The credential error is a configuration fix, and the licence
question needs a decision rather than research. Until both are cleared, the
project has no evidence for its most lawyer-visible claim, that it can read a
scanned deed accurately.

The one signal available is script-dependent confidence: the overall mean is
0.904, but the Sinhala-dominant identity-card pages read at 0.818. Sinhala is
21.7% of all characters in the corpus, so a weakness there is not a corner
case.

### 10.8 What to do next

1. Fix the Gemini credentials and re-run A, B and D, so a field-accuracy number
   exists at all.
2. Settle the OCR engine licence question, which blocks runs C, E and F.
3. Label a second and third matter, so field accuracy does not rest on one
   bundle.
4. Check corpus coverage for the seven persistently failing similar-case
   queries before tuning ranking again.
5. Replace LLM grading with a small human-verified relevance set, or report
   both and treat the LLM figure as indicative only.
6. Re-run the BM25 baseline on the 462-question set, so baseline and variant
   are comparable.
7. Report retrieval by difficulty tier, as the project's own research summary
   recommends: an aggregate score hides that keyword-explicit questions succeed
   while reasoning-heavy ones fail.

## 11. Test deliverables

- 59 commits on `platform/praveen`, each following the Conventional Commits
  format (listed in Appendix A);
- the new and extended test suites under `backend/tests/`,
  `backend/src/modules/*/tests/`, `frontend/src/**/*.test.ts(x)` and
  `frontend/tests/e2e/`;
- the CI workflow `.github/workflows/ci.yml` with PostgreSQL, coverage and
  gates;
- the coverage baseline and re-measurement recorded in the plan's §A1;
- this report.

## 12. Reusable test assets

| Asset | Location | Reuse |
|---|---|---|
| Synthetic factories (ids, clock, audit fake, token minter with a local key set) | `backend/tests/factories/` | Any backend test |
| Per-test PostgreSQL schema with real migrations and rollback | `backend/tests/db/fixtures.py` | Any database test |
| Security harness: the real app with only the key source replaced | `backend/tests/security/harness.py` | Any HTTP-level test |
| OpenAPI-driven route sweeps | `backend/tests/security/test_*_sweep.py` | New routes are covered automatically |
| Synthetic seed script | `backend/scripts/seed_synthetic_matter.py` | Local development and demos |
| Fetch recorder for API clients | `frontend/src/test/fetch-recorder.ts` | Any frontend API module |
| Render helper with the real translations | `frontend/src/test/render.tsx` | Any component test |

## 13. Lessons learned

1. **Measure before adding tests.** The first finding was that CI ran a small
   part of the existing tests. Making CI honest (stage 1) came before writing
   anything new, and exposed tests that had never run.
2. **Test on the real database.** Twelve of fifteen defects appeared only on
   PostgreSQL: foreign-key ordering, concurrency and data-at-rest. Fakes and
   SQLite hid all of them.
3. **Prove each test can fail.** Breaking the code on purpose caught several
   tests that would have passed anyway, for example because a test ran in the
   wrong order or a search missed an encoded value.
4. **Sweep rather than select.** Tests generated from the OpenAPI description
   found routes that a hand-written list would have missed, and will cover
   routes that do not exist yet.
5. **Record gaps as tests.** Strict expected-failure tests turn open questions
   into visible, dated work instead of comments that go stale.
6. **Ratchet coverage.** A floor set at today's number is accepted by the team;
   a fixed 80% target on day one would have been switched off.
7. **Keep a human in the loop for legal content.** Tests may check the
   structure of legal text, but never write or change it.

## 14. Approvals

| Role | Name | Decision | Date |
|---|---|---|---|
| Test author | Praveen De Silva | Submitted | 2026-09-19 |
| Test or team lead | | | |
| Product owner | | | |

## 15. Mapping to IEEE 829 (Test Summary Report)

| IEEE 829 section | Where it is in this report |
|---|---|
| Test summary report identifier | Document control table |
| Summary | Sections 1 and 8.2 |
| Variances | Section 3 |
| Comprehensive assessment | Sections 2.4, 4.3 and 8 |
| Summary of results | Sections 4, 6.1 and 9 |
| Evaluation | Sections 6.2, 6.3, 8 and 10 |
| Summary of activities | Sections 2.2, 2.5 and Appendix A |
| Approvals | Section 14 |

## Appendix A. Commit log

Commits on `platform/praveen` from 2026-09-18 to 2026-09-19, oldest first.

| Stage | Commit | Message |
|---|---|---|
| 1 | `8615109` | test(e2e): let the Playwright app specs run signed in (F3) |
| 1 | `002cbc0` | ci(test): run the frontend unit tests in CI (F6) |
| 1 | `78a0da9` | ci(test): run the whole backend suite in CI (F7) |
| 1 | `115377a` | ci(test): run the real-Postgres suite in CI (F11) |
| 1 | `009b059` | test(coverage): measure coverage in both stacks and record the baseline (F5) |
| 1 | `7316c93` | test(e2e): retry and report in CI, pin the Sinhala toggle on (F18, F22) |
| 1 | `6671336` | test(e2e): sweep every app route and stop overwriting review evidence |
| 2 | `e82f035` | test(fixtures): share one audit fake, fact tier and synthetic ids (F16) |
| 2 | `638d445` | test(db): add a migrated, rolled-back Postgres session per test |
| 2 | `d353f36` | fix(party): stop the event log from crashing every party create |
| 2 | `f93afda` | feat(seed): seed a synthetic smoke matter through the real services (F17) |
| 3 | `57348e4` | test(auth): exercise the real token path over HTTP (F1) |
| 3 | `053cfa2` | test(auth): enforce roles, platform grants and step-up over HTTP |
| 3 | `a9c3b68` | test(security): sweep every matter-scoped route for cross-tenant leaks (Rule 1) |
| 3 | `071aaa0` | test(security): guard the routes that take no bearer token (§8.4) |
| 3 | `d11a8c9` | test(web): cover how the middleware composes its auth gates (§8.5) |
| 3 | `f93f827` | fix(platform): sign the party and matter-agent pagination cursors (F4) |
| 3 | `a04e17b` | test(platform): pin If-Match and ETag translation to api-conventions §3 |
| 3 | `781c317` | test(outbox): cover backoff and the claim protocol on real Postgres (F2) |
| 3 | `d02ce0a` | fix(worker): reap each claim against its own job type's lease (F2) |
| 3 | `153a73e` | test(worker): pin the handler-outcome mapping and record the known gaps (§6.4, §6.5) |
| 3 | `a163270` | fix(audit): serialise each user's chain so concurrent writes cannot fork it (Rule 2) |
| 3 | `403db93` | fix(migrations): register every model with autogenerate and test the chain (§5.3) |
| 3 | `51ca560` | test(privacy): dump real Postgres and find no plaintext identifier (Rule 3, §5.4) |
| 3 | `261d50a` | fix(api): sign the matter, approval, check, document and draft list cursors (F4) |
| 3 | `491b767` | test(db): hold the matter repository to the §5.3 baseline |
| 3 | `4695857` | test(db): hold the checklist repository to the §5.3 baseline |
| 3 | `7895165` | test(db): hold the legal-issue repository to the §5.3 baseline |
| 3 | `c12ee89` | test(db): hold the generated-form repository to the §5.3 baseline |
| 3 | `d09f49d` | test(db): hold the approval repository to its append-only rules |
| 3 | `6980259` | test(db): hold the fact repository to versioning and the confirmed tier |
| 3 | `939d945` | test(db): hold the user and identity repositories to their keys |
| 3 | `b107f97` | fix(billing): store a plan before its entitlements so creating one works |
| 3 | `975ee72` | fix(billing): serialise each user's quota changes (Rule 7) |
| 3 | `1ca705e` | test(db): hold notification's once-only keys on Postgres |
| 3 | `867313a` | fix(obligations): store an obligation before its confirmation so creating one works |
| 3 | `8edf8bd` | fix(party): store a screening result before its match detail |
| 3 | `e87987d` | test(verification): pin the fact promotion policy (F9) |
| 3 | `9852ec1` | fix(billing): refuse a forged PayHere signature instead of raising (F12) |
| 3 | `b747d1c` | fix(notification): verify the Resend signature before decoding the body |
| 3 | `65ef792` | test(matter): pin intake routing and check it against the question catalogue (F8) |
| 3 | `ad52f30` | test(task): pin the checklist's three safety rules across every status combination |
| 3 | `b4e8a35` | fix(notarial): number an attestation in its Colombo register year |
| 3 | `9d90249` | test(matter): cover MatterService on Postgres (F8) |
| 3 | `bbf7b1f` | test(task): cover ChecklistService on Postgres (F8) |
| 3 | `2cd5fdb` | test: give the new module test files unique import names |
| 3 | `a27fffa` | test(api): require If-Match on every versioned write (Rule 5) |
| 3 | `145f94e` | test(conformance): enforce the service registry in the suite (F19) |
| 3 | `28f00a0` | test(contract): fail when the committed RTA rule-pack contracts drift (§4.3) |
| 3 | `6e648c3` | test(workflow): hold Appendix A's refusals through the real services (§4.2) |
| 4 | `eed5fa7` | test(web): cover the demo store's actions, audit trail and migrations (F10) |
| 4 | `fb090db` | test(web): cover draft building and the matter stage map (§3.2) |
| 4 | `cef9159` | test(web): cover label completeness, fact label keys and the workflow catalogue (§3.2) |
| 4 | `ac6a614` | test(web): cover the seven API client modules (§3.2) |
| 4 | `03399de` | refactor(web): move the intake helpers out of the new-matter screen and test them (§3.2) |
| 4 | `0ef0c76` | test(web): add a DOM for component tests and cover the badge and timeline (F15) |
| 4 | `93414d6` | test(e2e): hold the workflow override refusal in the browser (§7.2) |
| 4 | `26290c2` | ci: ratchet coverage floors one point under today's numbers (§11.3) |
| 4 | `98c5ce4` | test: shuffle the backend suite on every run (§11.5) |

## Appendix B. How to reproduce the results

Backend, from `backend/`, with PostgreSQL 16 running on port 55432:

```bash
export DRAFTLY_E2E_DATABASE_URL=postgresql+psycopg://test:test@localhost:55432/draftly_test
export DRAFTLY_E2E_REQUIRE_DATABASE=1
uv run pytest -m "not live" --cov --randomly-seed=1111
```

Frontend, from `frontend/`:

```bash
pnpm test:coverage
pnpm exec vitest run --sequence.shuffle --sequence.seed=1111
pnpm exec playwright test refusal-paths
```

The whole local gate, from the repository root:

```bash
pnpm check
```
