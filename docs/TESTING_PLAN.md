# Draftly — Testing Plan

**How to read this.** Part A is for approval — what we protect, what blocks M3,
what it costs, what decisions are needed. Part B is the engineering plan — file
paths, test names, fixtures, CI wiring, thresholds. The appendices hold the
lawyer-workflow scenario, the synthetic data roster, the commit plan, and the
sign-off checklist.

---

## PART A — SUMMARY AND APPROVAL

### A1. Where we actually are

The honest starting position, because the previous version of this document
said "the app has no tests" and that is not true.

| Stack | Runner | Test files | Runs in CI? |
|---|---|---|---|
| Backend | pytest + `pytest-asyncio` | 36 in `backend/tests/` + 30 in `src/modules/*/tests/` = **66** | Partially — see F7 |
| Frontend unit | Vitest 3.1.2 | **13**, colocated as `src/**/*.test.ts` | **No** — see F6 |
| Frontend E2E | Playwright + axe-core | **8** specs | **No** |

Some areas are genuinely well tested and must not be rewritten:

- `content_governance` — 165 assertions over taxonomy, eligibility, rule-pack
  integrity, form registry, workflow roles. The 22 prescribed instruments and
  the form-number collisions (Gazette Form 31 vs Ti.Re.31) are covered.
- `check/tests/test_runners.py` — all 17 deterministic V0 check runners.
- `approval` and `draft` policies — 89 tests over the §9.3 fact→field mapping,
  §9.4 preflight, and §10.7 staleness rules.
- `matter_agent` — permission-as-intersection, the bounded turn loop, the
  executor-decides / model-proposes boundary.
- `tests/unit/test_bootstrap_*.py` — 19 tests on the environment gates that keep
  stub identity, stub extraction, and local-disk storage out of production.
  These are the guardrails `DEPLOYMENT_PLAN.md` depends on.

The problem is not absence. It is that the gaps are concentrated in exactly the
places where a silent failure is most expensive: the authentication path, the
background worker, the intake routing that decides which legal form gets used,
and the auto-promotion rules that decide whether a machine guess can become a
fact without a lawyer looking at it.

**Coverage baseline (F5, measured 2026-09-18).** This is Step 1 of §11.3:
recorded, not gated.

| Stack | Lines | Branches | Measured with |
|---|---|---|---|
| Backend `src/` | **77%** (13802 / 17905) | **51%** (1466 / 2876) | `uv run pytest -m "not live" --cov`, real Postgres on |
| Frontend `src/` | **2.4%** (292 / 12419) | not meaningful yet | `pnpm test:coverage` |

The frontend branch figure is left out on purpose: v8 counts branches only in
files a test loads, so it reads 72% while almost no component is loaded. Lines
is the honest frontend number, and it is low because F10 and F15 are open.
Backend combined line-and-branch coverage is 73%. CI prints both numbers on
every run.

### A2. What we are protecting

Seven safety rules. Each one is a thing that, if it broke silently, would
produce a wrong legal artifact, leak a client identifier, or cross a tenant
boundary. Each now points at the engineering section that covers it.

#### Rule 1 — A lawyer cannot see another organisation's data

Org A's lawyer creates matter M1. Org B's lawyer requests M1. The result must be
**"Not Found", not "Forbidden"** — B must not be able to learn that M1 exists.
The denial is recorded in the audit log.

Covered today for `party` and `matter_agent` only. → **§8.3**, a single
parametrised sweep over every matter-scoped route in `contracts/services.yaml`.

#### Rule 2 — Every material change is in the audit log

Create matter, upload document, verify a fact, approve a draft, export — each
appends an audit event. The log is a **per-user hash chain**: each entry carries
the previous entry's hash, so a deleted or edited entry is detectable.

The hash function is tested. The writer that threads `prev_hash` is not.
→ **§5.3**, `test_audit_chain.py`.

#### Rule 3 — Client identifiers never appear in plaintext

NIC, name, address, deed and registry numbers. Not in logs, not in a database
dump, not in an error message. Identifiers are encrypted at rest with a blind
index for lookup, and reading one back requires an explicit stated purpose.

Covered against a recording harness, not a real database. → **§5.4**.

#### Rule 4 — Only the right lawyer can act

Capability checks by role, step-up authentication for role changes and
approvals, and a responsible-lawyer requirement on approval.

The capability map is well tested in isolation. What is missing is the HTTP
half — no test has ever seen a 401 from a bad token or a 403 from a wrong role.
→ **§8.1, §8.2**. This is finding F1 and it is the most serious one.

#### Rule 5 — The API behaves the same way everywhere

Pagination, error envelope shape, version checking via `If-Match`, retry safety
via `Idempotency-Key`.

Enforced for `party` only. Fourteen of sixteen routers are imported by no test.
→ **§4.1**, a five-test baseline applied to every router.

#### Rule 6 — Messages between services are reliable

An event is published once, delivered at least once, retried with backoff, and
dead-lettered rather than lost. Two workers never process the same message.

The worker has **no test file at all**. → **§6**. This is finding F2.

#### Rule 7 — Quota and metering work

Reserve, consume, release. Over-quota is refused. A failed operation returns its
reservation rather than burning it.

→ **§4.2**, `test_billing_quota.py`.

Beyond the seven rules, the full lawyer workflow and its five refusal cases are
in **Appendix A**, and they get tested at the API layer (**§4.2**) rather than
only through a browser.

### A3. Phases, and what blocks M3

#### Phase 1 — blocks M3

Two things, in order.

**Phase 1a, the unblocking set.** Before any new test is worth writing, the
harness has to work. Right now the frontend test suite never runs in CI, the
backend CI command skips 43 of 66 test files, one of the paths it does run is an
empty directory, and seven of eight Playwright specs fail on startup because
there is no authentication strategy. Fixing this is roughly two days and makes
every existing test count for something. → commit 1 in Appendix C.

**Phase 1b, the safety tests.** Rules 1–7 above, the workflow and its five
refusal cases, and the four Critical findings. → commits 2–7.

**Environment:** in-memory and SQLite for most of it, with a real Postgres
service added to CI (§5.1) because the outbox, the audit chain, and the privacy
guarantees cannot be verified without one. The previous version of this document
assumed Phase 1 needed no database; that turned out to be wrong for three of the
seven rules.

#### Phase 2 — after M3

Frontend component testing (needs a DOM environment added first, F15), the
remaining repository tests, the E2E recovery journeys, and the coverage ratchet
reaching its Step 2 targets.

#### Phase 3 — hardening

Everything in §9.3 that depends on features not yet built, retention and legal
hold (there is a skipped test waiting on `retention_service`), and the
conformance suite growing as `contracts/services.yaml` grows.

### A4. Status

Honest replacement for the previous all-"not started" table. "Partial" means a
suite exists but covers one module rather than the system.

| Safety rule | Status today | Remaining | Blocks M3? |
|---|---|---|---|
| 1. Tenancy isolation | Partial — `party`, `matter_agent` | Sweep every matter-scoped route | **Yes** |
| 2. Audit coverage | Partial — hash function only | Chain writer, concurrency, tamper detection | **Yes** |
| 3. Privacy / PII | Partial — recording harness | Real-database dump test | **Yes** |
| 4. Access control | Partial — policy map only | The entire HTTP path (F1) | **Yes** |
| 5. API conventions | Partial — `party` only | 14 routers × 5 baseline tests | **Yes** |
| 6. Events and worker | **None** | Outbox policies, runner, handlers (F2) | **Yes** |
| 7. Metering / quota | Partial — service unit tests | Reserve/consume/release at the API | Maybe |
| Workflow happy path | Browser only | API-layer walk | **Yes** |
| Workflow 5 refusals | Partial | API-layer, all five | **Yes** |
| CI actually runs it all | **No** (F6, F7, F11) | Three edits to `ci.yml` | **Yes** |
| Coverage measurable | **Yes** — baseline in §A1 (F5) | Per-path thresholds, §11.3 Step 2 | No |

### A5. Timeline

| Week | Work | Output |
|---|---|---|
| 1 | Phase 1a — commit 1 | CI runs every suite; Playwright works; coverage baseline published |
| 2 | Foundations and security — commits 2–4 | F1, F2, F4 closed; factories, DB fixture and seed script exist |
| 3 | Persistence and domain — commits 5–6 | Rules 2 and 3 closed; matter/task/verification covered |
| 4 | API surface — commit 7 | Rules 1, 5 and 7 closed; every router has a baseline |
| 5 | Frontend, E2E and the ratchet — commit 8 | Store tested; refusal journeys; thresholds on. Sign-off (Appendix D) |

Roughly four to five weeks, which is a week longer than the previous estimate.
The difference is Phase 1a and the Postgres service, both of which the earlier
plan did not account for.

### A6. Decisions needed

1. **Database in CI — settled, needs confirmation.** Docker Postgres on every
   PR, real Neon on push to `main` only. Docker is free, offline, and
   sub-minute; Neon catches pooler behaviour and autosuspend cold start, which
   `DEPLOYMENT_PLAN.md` §9.7 flags as the likely first bottleneck. Details in
   §5.1.
2. **Coverage gate style.** Recommended: ratchet from a measured baseline (§11.3)
   rather than a fixed 80% cliff. A hard gate on a repo with no current number
   fails the next PR and gets switched off within a week.
3. **Does `/kitchen-sink` ship?** It is a design-system showcase page currently
   in the production route tree with no guard. Testing it, guarding it, or
   deleting it are all fine; leaving it undecided is not.
4. **The missing scheduler.** `backend/docs/jobs-and-workers.md` §1 specifies a
   `python -m workers.runner --sched` entrypoint electing a leader through a
   Postgres advisory lock, and `DEPLOYMENT_PLAN.md` §1.3 depends on it. Neither
   the flag nor any `pg_advisory` call exists, so nine scheduled jobs have no
   runtime. This is implementation work, not a documentation fix, and a test
   cannot bridge it. See §6.5.

### A7. Rules that never bend

From `CLAUDE.md`, restated because they bind test code too:

- **Synthetic data only.** No real names, NICs, addresses, deed or registry
  numbers, ever, in any fixture or seed script. All demo content is labelled as
  synthetic. Nothing is copied from `../draftly-research/data/raw/`.
- **No Harvey assets** in fixtures, screenshots, or expected strings.
- **Legal wording is human-owned.** A test may assert that prescribed statutory
  text is present and unmodified. A test may not author or alter it.
- **`uv` for Python, `pnpm` for Node.** `pytest-cov` goes in via `uv add --dev`,
  never pip.
- **Deterministic fixtures.** Fixed ids and timestamps. No `Date.now()`,
  `Math.random()`, `uuid4()`, or `Faker` inside a factory.
- Human gates are not self-approvable: the legal correctness of any scenario
  touching prescribed text, the synthetic roster, and any decision to enable
  `PROVIDER_DATA_APPROVAL` for a test run.

### A8. Explaining this

**Two minutes.** "We have tests, but CI only runs about a third of them, and the
parts with no tests at all are the login path and the background worker. The
plan fixes the CI wiring first, then covers the seven safety rules before M3.
Four to five weeks."

**Five minutes.** Add: the seven rules from §A2, the fact that the previous plan
underestimated because it assumed no database was needed, and the two findings
worth naming out loud — no test has ever seen a 401 from a bad token, and the
background worker that moves every job through the system has no test file.

**Ten minutes.** Walk the findings table in §0, then Appendix A for what a real
matter does end to end and where each refusal is enforced.

---

## PART B — ENGINEERING PLAN

### 0. Findings

Severity per the `test-master` rubric: **Critical** = security or data-loss
exposure, **High** = major functionality unverified, **Medium** = partial
coverage with a workaround, **Low** = cosmetic or cheap to close.

| # | Severity | Finding | Location |
|---|---|---|---|
| F1 | Critical | The real token path (`HTTPBearer` → `get_bearer_token` → `AuthService.build_request_context` → `ClerkIdentityAdapter.validate_token`) is never executed by any test. Every test overrides `get_request_context`, so **no test observes a 401 from a missing, expired, or tampered token**. | `backend/src/api/deps.py` |
| F2 | Critical | `src/workers/runner.py` has no test file. The outbox claim / retry / dead-letter path is unverified. `test_matter_agent_api.py` defers to "the worker's own tests"; they do not exist. | `backend/src/workers/runner.py` |
| F3 | Critical | Playwright has no auth strategy — no `storageState`, no `globalSetup`, no sign-in helper, no `AUTH_BYPASS` injection. With the repo's `.env` (`AUTH_BYPASS=false`, Clerk configured) seven of eight specs redirect to `/sign-in` and fail. | `frontend/playwright.config.ts` |
| F4 | Critical | HMAC-signed pagination cursors (`encode_cursor` / `decode_cursor`) have no test. A forged or truncated cursor is unverified against a signing-key bypass. | `backend/src/platform/api/pagination.py` |
| F5 | High | Zero coverage instrumentation in either stack. No `pytest-cov`, no `@vitest/coverage-v8`, no threshold, no upload. No coverage number is measurable today. | repo-wide |
| F6 | High | `pnpm --dir frontend test` (13 vitest files) never runs in CI. `ci.yml` calls `typecheck`/`lint`/`build`/`check:markdown` individually instead of the root `pnpm check`, which does include it. | `.github/workflows/ci.yml` |
| F7 | High | CI runs `uv run pytest tests/unit tests/contract tests/conformance`, excluding `tests/security/`, `tests/privacy/`, `tests/integration/`, and all 30 co-located module suites. `tests/conformance/` is an empty `.gitkeep` directory, so that path passes vacuously. `CLAUDE.md` mandates a bare `uv run pytest`; CI does not honour it. | `.github/workflows/ci.yml` |
| F8 | High | `MatterService` (12 public methods) and `ChecklistService` (9 methods) — the intake, routing, and checklist-compilation core — have no test file. `src/modules/task/tests/` and `src/modules/auth/tests/` contain only `__init__.py`. | `backend/src/modules/{matter,task}/` |
| F9 | High | `verification.domain.policies` is untested: `may_auto_promote`, `guard_human_confirmation`, `guard_evidence`, `guard_negative_conclusion` — the layer deciding whether a machine value becomes a fact without a lawyer. | `backend/src/modules/verification/domain/policies.py` |
| F10 | High | `src/lib/store/demo-store.ts` (806 lines, 20 actions, persisted-state migrations) is the frontend's entire offline domain state machine and audit emitter. Zero unit tests; verified only through a 180-second browser spec. | `frontend/src/lib/store/demo-store.ts` |
| F11 | High | No Postgres service in CI. DB-touching tests skip silently. The `integration` marker is applied to exactly one file, so the other three in `tests/integration/` run under `-m "not integration"` anyway. | `.github/workflows/ci.yml` |
| F12 | High | PayHere webhook signature verification has no test, on an unauthenticated public route. | `backend/src/modules/billing/infrastructure/payhere_adapter.py` |
| F13 | Medium | Fourteen of sixteen routers are imported by no test. `test_openapi_contract.py` asserts schema shape only — never status codes, `If-Match` handling, or error envelopes. No test asserts a 403/404/412/428 outside the party and matter-agent suites. | `backend/src/modules/*/api/router.py` |
| F14 | Medium | Twelve of fifteen SQL repositories have no test. Optimistic-concurrency version bumps and cursor SQL are largely unverified, including the audit hash-chain **writer**. | `backend/src/modules/*/infrastructure/repository.py` |
| F15 | Medium | Vitest has no DOM environment and no Testing Library. All 23 logic-bearing client components are structurally untestable until `jsdom`/`happy-dom` + `@testing-library/react` are added. | `frontend/vitest.config.ts` |
| F16 | Medium | `FakeAudit` is implemented four times and `fact_tier` three times across `tests/fixtures/` and four module `fakes.py` files. No shared factory module; `USER_ID`/`MATTER_ID`/`NOW` are redefined per module. | repo-wide |
| F17 | Medium | No seed script anywhere. There is no supported way to materialise a test matter + party + document into a database. | `backend/scripts/` |
| F18 | Medium | Playwright `retries` is unset (0) on a suite containing a 180 s and a 240 s multi-step walk. `reporter: "line"` produces no CI artifact. `webServer` runs `pnpm dev`, so design-audit's strict CSS-token assertions test a dev build. | `frontend/playwright.config.ts` |
| F19 | Medium | `tests/conformance/` is referenced by `contracts/services.yaml` as the enforcement point for service levels, tenancy, and idempotency exemptions. The directory does not exist, so the registry is unenforced documentation. | `backend/contracts/services.yaml` |
| F20 | Low | CORS origins are hardcoded in `src/main.py` (`localhost:3000`, `localhost:4310`) with `allow_credentials=True`. No test asserts the allowlist; `DEPLOYMENT_PLAN.md` §4.1 already flags it as a pre-deploy edit. | `backend/src/main.py` |
| F21 | Low | The `[...slug]` catch-all swallows genuine 404s, so `not-found.tsx` is effectively dead for in-app paths and `/workflows/anything` renders a hardcoded demo matter. | `frontend/src/app/[...slug]/page.tsx` |
| F22 | Low | `MULTILINGUAL_LANGUAGE_SUPPORT=false` in `.env` while two specs require the Sinhala toggle. Those specs are config-dead as the repo stands. | `frontend/.env` |

**Order of work:** F3 → F6 → F7 (make the harness and CI honest) → F5 (get a
number) → F1, F2, F4, F12 (security-critical) → F8, F9 (domain core) → the rest.

### 1. Existing infrastructure and what runs where

Backend suite layout and its purpose:

- `tests/unit/` (17 files) — services and policies over hand-written in-memory
  port doubles. No DB, no network.
- `tests/contract/` (8) — wire shapes plus committed-artifact staleness gates
  (`contracts/openapi.v1.json`, party API conventions).
- `tests/integration/` (4) — `test_matter_agent_api.py` is the broad one: real
  router, real service graph, real SQLAlchemy repositories over in-memory SQLite
  built from a hand-picked 11-table subset. `test_matter_agent_neon_e2e.py` is
  the only real-Postgres test in the repo and the best single test in it.
- `tests/security/` (2), `tests/privacy/` (1) — party and notification scoping,
  identifier encryption at rest.
- `tests/e2e/` (4) — three live-provider probes gated on `RUN_LIVE_TESTS=1`,
  plus one cross-service slice over fakes.
- `src/modules/*/tests/` (30) — the richest suites. `document` (11),
  `content_governance` (6), `matter_agent` (5), `check` (3), `approval` (2),
  `draft` (2), `verification` (1). `auth/tests/` and `task/tests/` are empty.

| Suite | Local (`uv run pytest` / `pnpm check`) | CI |
|---|---|---|
| `tests/unit`, `tests/contract` | ✅ | ✅ |
| `tests/conformance` | ✅ (empty) | ✅ (vacuous) |
| `src/modules/*/tests` (30 files) | ✅ | ❌ |
| `tests/security`, `tests/privacy` | ✅ | ❌ |
| `tests/integration` | ✅ (Postgres one skips) | ❌ |
| `tests/e2e` live probes | skipped without env | ❌ |
| Vitest (13 files) | ✅ via `pnpm check` | ❌ |
| Playwright (8 specs) | manual only | ❌ |

Three of those eight rows are §11.1, the first deliverable.

### 2. Critical modules and behaviours

"Critical" means a silent failure produces a wrong legal artifact, leaks a
client identifier, crosses a tenant boundary, or loses evidence.

#### C1 — Tenant and matter isolation

Enforced server-side on every read and write; `FakePartyRepo` is the canonical
shape, scoping every read by `user_id`. A cross-tenant read returns **404, never
403** — existence must not leak. Covered for party and matter-agent; unverified
for matter, task, check, draft, approval, verification, obligations, notarial
register. → §8.3.

#### C2 — Evidence immutability and the audit hash chain

`audit.infrastructure.repository` writes a **per-user** chain via
`get_last_hash(user_id)` → `prev_hash`. The canonicalisation function is tested;
the writer that threads `prev_hash` is not. A broken chain is undetectable
without a test that writes N events and walks the links.

Originals are immutable — `tests/unit/documents/test_immutability.py` covers the
filesystem and GCS adapters and is a named release blocker. Supersession must
create a new version with a `DocumentVersionRelationship`, never mutate or
delete.

#### C3 — Lawyer-in-the-loop gates

The product rests on machine output never reaching an approved artifact
unreviewed:

- `verification.domain.policies` — `may_auto_promote`, `guard_human_confirmation`,
  `guard_evidence`, `guard_negative_conclusion`: **untested** (F9).
- `check.domain.policies.blocks_draft_generation` / `blocks_approval` /
  `blocks_registration_ready_export` — tested, 30 policy tests.
- `approval.domain.policies.guard_approval` / `require_responsible_lawyer` /
  `approval_matches_snapshot` — tested, 43 tests.
- `draft.domain.policies` staleness §10.7 — tested, 46 tests.
- Frontend mirror: `EditorFactChipNode.attrs.verification_state` is typed to
  `"verified" | "corrected"` only, and `fact-chip.test.ts` asserts the insertion
  rule. Its producer, `lib/templates/build-document.ts`, is untested.

#### C4 — Optimistic concurrency

`require_if_match`: missing **or** malformed ⇒ 428; stale ⇒ 412. Applied on 20+
mutating routes. Three routers hand-roll their own variant (`party`,
`obligations`, billing's manual header read), and **`notarial_register` has no
`If-Match` at all** on nine mutating routes. Only the party variant is tested.

#### C5 — Identifier confidentiality

NIC and passport values encrypted at rest with a blind index
(`LocalFieldEncryptionAdapter`); `read_identity_value` requires an explicit
`purpose`. `platform/privacy.py` provides `assert_no_private_content`. Covered
by 11 tests against a recording session, not live Postgres. → §5.4.

#### C6 — The outbox

Single table, `UniqueConstraint(kind, name, idempotency_key)`,
`SELECT … FOR UPDATE SKIP LOCKED` (**Postgres only** — on SQLite the claim is
unlocked). `backoff_seconds(attempts) = min(2**attempts * 5s, 30min)` ±20%
jitter, `DEFAULT_MAX_ATTEMPTS = 8`, 120 s leases reaped by `reap_leases`. Only
`backoff_seconds` has any test.

#### C7 — The provider gates

`bootstrap.py` refuses at boot: stub identity outside `{local, test, ci}`, stub
extraction outside the same set, filesystem storage outside the same set, GCS
without `DRAFTLY_STORAGE_REAL_DATA_APPROVED=true`, Gemini without a key.
`_assert_bucket_policy` refuses non-uniform bucket-level access, unenforced
public-access prevention, or the wrong region. Well covered (19 tests) and worth
protecting.

#### C8 — Auth and capability policy

`CAPABILITY_MAP` + `is_capability_granted(role, capability)` — 23 tests.
`require_step_up` on role changes. `ClerkIdentityAdapter` checks `azp` against
`clerk_authorized_parties` and applies `clerk_leeway_seconds=30` to `iat`/`nbf`/
`exp`. Helpers tested in isolation; the wired HTTP path is not (F1).

#### C9 — Intake and routing

`new-matter-screen.tsx` (1595 lines, ~20 state slices) drives the questionnaire
deciding the matter subtype, which decides the checklist, which decides the
form. Its backend counterpart `matter.domain.routing` (Q01–Q22) is also
untested (F8). The most consequential decision in the product is unverified on
both sides.

### 3. Unit-test candidates

Pure functions and services drivable through existing port doubles. No new
infrastructure. Ordered by value.

#### 3.1 Backend

**`src/modules/verification/tests/test_policies.py`** (~18) — F9.

| Test | Expected |
|---|---|
| `test_auto_promote_refused_below_confidence_threshold` | `may_auto_promote` False under the band |
| `test_auto_promote_refused_without_evidence_span` | False when the span is absent |
| `test_auto_promote_refused_for_negative_conclusion` | `guard_negative_conclusion` raises — absence of a finding is never auto-promoted |
| `test_human_confirmation_required_for_conflicting_candidates` | raises on two candidates for one field |
| `test_resolve_status_maps_each_candidate_state` | parametrised over every `VerificationState`; no `KeyError`, no default fallthrough |
| `test_guard_evidence_rejects_span_outside_document` | raises when the char range exceeds the page |

**`src/modules/verification/tests/test_fact_query_service.py`** (~8) —
`list_facts` scoping, empty-matter case, ordering stability.

**`src/modules/matter/tests/test_routing.py`** (~30) — F8, the highest-value new
file in the plan. Parametrised over the Q01–Q22 answer space:

- each `TriState` on Q01 routes to the documented regime or to "cannot route";
- `UNKNOWN` never silently picks a default;
- every `RtaSubtypeId` reachable by routing exists in the taxonomy;
- `DispositionScope` × `ParcelKind` yields the Section 47 part-parcel module
  when and only when the spec says so (Appendix A, refusal 4);
- `PartyContext` combinations activate the right `lk.rta.module.*` ids;
- routing is deterministic for identical input — run twice, compare.

**`src/modules/matter/tests/test_matter_service.py`** (~24) — `create_matter`,
`save_answer` (supersession, not overwrite), `confirm_subtype` with a version
mismatch ⇒ `PreconditionFailedError`, `route`, `compile_checklist`, `transition`
refusing an illegal target, cursor stability, cross-tenant ⇒ `NotFoundError`.

**`src/modules/task/tests/test_policies.py`** (~26) — the six status axes
(applicability / collection / digital_review / currency / consistency /
resolution) are a truth table; parametrise `compute_resolution` and
`derive_lifecycle` across it. Plus `guard_resolution_write` refusing a
lawyer-owned decision from a non-lawyer, `guard_administrative_collection`,
`apply_physical_original` per `PhysicalOriginalStatus`, `is_blocking_unsatisfied`.

**`src/modules/task/tests/test_checklist_service.py`** (~20) —
`compile_snapshot` determinism, non-destructive recompile (existing decisions
survive), `decide_satisfaction` version conflicts, `link_document` /
`supersede_document_links`, `blocking_requirement_ids`.

**`src/modules/notarial_register/tests/test_policies.py`** (~12) —
`assert_state_transition`, `register_year_for` at year boundaries in
`Asia/Colombo`, `validate_export_source`, `require_practising_notary_actor`.

**`tests/unit/test_outbox_policies.py`** (~14) — see §6.1.

**`tests/unit/test_pagination_cursor.py`** (~12) — F4, security-critical.

| Test | Expected |
|---|---|
| `test_cursor_round_trips` | `decode_cursor(encode_cursor(x)) == x` |
| `test_forged_cursor_rejected` | re-encoded with a different key ⇒ raises, never silently decodes |
| `test_truncated_cursor_rejected` | raises |
| `test_cursor_from_other_key_rejected` | rotating the signing key invalidates old cursors |
| `test_clamp_limit_bounds` | parametrised: 0, 1, default, max, max+1, −1 |
| `test_paginate_by_id_is_stable_across_inserts` | a row inserted after page 1 does not shift page 2 |

**`tests/unit/test_conditional.py`** (~8) — `etag_for_version`, and
`require_if_match` on missing / malformed / unquoted / weak-etag / correct input.

**`src/modules/billing/tests/test_payhere_adapter.py`** (~10) — F12. Valid
signature accepted; wrong secret rejected; replayed `order_id` detected as
duplicate; body over 65536 bytes rejected before parse; malformed form encoding
rejected; a non-JSON body does not 500.

**`tests/unit/test_agent_read_tools.py`** / **`test_agent_write_tools.py`**
(~17 combined) — the 9 read and 8 write tool bodies. The authorization decision
is covered; the bodies are not. Assert `read_tools.untrusted()` wraps every
model-visible string.

#### 3.2 Frontend, no new infrastructure needed

**`src/lib/store/demo-store.test.ts`** (~35) — F10, the highest-value frontend
file. Drive the store via `useDemoStore.getState()`, reset with `resetDemo()`.

- one test per action asserting the resulting state **and** the audit event it
  emits. The 13 strings `demo-path.spec.ts` asserts after a 180-second browser
  walk belong here, asserted in milliseconds;
- `correctFact` on a verified fact marks dependent drafts `stale` (Appendix A,
  refusal 2);
- `exportDraft` before `approveDraft` is refused (refusal 3);
- `migratePersistedMatter` / `migratePersistedDocument` against a v1 payload;
- `resetDemo` restores the seeded fixture exactly.

**`src/lib/templates/build-document.test.ts`** (~12) — `buildTemplateDocument`
emits `lockedBlock` nodes for prescribed text and `factChip` nodes only for
`verified`/`corrected` facts; an `unreviewed` fact produces a placeholder, never
a chip; block order follows the template.

**`src/components/shell/matter-stage.test.ts`** (~3) — parametrise
`stageForState` over every `RtaMatterState`; no fallthrough; result is in
`STAGE_ORDER`.

**`src/lib/i18n/labels.test.ts`** (~8) — completeness: every member of
`VerificationState`, `SourceFileState`, `CheckStatus`, `StepState`,
`PhysicalOriginalStatus`, `AuthorityType`, `CourtLevel`, `AuthorityWeight` has
both an `en` and an `si` label. Today a new union member fails silently at
runtime.

**`src/lib/rta/workflow-catalogue.test.ts`** (~8) — grouping,
`commonRtaWorkflows(limit)` boundaries (0, 1, default, over-length),
`availableRtaWorkflowCount` against the taxonomy.

**`src/lib/i18n/fact-label-keys.test.ts`** (~6) — `factLabelKey` normalisation
and its fallback; `FACT_SECTIONS` covers every `FACT_LABEL_KEYS` member.

**`src/lib/api/*.test.ts`** — seven files (`matters`, `documents`, `drafts`,
`checks`, `approvals`, `auth`, `rta`), ~6 each. URL shape, query-string
construction from each `List*Params`, the `ifMatch(version)` header on every
mutation, `stepUpToken` propagation in `approvals.ts`, `FormData` construction
in `uploadSourceFile`, `needsOnboarding(user)`. Model these on the existing
`agent.test.ts`, which already does it well.

**Extract then test** from `new-matter-screen.tsx` into
`src/lib/rta/intake-helpers.ts`: `togglePartyContext`, `inclusionText`,
`legacyTypeForSubtype`, `demandsOriginal`. Four pure functions currently trapped
inside a 1595-line component. ~12 tests once extracted.

### 4. Integration and API-test candidates

Integration means real router, real service graph, real repositories, over the
in-memory SQLite harness `tests/integration/test_matter_agent_api.py` already
proves works. Copy its `session_maker` fixture and `dependency_overrides`
pattern. Party's JSONB columns do not build on SQLite, which is why that harness
picks 11 tables by hand; new harnesses must do the same or use §5's Postgres.

#### 4.1 Per-router API suites

One file per router under `backend/tests/integration/api/`. Each gets the same
five baseline tests before any domain-specific ones — the F13 fix:

| Baseline test | Expected |
|---|---|
| `test_requires_authentication` | no `Authorization` header ⇒ **401**, envelope with `code`, `message`, `correlation_id` |
| `test_rejects_foreign_tenant` | valid ctx for user B against A's resource ⇒ **404**, not 403, body leaks no id |
| `test_missing_if_match_returns_428` | mutating routes only |
| `test_stale_if_match_returns_412` | write, then replay with the old version |
| `test_error_envelope_shape` | any 4xx matches `ErrorEnvelope`, `X-Correlation-Id` echoed |

Priority order: `matter`, `task`, `verification`, `check`, `draft`, `approval`,
`document.ingestion_router`, `obligations`, `notarial_register`, `notification`,
`billing`, `billing.admin_router`, `auth`, `content_governance`.

`notarial_register` deserves a finding rather than a test that rubber-stamps
current behaviour: nine mutating routes with no `If-Match`. Write
`test_attestation_mutations_are_version_guarded` as a **failing** test and fix
the router, rather than asserting the gap into permanence.

#### 4.2 Cross-module flow tests

**`test_intake_to_checklist.py`** (~10) — create matter → save Q01–Q22 → `route`
→ `compile_checklist` → `GET /checklist`. Assert the compiled checklist matches
`content_governance.compiler` for that subtype, that recompiling after one answer
changes is non-destructive, and that `UNKNOWN` blocks routing rather than
defaulting.

**`test_document_to_fact.py`** (~12) — upload → `process` → boundary decision →
classification decision → candidate edit → candidate approve → `GET /facts`.
Assert the approved candidate becomes a fact with `corrected` or `verified`
state and an evidence span, and that an **unapproved** candidate never appears
in `/facts` (Appendix A, refusal 5).

**`test_fact_to_approved_export.py`** (~14) — Appendix A's happy path as one API
walk: facts verified → `runChecks` → resolve blocking issues → `generateForm` →
`preflight` → `approve` → `export`. Then the five refusals as separate tests,
each asserting a refusal, not a success.

**`test_billing_quota.py`** (~8) — Rule 7. `reserve_usage` → `consume_usage`
happy path; `reserve` → `release` on failure returns the quota; over-quota
refused; `require_feature_or_raise` under a restricted subscription; concurrent
reservations for one `operation_id` are idempotent.

#### 4.3 Contract-artifact gates

`test_openapi_contract.py` already fails on a stale `contracts/openapi.v1.json`.
Extend the pattern:

- **`test_rta_rule_pack_contract.py`** — `contracts/rta-rule-pack.v1.json` and
  `frontend/src/lib/rta/taxonomy.generated.json` must both match
  `full_rule_pack_contract()` / `taxonomy_contract()`. The frontend copy
  drifting from the backend source is a real failure mode; nothing catches it.
- **`backend/tests/conformance/`** — F19, Rule 6. Create the directory the
  registry already claims exists, parametrised over `contracts/services.yaml`:
  `test_registry_matches_readme`, `test_every_table_has_organisation_id`,
  `test_idempotency_key_required`, `test_every_declared_job_has_a_handler`
  (currently fails — `billing.reconcile-subscriptions` is declared with no
  handler), and `test_every_consumed_event_has_one_publisher` (move the inline
  `python3` heredoc out of `ci.yml` so it runs locally too).

### 5. Database and repository tests

#### 5.1 The harness decision

Decision A6.1, resolved: **Docker Postgres in CI, Neon on push to `main`.**
Docker gives a sub-minute, offline, free loop; Neon catches pooler behaviour,
`DATABASE_URL` vs `DATABASE_URL_DIRECT`, and autosuspend cold start, which
`DEPLOYMENT_PLAN.md` §9.7 flags as the likely first bottleneck.

Add to `ci.yml`'s `backend` job:

```yaml
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: draftly_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
```

The placeholder URL already in `tests/conftest.py`
(`postgresql+asyncpg://test:test@localhost:5432/draftly_test`) matches exactly,
so the `os.environ.setdefault` seeding needs no change.

#### 5.2 Isolation strategy

No transactional-rollback harness exists. Add `backend/tests/db/conftest.py`:

```python
@pytest.fixture(scope="session")
async def db_engine(): ...          # one engine, alembic upgrade head, once

@pytest.fixture
async def db_session(db_engine):
    """Outer transaction per test, rolled back — never committed."""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
```

Rollback per test rather than truncate per test: faster, and it keeps tests
order-independent. The one place it does not work is the outbox worker, which
commits across two sessions by design; those need a real commit and an explicit
truncate, so keep them in a separate `db_session_committing` fixture.

#### 5.3 Repository tests — F14

One file per repository under `backend/tests/db/`, baseline ~6 each:

| Test | Expected |
|---|---|
| `test_insert_then_get_round_trips` | every column survives, including JSON/JSONB and tz-aware datetimes |
| `test_get_is_scoped_by_user_id` | another tenant's id returns `None`, not the row |
| `test_update_bumps_version` | increments by exactly 1 |
| `test_update_with_stale_version_raises` | `PreconditionFailedError`, row unchanged |
| `test_list_cursor_is_stable` | insert between pages; page 2 does not repeat or skip |
| `test_list_respects_limit_clamp` | over-max clamped, not rejected |

Priority: `audit` (C2), `matter`, `task`, `verification`, `check`, `draft`,
`approval`, `obligations`, `notification`, `billing`, `matter_agent`, `auth`.

**`tests/db/test_audit_chain.py`** (~8) — Rule 2:

- write 10 events for one user; walk `prev_hash` back to genesis;
- two users' chains are independent;
- concurrent writes for one user produce a linear chain, not a fork (needs the
  committing fixture and two sessions);
- tampering with one row's payload makes the recomputed hash mismatch.

**`tests/db/test_migrations.py`** (~5):

- `alembic upgrade head` from empty succeeds; `downgrade base` succeeds;
- `alembic heads` returns exactly one revision (guards a bad merge);
- ORM metadata matches the migrated schema — autogenerate produces an empty diff;
- migrations run against `DATABASE_URL_DIRECT`, not the pooled URL —
  `DEPLOYMENT_PLAN.md` §7.3 depends on this and nothing asserts it.

The chain is not all additive, as an earlier version of this section said:
`notification_0002_outbox_inbox.py` and `party_0002_tenant_key.py` backfill
with `op.execute`, tighten columns to `NOT NULL` and replace a unique key.
`test_no_new_upgrade_step_drops_or_alters_a_column` scans every other
`migrations/versions/*.py` and names those two as exemptions that predate the
check; whether each was safe under `DEPLOYMENT_PLAN.md` §7.2's one release of
backward compatibility is for the team to confirm.

Built in `tests/db/test_migrations.py`, which also found that
`migrations/env.py` did not import the matter-agent models or
`api_idempotency_keys`, so autogenerate would have proposed dropping eight
tables. That is fixed and guarded. The autogenerate diff is not empty: 14
entries of model-versus-migration drift (agent foreign keys, one JSON/JSONB
type, five indexes) are listed in `KNOWN_DRIFT`, so new drift fails at once
and a strict xfail tracks the rest until each is fixed.

#### 5.4 Privacy at rest — Rule 3

Upgrade `tests/privacy/test_party_privacy.py` from the recording harness to the
real DB fixture, and add the dump test: write a party with the reserved
synthetic NIC, then `SELECT *` across every table and assert the raw NIC string
appears nowhere — only ciphertext and the blind index. Same for names,
addresses, and the rest of `platform/privacy.py`'s private-content set. Repeat
against captured log output, not just the database.

### 6. Background jobs and asynchronous workflows

F2 is the largest single gap. `src/workers/runner.py` is 107 lines with no test.

#### 6.1 `tests/unit/test_outbox_policies.py` (~14, no DB)

| Test | Expected |
|---|---|
| `test_backoff_grows_exponentially` | `backoff_seconds(n, jitter=0)` = `min(2**n * 5, 1800)` for n in 0..10 |
| `test_backoff_caps_at_thirty_minutes` | n ≥ 9 ⇒ 1800 s |
| `test_backoff_jitter_stays_within_twenty_percent` | parametrised at ±1.0 bounds |
| `test_dead_letters_at_max_attempts` | `mark_retry` at `attempts == 8` ⇒ `dead_letter` |
| `test_mark_failed_is_terminal` | never re-claimed |

#### 6.2 `tests/db/test_outbox_repository.py` (~16, real Postgres)

`FOR UPDATE SKIP LOCKED` only engages on Postgres — testing it on SQLite tests
nothing.

- two concurrent `claim_batch` calls return disjoint sets;
- a claimed message is invisible to a third claimer until its lease expires;
- `reap_leases(lease_seconds=120)` returns an expired claim to `pending`;
- the unique constraint rejects a duplicate publish;
- `pending → claimed → {done, failed, dead_letter}` and no illegal transition;
- `available_at` in the future is not claimed.

#### 6.3 `tests/db/test_worker_runner.py` (~12, real Postgres)

| Test | Expected |
|---|---|
| `test_handler_exception_rolls_back_then_marks_retry` | the handler's partial writes are gone **and** the message is `pending` with `failure_code="handler_error"` — the two-session path, and the one most likely to be subtly wrong |
| `test_handler_done_commits_work_and_marks_done` | both in one transaction |
| `test_handler_retry_preserves_attempt_count` | increments by 1 |
| `test_run_once_reaps_before_claiming` | an expired lease is picked up in the same pass |
| `test_run_once_is_idempotent_on_empty_queue` | no error, no spurious commit |
| `test_unknown_message_name_does_not_crash_the_loop` | dispatcher miss handled, not raised |

#### 6.4 Handler tests

**`src/modules/notification/tests/test_jobs.py`** (~14) — `run_delivery_job`
mapping every outcome (`delivered`, `suppressed`, `permanent-failure`,
`unknown-delivery`, `retry`, `dead-letter`) to the right `MessageResult`;
`consume_registered_event` for `processed` / `duplicate` / `suppressed` /
`dead-letter`; the 27 `EVENT_TEMPLATE_ROUTES` entries each resolve to a template
that exists (parametrised — catches a renamed template).

**`src/modules/matter_agent/tests/test_jobs.py`** (~8) — `run_turn_job`,
including the deliberate choice that **anything other than `retry` maps to
`DONE`**, because replaying a failed turn would answer the user twice. Write
that test with a docstring saying so, or someone will "fix" it.

`test_matter_agent_neon_e2e.py` already covers the end-to-end turn. Keep it,
mark it, run it in the Neon job.

#### 6.5 Gaps that tests should expose, not paper over

Three pieces of dead or half-wired machinery. Each gets an `xfail` with a
reason, not a silent omission:

- `matter_agent.jobs.purge_stream_events` has no caller and no scheduler; stream
  events accumulate forever. → `test_purge_stream_events_has_a_caller` `xfail`.
- `ObligationsService.schedule_reminders` writes into
  `SqlNotificationIntentPort`, which is an in-process list, not a real write. No
  `obligation.reminder-due` event is ever emitted, so the notification consumer
  for it can never fire. → `test_scheduled_reminder_emits_an_outbox_event`
  `xfail`.
- `contracts/services.yaml` declares `billing.reconcile-subscriptions` with no
  registered handler. → covered by the conformance test in §4.3.

**Decision A6.4 belongs here.** `backend/docs/jobs-and-workers.md` §1 requires a
`--sched` runner mode electing a leader through a Postgres advisory lock, and
`DEPLOYMENT_PLAN.md` §1.3 depends on it. There is no `pg_advisory` call anywhere
in `src/` or `migrations/` and no scheduler entrypoint, so nine of the eleven
scheduled jobs have no runtime — only `outbox.drain` and `lease.reap` are
covered, incidentally, by the worker loop. Deduplication for ordinary jobs comes
from `SKIP LOCKED` plus the unique constraint, which is unaffected. Build the
lock; a test cannot bridge the gap.

A related defect belongs in the same commit: `runner.py` hardcodes
`DEFAULT_LEASE_SECONDS = 120` for every message type, while
`backend/docs/jobs-and-workers.md` §5 assigns per-type leases up to 3600 s
(`document.process` is 900 s). A long job would be reaped and re-claimed while
still running. It is latent only because document processing is currently
synchronous. Cover it with
`test_long_lease_job_is_not_reaped_while_running`.

Separately, document processing runs **synchronously** inside the HTTP request
(`SynchronousProcessingJob`), not through the worker. That is a deliberate
current-phase choice, but it makes `DEPLOYMENT_PLAN.md`'s `proxy_read_timeout
120s` load-bearing. Add
`test_processing_completes_within_the_proxy_timeout_budget` against the stub
extractor.

### 7. Playwright end-to-end journeys

#### 7.1 Fix the harness first — F3, F18, F22

No new spec is worth writing until the existing eight can run.

**Auth.** Add `frontend/tests/e2e/global-setup.ts`:

```ts
// Preferred: sign in once with Clerk testing tokens, persist storageState.
// Fallback where Clerk test keys are unavailable: set AUTH_BYPASS=true on the
// webServer only — never in a shipped environment file.
export default async function globalSetup(config: FullConfig) { … }
```

and in `playwright.config.ts`:

```ts
globalSetup: require.resolve("./tests/e2e/global-setup"),
use: {
  baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:4310",
  storageState: "tests/e2e/.auth/user.json",
  trace: "retain-on-failure",
},
retries: process.env.CI ? 2 : 0,
reporter: process.env.CI
  ? [["github"], ["html", { open: "never" }], ["junit", { outputFile: "results.xml" }]]
  : [["line"]],
webServer: {
  command: process.env.CI ? "pnpm build && pnpm start -p 4310" : "pnpm dev -p 4310",
  env: { MULTILINGUAL_LANGUAGE_SUPPORT: "true" },
  url: "http://127.0.0.1:4310",
  reuseExistingServer: !process.env.CI,
  timeout: 180_000,
},
```

Four things change: auth becomes deterministic, `baseURL` becomes overridable so
the suite can point at a preview deploy, CI gets retries and artifacts, and CI
tests the production build — which matters because `design-audit.spec.ts`
asserts exact font and CSS-token values.

Keep `auth-flow.spec.ts` signed **out**; it must opt out of the shared
`storageState` via `test.use({ storageState: {} })`.

**Route inventory.** `tests/e2e/routes.ts` lists 18 routes and omits eleven that
exist: `/profile`, `/onboarding`, `/kitchen-sink`,
`/matters/[id]/processing`, `/exports`, `/missing-documents`,
`/matters/[id]/assistant`, `/documents/[documentId]/review`,
`/drafts/[draftId]/approval`, and the auth pages. Add the real ones; decision
A6.3 covers `/kitchen-sink`.

**`screen-review.spec.ts`** writes to a frozen path
`../docs/review/<slug>/2026-07-22` and overwrites the same baseline on every
run. Parameterise the date or drop it from the default run.

#### 7.2 Journeys to add

Existing coverage — `demo-path` (full happy path), `spec-fidelity` (governed
states), `design-audit`, `accessibility-audit`, `responsive-i18n`, `i18n-smoke`,
`auth-flow` — is unusually good for a repo this size. The gaps are refusals and
recovery, not happy paths.

**P0 — `refusal-paths.spec.ts`** (~6). Each asserts the UI blocks and says why,
in a user-visible string. These are Appendix A's five refusals at the UI layer:

| Journey | Expected |
|---|---|
| Export an unapproved draft | Export disabled, reason shown |
| Generate a draft with an open statutory blocker | "Draft generation blocked" + the blocking issue named |
| Complete a blocked mandatory step with no reason | Complete stays disabled until an override reason is entered |
| Insert a fact chip from an `unreviewed` fact | Not offered |
| Approve as a non-responsible lawyer | Refused with the role reason |
| Accept a 95%-confidence machine value as verified | Still shows as unreviewed |

**P0 — `matter-isolation.spec.ts`** (~3) — Rule 1 at the UI layer. Sign in as
user B, navigate directly to user A's matter URL. Expect a not-found surface,
**not** a permission error, and assert the body contains no fragment of A's
matter reference.

**P1 — `error-recovery.spec.ts`** (~6). `page.route()` fault injection:

- 500 on `GET /matters` ⇒ `error.tsx` renders with a working retry;
- 401 mid-session ⇒ redirect to sign-in, no infinite loop;
- 412 on save ⇒ a conflict message naming the stale-version cause, not a raw code;
- 413 on upload ⇒ a size message;
- offline mid-upload ⇒ retry available, no duplicate upload;
- 20-second response ⇒ loading state, no double submit.

**P1 — `upload-and-review.spec.ts`** (~5) — upload → processing poll → boundary
decision → classification decision → candidate edit → approve. Currently only
the happy path inside `demo-path.spec.ts` touches this, and only via the demo
store.

**P2 — `session-and-onboarding.spec.ts`** (~4) — first sign-in ⇒ `/onboarding`;
completed profile ⇒ `/`; `needsOnboarding` false path; sign-out clears state.

#### 7.3 What E2E should not carry

`demo-path.spec.ts` asserts 13 exact audit-event strings after a 180-second
walk. Once `demo-store.test.ts` exists (§3.2), move those assertions down to the
unit test and leave the spec asserting that the activity feed renders events at
all. A 180-second browser run is the wrong place to test a string map.

### 8. Authentication and authorization

#### 8.1 The real token path — F1

`backend/tests/security/test_auth_http.py` (~16). These must **not** override
`get_request_context` — that is the entire point. Override only the identity
adapter's key source so a locally-minted JWT validates.

| Test | Expected |
|---|---|
| `test_missing_authorization_header_returns_401` | on a representative route from every router |
| `test_malformed_bearer_returns_401` | `Bearer` alone, `Bearer` with an empty token, `Basic x`, a bare token |
| `test_expired_token_returns_401` | `exp` past beyond `clerk_leeway_seconds` |
| `test_token_within_leeway_is_accepted` | `exp` 20 s past, leeway 30 s ⇒ 200 |
| `test_tampered_signature_returns_401` | last 5 chars mutated |
| `test_wrong_azp_returns_401` | `azp` not in `clerk_authorized_parties` — the `CLERK_AUTHORIZED_PARTY` misconfiguration `DEPLOYMENT_PLAN.md` §4.2 warns fails closed |
| `test_alg_none_token_rejected` | classic JWT bypass |
| `test_unverified_email_rejected` | `_is_affirmatively_verified` |
| `test_unprovisioned_identity_raises_account_pending` | `AccountPendingError`, distinct from 401 |
| `test_correlation_id_is_bound_and_echoed` | `X-Correlation-Id` in ⇒ same value out, and present in the structlog record |
| `test_correlation_context_is_cleared_after_request` | two sequential requests do not share contextvars |

#### 8.2 Capability, role, step-up

`tests/security/test_capability_http.py` (~12) — for each capability-gated
route, the wrong `Role` gets a **403** with a `CapabilityDeniedError` envelope
and the right one gets through. Include `platform.administer` on
`billing.admin_router`; an admin route reachable by a regular user is the
canonical Critical security finding.

`test_step_up_required.py` (~6) — `PATCH /me/role` without `X-Step-Up-Token` ⇒
`StepUpRequiredError`; a stale token ⇒ refused; a valid one ⇒ 200. Same for the
approval step-up path.

#### 8.3 Tenancy sweep — Rule 1, C1

`tests/security/test_tenancy_sweep.py`, parametrised over every route in
`contracts/services.yaml` marked `matter_scoped: true`. Two users, two matters.
For each route: user B against A's resource ⇒ **404**, and the body contains no
identifier belonging to A. This one parametrised file closes system-wide what
`test_party_security.py` closes for one module, and it is what Rule 1 actually
asks for.

#### 8.4 Unauthenticated surfaces

Four routes take no `get_request_context`; each needs its own guard test:

- `GET /health/live`, `GET /health/ready` — 200 without auth; `/health/ready`
  reports `db: ok` and **503 when the DB is unreachable**.
  `DEPLOYMENT_PLAN.md` §10.1 balances the load balancer on exactly this
  distinction, and nothing tests it today.
- `POST /me/provision` — accepts a bearer token with no provisioned account;
  rejects a missing token.
- `POST /billing/webhooks/payhere` — §3.1, F12.
- `POST /notifications/provider-webhooks/resend` — signature verification, and
  `include_in_schema=False` so it stays out of the public contract.

#### 8.5 Frontend auth

`frontend/src/middleware.test.ts` (~8). The gate's four branches compose in a
specific order: bypass → unconfigured-fail-closed → public-route →
`auth.protect()`. The three helpers are individually tested; the composition and
the `config.matcher` regex are not. Assert `/clerk-not-configured` is reachable
while unconfigured, a static asset path is excluded by the matcher, and bypass
short-circuits before the fail-closed redirect.

### 9. Failure, edge-case and recovery tests

#### 9.1 Input and boundary

Values to parametrise rather than hand-write:

- **Pagination** — `limit` at 0, 1, default, max, max+1, −1, non-numeric;
  `cursor` empty, forged, truncated, from another key, from another collection.
- **Uploads** — 0 bytes, 1 byte, `MAX_SOURCE_FILE_BYTES` exactly, max+1
  (⇒ 413 at nginx before FastAPI sees it — `DEPLOYMENT_PLAN.md` §5.2 pins
  `client_max_body_size 50m` to this constant, so assert the constant is
  52428800 and cite it in the nginx config), a password-protected PDF, a `.exe`
  renamed `.pdf` (`sniff_media_type` must beat the extension), a 0-page PDF, a
  500-page PDF.
- **Text fields** — empty, whitespace-only, max length, max+1, Sinhala script, a
  mixed EN/SI string, an RTL control character, `'; DROP TABLE matters; --`,
  `<script>alert(1)</script>`. The last two should be stored and returned
  verbatim — SQLAlchemy parameterises, React escapes. Assert that, rather than
  asserting a 400; a rejection here would be the wrong fix.
- **Dates** — year boundary in `Asia/Colombo` (`register_year_for`), a leap day,
  a deadline landing on a Poya day or weekend (`add_working_days`,
  `presentation_deadline`).
- **Numbers** — extent comparison at the rounding boundary (`compare_areas`),
  zero consideration, a negative amount (`is_valid_money`).

#### 9.2 Concurrency

- Two clients `PATCH` the same matter with the same `If-Match` ⇒ one 200, one
  412. Never two 200s.
- Two workers claim the same outbox batch ⇒ disjoint sets (§6.2).
- Two approvals of the same form ⇒ the second is refused or a no-op, never a
  second approval record.
- Concurrent audit writes for one user ⇒ linear chain (§5.3).
- Duplicate `Idempotency-Key` on an agent message ⇒ same job id, one job.
  Partially covered; extend to billing checkout.

#### 9.3 External-dependency failure

| Dependency | Failure | Expected |
|---|---|---|
| Gemini | timeout | run marked failed with a `failure_explanation_key`; source file **not** marked processed |
| Gemini | 429 | retryable classification, outbox retry, not dead-letter |
| Gemini | malformed JSON | no crash, empty candidate set, honest failure state |
| Cloud Vision | quota exceeded | same |
| GCS | 403 on write | upload refused, **no partial state** — no source-file row without bytes |
| GCS | bucket policy drift | refused at boot (covered) |
| Clerk | JWKS unreachable | 401 or 503, never a permitted request |
| Resend | 5xx | retryable; 4xx ⇒ permanent per `classify_failure` |
| PayHere | replayed webhook | duplicate detected, subscription not double-applied |
| Postgres | pool exhausted | `/health/ready` fails ⇒ the LB ejects the VM (`DEPLOYMENT_PLAN.md` §9.7 names this as the likely first bottleneck) |
| Supermemory | disabled / unreachable | `NullMemoryPort` path, agent turn still completes |

#### 9.4 Recovery

- Worker crashes mid-message ⇒ lease expires ⇒ another worker reaps and
  reprocesses ⇒ **exactly-once observable effect**. Assert the effect count, not
  the call count.
- Draft goes `stale` after a fact correction ⇒ regenerate ⇒ the new draft carries
  the corrected value and the old approval does not transfer
  (`approval_matches_snapshot`). Appendix A, refusal 2.
- A superseded document's links are re-pointed, not orphaned.
- Partially-completed checklist compilation is re-runnable without losing lawyer
  decisions.

### 10. Mocking, fixtures, factories and seed data

#### 10.1 The rule

**Mock external services, not internal logic.** Draftly's boundary is clean —
everything crossing it is a declared port. Mock at the port, never inside a
service.

| Layer | Strategy |
|---|---|
| Gemini, Cloud Vision, Clerk, Resend, PayHere, Supermemory, GCS | Always faked. `tests/e2e/*_live.py` are the only real calls, behind the `live` marker. |
| Postgres | Real, via §5.2, for repository / outbox / audit-chain / privacy tests. Faked elsewhere. |
| Services and repositories | **Never mocked.** Real class over a fake port, or a real session. |
| Frontend API client | `page.route()` in Playwright; `vi.stubGlobal("fetch", …)` in Vitest. Never mock `lib/api/*` itself — that tests the mock. |

#### 10.2 Consolidate the fakes — F16

`FakeAudit` exists four times, `fact_tier` three times, and `USER_ID` /
`MATTER_ID` / `NOW` are redefined per module. Consolidate into
`backend/tests/factories/`, importable from both `tests/` and
`src/modules/*/tests/`:

```text
backend/tests/factories/
  __init__.py
  constants.py      # USER_A, USER_B, MATTER_A, NOW = datetime(2026,1,1,9,0,tzinfo=UTC)
  context.py        # ctx(role=Role.REVIEWER, actor=USER_A) -> RequestContext
  audit.py          # FakeAudit — one implementation
  events.py         # FakeEvents / InMemoryEventPort
  matter.py         # matter(**overrides), intake_answer(**overrides)
  party.py          # party(**overrides) — absorbs party_synthetic.py
  document.py       # source_file(), detected_document(), candidate_field()
  fact.py           # fact_tier(**overrides) — one implementation
  form.py           # form_snapshot(), approval_record()
  checklist.py      # compiled_checklist(), checklist_item()
```

Migrate the four module `fakes.py` files to import from here, keeping
module-specific fakes (`FakeFormReader`, `FakeIssueGates`) local. Do this
**before** writing the §3–§6 tests, or the duplication triples.

#### 10.3 Factory conventions

Hand-rolled builders, not `factory_boy` — the existing ones are good and a
library adds a dependency for little gain. What to enforce:

- **Complete by default.** A factory returns every field a real object has, so a
  test never passes on an incomplete mock and crashes in production on
  `user.email`.
- **Deterministic.** Fixed ids and timestamps, per `CLAUDE.md`. Sequence
  counters where uniqueness is needed, never `uuid4()` or `Faker`.
- **Keyword overrides only** — `party(display_name="…")`, never positional.
- **Synthetic and labelled** — see Appendix B.

#### 10.4 Seed data — F17

Built as `backend/scripts/seed_synthetic_matter.py`, the name
`backend-implementation-plan-v0.md` §4 already reserves:

```bash
uv run python scripts/seed_synthetic_matter.py   # smoke: 1 lawyer, 1 matter, 2 parties, 1 doc
```

What it does: runs only where a fake identity is already allowed (`local`,
`test`, `ci`); builds from `tests/factories/` so seed and test data cannot
drift; writes through the real services, so a seeded matter carries the audit
trail a walked-through one does. `tests/db/test_seed_synthetic_matter.py`
covers all of it against real Postgres.

Three changes from the original plan, each forced by a rule that outranks it:

- **Idempotent by natural key, not fixed ids.** The real services mint their
  own ids, so fixed ids would mean bypassing them. A matter is unique per owner
  and reference instead; a second run finds it and changes nothing.
- **No `--reset`.** It would have to delete audit rows, and the audit log is
  append-only. Reset by dropping the local database.
- **No `full` profile yet.** It needs the Appendix B roster, which is a human
  gate. The frontend-id parity in §10.5 waits on it too, and cannot use fixed
  ids for the reason above.

This unblocks three things at once: E2E against a real backend, the Playwright
`globalSetup`, and manual supervisor demos.

#### 10.5 Frontend fixtures

`frontend/src/lib/mocks/fixtures.ts` is 1514 lines of deterministic seed data
and is already the right shape. Two additions: a parity test asserting its ids
match the seeded backend's, so an E2E spec can run against either the mock store or
a seeded backend; and typed builders (`makeMatter(overrides)`) rather than
exported literals, for the completeness reason in §10.3.

### 11. CI configuration and coverage thresholds

#### 11.1 Fix what is there — F6, F7, F11

Three edits to `.github/workflows/ci.yml`, in order.

**(a) Run the frontend tests.** In the `verify` job, after `lint`:

```yaml
      - run: pnpm --dir frontend test
```

Better: replace the four individual steps with `pnpm check`, which already
chains typecheck → lint → test → build → markdown. That makes the root script
the single source of truth and stops this class of drift recurring.

**(b) Run the whole backend suite.** Replace:

```yaml
          uv run pytest tests/unit tests/contract tests/conformance
```

with:

```yaml
          uv run pytest -m "not live"
```

`testpaths = ["src/modules", "tests"]` then picks up all 66 files — what
`CLAUDE.md` already mandates. Convert the `skipif(RUN_LIVE_TESTS)` guards in
`tests/e2e/` to a declared `live` marker so the exclusion is explicit rather
than environment-dependent.

**(c) Add Postgres.** The `services:` block from §5.1, plus `ENVIRONMENT: ci` in
the job env. The `integration` marker then stops being a silent skip.

Two smaller items: pin the third-party actions to immutable SHAs (`ci.yml`'s own
comment asks for this and `pr-agent.yml` already does it), and move the inline
`python3` service-registry heredoc into `tests/conformance/` so it runs locally
too (§4.3).

#### 11.2 Add coverage — F5

Backend:

```bash
uv add --dev pytest-cov
```

```toml
[tool.coverage.run]
source = ["src"]
branch = true
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "raise NotImplementedError"]
```

Frontend:

```bash
pnpm --dir frontend add -D @vitest/coverage-v8
```

```ts
test: { coverage: { provider: "v8", reporter: ["text", "lcov"], all: true } }
```

#### 11.3 Thresholds — ratchet, do not cliff

An 80% gate on a repo with no current number fails the next PR and gets disabled
within a week.

**Step 1 (this sprint).** Measure and record the real number. No gate. Publish
it in §A1, replacing the import-reachability estimate.

**Step 2 (once §3 and §6 land).** Per-path minimums, not a global one — a global
number lets well-tested `content_governance` mask untested `matter`:

| Path | Line | Branch | Rationale |
|---|---|---|---|
| `src/modules/*/domain/policies.py` | 95% | 90% | Pure functions, the legal gates |
| `src/modules/*/application/*_service.py` | 85% | 75% | |
| `src/platform/` | 85% | 75% | Cursors, ETags, privacy, audit |
| `src/workers/` | 90% | 85% | F2 |
| `src/modules/*/api/router.py` | 75% | 60% | Thin; the value is in status codes (§4.1) |
| `src/modules/*/infrastructure/` | 70% | 50% | Mostly provider plumbing |
| **Backend overall** | **80%** | **70%** | |
| `frontend/src/lib/` | 85% | 75% | |
| `frontend/src/components/` | 50% | 40% | Only after F15; most value stays in E2E |
| **Frontend overall** | **70%** | **60%** | |

**Step 3 (ongoing).** `--cov-fail-under` at the current number minus one point,
raised whenever it is beaten. Coverage may never fall; it need not jump.

**What the threshold does not measure.** A 95%-covered `policies.py` whose tests
only assert `is not None` is worse than a 70%-covered one with real assertions.
Coverage is a floor, not a goal, and §12 exists because it can be gamed. The
PR-agent rubric (`.agents/skills/draftly-code-review/SKILL.md`) should treat a
coverage-only justification as insufficient.

#### 11.4 Job layout

| Job | Triggers | Contents | Target |
|---|---|---|---|
| `verify` | every PR | typecheck, lint, build, markdown, **vitest + coverage** | < 6 min |
| `backend` | every PR | ruff, mypy, `uv lock --check`, **full pytest + coverage**, Postgres service | < 8 min |
| `e2e` | every PR | Playwright against a production build, 2 retries, HTML + JUnit artifacts | < 12 min |
| `neon` | push to `main` | `-m integration` against a real Neon branch, plus `alembic upgrade head` / `downgrade base` | < 10 min |
| `live` | manual `workflow_dispatch` | `-m live` (Gemini, Vision, GCS). Costs money; never automatic. | — |

The `e2e` job needs `pnpm --dir frontend exec playwright install --with-deps
chromium` plus the secrets for whichever auth route §7.1 settles on.

#### 11.5 Flake policy

Quarantine and fix; never re-run until green.

- Playwright retries are for infrastructure noise, not known flakes. A spec that
  passes only on retry gets an issue and `test.fixme()` within one working day.
- Backend tests get **zero** retries. A flaky pytest is a real bug, almost
  always shared state — the only `autouse` fixture today is
  `_reset_settings_cache` and there is no DB isolation until §5.2.
- Run `pytest -p randomly` periodically. With 66 files and no per-directory
  conftest, an ordering assumption is easy to introduce.

### 12. Tests that should not be written

Everything here is something a coverage target will tempt someone into writing.
Listed so a reviewer can reject it with a citation.

#### 12.1 Implementation-detail tests

- **Assertions that a repository method was called.** A `toHaveBeenCalledWith`
  as the *only* assertion tests the mock. Assert the resulting state. The
  exception is audit and event emission, where the emission **is** the
  observable behaviour — `FakeAudit.actions()` is a legitimate target because an
  unaudited mutation is the bug.
- **Pydantic schema field tests.** `test_matter_read_has_an_id_field` verifies
  Pydantic. `test_openapi_contract.py` already locks the whole surface in one
  test.
- **SQLAlchemy column declarations.** Covered structurally by the
  autogenerate-diff test in §5.3.
- **Getter and pass-through tests.** `MatterService.get_matter` returning what
  the repository returned is not a behaviour. Test the scoping it applies.
- **`cn()` class-merge ordering**, `structuredClone` in `lib/data.ts`, TipTap's
  own node serialisation. Third-party behaviour.

#### 12.2 Snapshot tests where an explicit assertion exists

No `toMatchSnapshot()` on rendered components or on rule-pack JSON. A snapshot
diff tells you something changed, not whether it should have. The repo already
does this correctly — `test_openapi_contract.py` regenerates and compares with a
named failure message ("regenerate it with …") rather than an opaque snapshot.
Follow that for the rule-pack and taxonomy artifacts (§4.3).

`design-audit.spec.ts` is the good counter-example: it asserts the 14 named
design tokens by value, not a screenshot. Do not convert it to visual regression.

#### 12.3 Tests that duplicate a type

- `EditorFactChipNode.attrs.verification_state` is typed
  `"verified" | "corrected"`. A runtime test that it is never `"unreviewed"`
  duplicates the compiler. `fact-chip.test.ts` earns its place by testing the
  *insertion rule*, which is behaviour.
- Enum exhaustiveness in TypeScript is a `switch` with a `never` default, not a
  test. The **label-map completeness** test in §3.2 is different — those maps are
  data, not types, and can silently lose a member.
- Backend `Literal` types on request schemas are enforced by FastAPI validation,
  which the OpenAPI contract test locks.

#### 12.4 Tests that freeze a known gap

Where this audit found a gap, do not write a test that makes it permanent:

- `notarial_register`'s nine mutating routes have no `If-Match`. Write the test
  that **requires** it and fix the router (§4.1). Not
  `test_attestation_accepts_request_without_if_match`.
- The `[...slug]` catch-all swallows 404s (F21). Not
  `test_unknown_route_renders_skeleton`. Decide whether the catch-all should
  exist; if it should, scope its matcher and test that.
- CORS origins are hardcoded (F20). Do not assert `["localhost:3000",
  "localhost:4310"]`. `DEPLOYMENT_PLAN.md` §4.1 requires moving this to
  `CORS_ALLOWED_ORIGINS`; write the test against the setting once it exists.
- `SqlNotificationIntentPort` is an in-process list. Do not assert its contents
  — that tests a stub. `xfail` per §6.5.

#### 12.5 Over-mocked integration tests

An "integration" test where every dependency is a mock is a slow unit test. Rule
for `tests/integration/`: **at most one faked dependency per test, and it must
be an external provider.** Three fakes means it belongs in `tests/unit/` or a
module suite.

`tests/integration/test_party_integration.py` currently sits on this line and is
honest about it in its docstring. Once the §5.2 fixture exists, move it to real
Postgres or move it to `tests/unit/`.

#### 12.6 Live-provider tests in the default path

`test_gemini_live.py`, `test_vision_live.py`, `test_gcs_live.py` cost money and
depend on external availability. They stay behind the `live` marker and
`workflow_dispatch` (§11.4). Never add one to the PR path, and never add a new
live test without a cost note in the PR description.

#### 12.7 Load and performance tests

Out of scope. `DEPLOYMENT_PLAN.md` §9 owns the k6 ladder, the targets table, and
the failover and rolling-deploy procedures. The only overlap claimed here is the
two constants both documents depend on and that belong in a unit test:
`MAX_SOURCE_FILE_BYTES` (52428800, pinned to nginx's `client_max_body_size 50m`)
and the `/health/ready` vs `/health/live` distinction the load balancer routes
on (§8.4).

---

## Appendix A — The lawyer workflow

The scenario every layer is ultimately testing. Tested at the API layer in
§4.2, at the UI layer in §7.2, and in the frontend store in §3.2.

### A.1 Happy path

| Step | Action | Expected result |
|---|---|---|
| 1 | Lawyer creates a matter | Status `intake`; checklist compiled from the routed subtype |
| 2 | Uploads deed, mortgage, registry extract | Files stored; extraction produces candidate fields, all **unverified** |
| 3 | Reviews and verifies each extracted value | Facts move to `verified` or `corrected`, each with an evidence span; status `verification` |
| 4 | Runs checks | No encumbrance, no prior mortgage, no caveat ⇒ no blocking issues |
| 5 | Generates the draft | Form created, fields filled from verified facts only; status `draft` |
| 6 | Submits for approval | Status `submitted` |
| 7 | Approves | Status `approved`; audit event names the approving lawyer, the time, and the snapshot hash |
| 8 | Exports | Registration-ready artifact produced; status `exported` |

**Success criteria:** the matter passes through every status in order; every one
of the eight steps appends an audit event; draft fields match the verified facts
exactly; the export is downloadable and its manifest hash matches the approval
snapshot.

### A.2 The five refusals

Each of these is a case where the system must **stop**, and the test asserts the
refusal — not a workaround.

**Refusal 1 — Encumbrance.** The registry extract shows a lien. The
`no_encumbrance` checklist rule fails and raises a statutory blocker. Draft
generation is refused. **There is no override.** The lawyer resolves the
encumbrance outside the system or abandons the matter. *Why: the law does not
permit automated approval over an encumbered title.*

**Refusal 2 — A fact is corrected after approval.** A draft was approved with
the buyer name as extracted. The lawyer later corrects it. The system marks the
draft `stale`; export of a stale draft is refused; the old approval does not
transfer to the regenerated draft. *Why: an exported instrument must match the
facts as they stand.*

**Refusal 3 — Export before approval.** The draft is `submitted`, not
`approved`. Export is refused and the refusal is audited. *Why: no instrument
reaches a registry without a named lawyer's approval.*

**Refusal 4 — Part-parcel property, Section 47.** The registry extract shows a
part-parcel. Routing activates the Section 47 module and the checklist blocks.
Draft generation is refused until consent is recorded. *Why: part-parcel
dispositions carry a separate statutory consent requirement.*

**Refusal 5 — Unverified facts.** Extraction returns a value at 95% machine
confidence. The lawyer has not reviewed it. Draft generation is refused.
**Machine confidence is never sufficient**, at any threshold. *Why: this is the
product's central premise — a machine guess is a candidate, not a fact.*

---

## Appendix B — Synthetic data roster

**Every value below is invented.** No real person, NIC, address, deed, or
registry number appears in this repository. `CLAUDE.md` requires demo content to
be labelled as synthetic; the `(synthetic)` suffix is part of the data, not a
comment, so it shows up in any leaked log or screenshot.

Align new fixtures with the constants already in
`backend/tests/fixtures/party_synthetic.py` (`SYNTHETIC_NIC = "200012345678"`,
`SYNTHETIC_NIC_OLD_FORMAT = "851234567V"`, `SYNTHETIC_PASSPORT = "N7654321"`)
rather than minting new identifier formats. When §10.2 absorbs that file into
`tests/factories/party.py`, the roster below moves with it.

| Role | Name | Identifier | Notes |
|---|---|---|---|
| Lawyer A | `Lawyer A (synthetic)` | old-format NIC | Tenant A. Practising notary. |
| Lawyer B | `Lawyer B (synthetic)` | old-format NIC | Tenant B. The counterparty in every isolation test. |
| Buyer 1 | `First Buyer (synthetic)` | new-format NIC | First-time buyer |
| Buyer 2 | `Repeat Buyer (synthetic)` | new-format NIC | Repeat buyer |
| Seller 1 | `Individual Seller (synthetic)` | old-format NIC | Natural person |
| Seller 2 | `Synthetic Holdings (demo)` | `BR-SYN-0001` | Corporate seller; exercises the company-authority check |
| Mortgagee | `Demo Bank (synthetic)` | — | Exercises the mortgage-status check |

Document types: deed of transfer, mortgage bond, registry extract. Add a
password-protected PDF and a non-PDF renamed `.pdf` for §9.1.

Matters:

| Matter | Shape | Exercises |
|---|---|---|
| M1 | Simple freehold, no blockers | Appendix A happy path |
| M2 | Freehold with an encumbrance | Refusal 1 |
| M3 | Part-parcel | Refusal 4, Section 47 routing |

Tenancy pairing: Lawyer A owns M1 and M2, Lawyer B owns M3. Every isolation test
in §8.3 uses that pairing, so a leak shows up as a specific named matter rather
than an empty result that could also mean "nothing there".

---

## Appendix C — Commit plan

Group by concern, not by file. Five or more tests per commit. Conventional
Commits with epic-id scopes, per `CLAUDE.md`.

Eight commits, one per concern. Each is a reviewable unit that leaves the tree
green; none is a single test, and none mixes two areas.

| # | Commit | Contents | Approx. tests |
|---|---|---|---|
| 1 | `ci(test): run every suite and measure coverage` | F5, F6, F7, F3, F18, F22 — `ci.yml` runs `pnpm check` and `pytest -m "not live"`; Postgres service; `live` marker; `pytest-cov` + `@vitest/coverage-v8` with a recorded baseline; Playwright `global-setup.ts`, retries, reporters, route inventory; the `e2e`/`neon`/`live` jobs from §11.4 | 0 new — but **+43 backend files, 13 vitest files and 8 specs start running** |
| 2 | `test(fixtures): add factories, the DB fixture and the seed script` | F16, F17, §5.1–§5.2, §10.2, §10.4 — the `tests/factories/` tree, migrate four `fakes.py`, the rollback `db_session` fixture, `scripts/seed_synthetic_matter.py` | ~6 new, ~30 refactored |
| 3 | `test(auth): cover the token path, capabilities and tenancy` | F1, §8.1–§8.5 — the real `HTTPBearer` → Clerk path incl. 401s, capability and step-up HTTP, the parameterised tenancy sweep, `middleware.test.ts`. Rules 1 and 4 | ~45 |
| 4 | `test(worker): cover the outbox, the runner and its handlers` | F2, F4, §6.1–§6.5 — outbox policies, `claim_batch`/`reap_leases` on real Postgres, `process_message`'s two-session rollback path, notification and agent handlers, the §6.5 `xfail`s, the per-type lease defect, plus cursor signing, ETags and correlation ids. Rule 6 | ~110 |
| 5 | `test(db): cover repositories, the audit chain and migrations` | F14, §5.3–§5.4 — twelve repositories against the §2 baseline, the per-user hash chain incl. concurrency and tamper detection, `alembic` up/down/single-head/no-destructive-DDL, privacy dump test on real Postgres. Rules 2 and 3 | ~65 |
| 6 | `test(domain): cover matter routing, checklist and verification` | F8, F9, F12, §3.1 — Q01–Q22 routing, `MatterService`, `ChecklistService` and the six-axis status table, the auto-promotion guards, notarial-register policies, PayHere signature verification | ~145 |
| 7 | `test(api): cover every router, the matter flows and conformance` | F13, F19, §4.1–§4.3 — the five-test baseline across fourteen routers, intake→checklist, document→fact, fact→approved export with Appendix A's five refusals, billing quota, the `tests/conformance/` registry suite. Rules 5 and 7 | ~125 |
| 8 | `test(web): cover the store, lib, API clients and E2E journeys` | F10, F15, §3.2, §7.2, §11.3 — `demo-store`, `build-document`, `matter-stage`, label completeness, seven API client modules, extracted intake helpers, the refusal-path and matter-isolation specs, error recovery and upload review; then enable the ratcheting coverage thresholds | ~140 |

Roughly 580 new tests.

**Ordering is a dependency chain, not a preference.** Commit 1 is Phase 1a and
should land on its own — it changes no test but makes every existing one count,
and it is the cheapest commit here by a wide margin. Commit 2 must precede 3–8,
or each of them reinvents a fake and the duplication in F16 triples. Commits 4
and 5 need the Postgres service and `db_session` fixture from 1 and 2. Commit 8
turns the coverage gate on last, once there is a number worth gating.

Commits 3, 6 and 7 are the large ones and are the natural place to split further
if a reviewer asks — 6 splits cleanly by module (matter / task / verification /
billing) and 7 by layer (routers / flows / conformance). Do not split 4: the
outbox, the runner and its handlers are one mechanism, and testing a third of it
proves nothing about the other two thirds.

---

## Appendix D — Sign-off

This plan is complete when:

- [ ] All Critical findings (F1–F4) have passing tests.
- [ ] All High findings (F5–F12) have passing tests or a dated, owned exception.
- [ ] CI runs every suite the repo contains, with no vacuous path.
- [ ] A coverage number exists, is published in §A1, and is ratcheting.
- [ ] Each of the seven safety rules in §A2 maps to a named test file.
- [ ] Appendix A's happy path and all five refusals are covered at the API layer,
      not only in the browser.
- [ ] No test in the repo asserts only on a mock call.
- [ ] No new fake duplicates one in `tests/factories/`.
- [ ] `pytest -p randomly` passes three consecutive runs.
- [ ] The `xfail`s in §6.5 are fixed, or have an owner and a date.
- [ ] Decisions A6.1–A6.4 are recorded, including whichever way A6.4 resolves.

Human gates, not self-approvable per `CLAUDE.md`: the legal correctness of any
scenario touching prescribed statutory text, the synthetic roster in Appendix B,
and any decision to enable `PROVIDER_DATA_APPROVAL` for a test run.
