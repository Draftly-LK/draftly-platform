<!-- markdownlint-disable MD033 -->
<!-- The RUP technique tables need <br> to hold several lines in one cell. -->

# Draftly — Test Report

| Field | Value |
|---|---|
| Document | Test Report: software testing, evaluation of the data-science parts, and their error analysis |
| Identifier | DRAFTLY-MTP-002 |
| Version | 2.0 |
| Date | 2026-09-20 |
| Module | In23-S5-CS3501 Data Science and Engineering Project, Group 06 |
| Prepared by | Dhanapala D.H.N., Dilshan A.D.L., De Silva B.K.P. |
| Supervision | Dr. Nisansa de Silva (Mentor), Ms. Sathsarani A. (TA) |
| System | Draftly — a lawyer-in-the-loop legal workflow platform for Sri Lankan legal practice |
| Structure | Sections 1 to 5 follow the Rational Unified Process Master Test Plan template; sections 6 to 9 report the results |

## Revision history

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-09-18 | 1.0 | Draft raised with the audit of existing test coverage | Praveen, Himath, Lahiru |
| 2026-09-20 | 2.0 | Approach, techniques, results, DS evaluation and error analysis completed | Praveen, Himath, Lahiru |

## 1. Evaluation Mission and Test Motivation

Draftly prepares statutory land-registration instruments for Sri Lankan
notaries. A lawyer opens a matter, uploads title documents, reviews facts the
system extracts from them, works through a statutory checklist, and produces a
registration form, for example Form 8 for a transfer of land, which the lawyer
approves and exports.

The motivation for this test effort is that the cost of a silent error is
legal, not cosmetic. A wrong parcel number on a transfer, a repealed statute
quoted as current, or one lawyer seeing another firm's client data is a
professional failure and may be a breach of the Personal Data Protection Act.
The system also places machine output in front of a lawyer, so the product's
central promise is that no machine value ever becomes a fact, or reaches an
approved document, without a lawyer's decision.

An audit of the existing tests at the start of this iteration found 22
weaknesses, 4 of them critical: the real login path was never executed by any
test, the background worker had no tests, signed pagination cursors had no
tests, and the browser suite could not sign in. Continuous integration ran 245
of the repository's tests and none of the frontend ones. No coverage figure
existed for either stack. That is the state this plan addresses.

The mission of the evaluation in this iteration is to:

- verify the seven safety rules the product rests on, at the layer that
  enforces them, rather than only in the browser;
- find important problems in the areas where a defect is invisible to the user:
  concurrency, data at rest, message delivery, and access control;
- assess quality risk by measuring coverage honestly and publishing the number,
  rather than claiming a level of testing the repository cannot show;
- verify the specification, meaning the documented API conventions, the rule
  pack and the refusals the workflow must make;
- advise on project risk by recording each gap as a test that fails on purpose,
  so an open question is visible in the build rather than in a comment.

Performance, load, failover and configuration testing are planned here but not
executed in this iteration, for the reasons given in each section. The system
is not production-ready and runs on synthetic data only, so those techniques
would measure a configuration nobody will deploy.

## 2. Target Test Items

| Item | Description | Relative importance |
|---|---|---|
| Backend application (FastAPI, Python 3.12) | 17 routers, 25 registered services, the domain rule pack | Highest: enforces every safety rule |
| Domain policies | Fact promotion, checklist satisfaction, intake routing, approval gates | Highest: the legal gates |
| PostgreSQL database and Alembic migrations | 61 tables, optimistic concurrency, audit hash chain | Highest: correctness at rest |
| Outbox and background worker | Job claim, retry, dead-letter, lease reaping | High: silent failure otherwise |
| Platform utilities | Signed pagination cursors, ETag and If-Match handling, error envelope | High: security-relevant |
| Frontend application (Next.js 15, React 19) | 37 client components, of which 23 carry logic; the offline demo state store; 7 API client modules | High |
| Authentication and identity (Clerk adapter) | Token validation, roles, capabilities, step-up | Highest |
| Third-party integrations | Payment webhook, email webhook, object storage, AI extraction and OCR | Medium: verified at the adapter boundary |
| Continuous integration pipeline | GitHub Actions workflow, PostgreSQL service, coverage gates | High: the plan is worthless if CI does not run it |
| Data-science components | Statute and case retrieval, headnote recovery, OCR field extraction | Medium here: evaluated in the research repository |

Items deliberately excluded: the marketing landing page, and any test that
would need real client data. All test data is synthetic and labelled.

## 3. Test Approach

The approach follows one principle: **test each rule at the layer that enforces
it.** A tenancy rule enforced in the database is tested against a real
database; a refusal enforced in a service is tested through that service; a
rule enforced in the browser is tested in a browser. Tests that assert only
that a mock was called are rejected in review, because they pass when the
system is broken.

Four practices support that principle:

1. **Real dependencies over fakes where behaviour differs.** Repository and
   service tests run against PostgreSQL 16 in Docker, on a schema built by the
   project's own migrations, rolled back after each test. Twelve of the fifteen
   defects found in this iteration appear only on a real database: foreign-key
   ordering, row locking and concurrent transactions.
2. **Sweeps generated from the specification.** Route-level rules are checked
   by reading the published OpenAPI description and asserting the rule against
   every route of a kind, so a new route is covered the day it is added.
3. **Every test is proven able to fail.** After each fix, the repaired code is
   broken again on purpose, the test is observed to fail, and the code is
   restored. A test that has never failed has not been shown to test anything.
4. **Gaps are recorded as failing-on-purpose tests.** Where the product has a
   gap that needs a decision rather than code, a strict expected-failure test
   holds it. If someone closes the gap, the test passes unexpectedly and the
   build reports it.

### 3.1 Testing Techniques and Types

#### 3.1.1 Data and Database Integrity Testing

The database and its processes are tested as an independent subsystem, without
the user interface as the route to the data.

| | |
|---|---|
| Technique Objective: | Exercise every repository and migration against a real PostgreSQL instance, so that optimistic concurrency, foreign-key ordering, row locking, the audit hash chain and encryption at rest are verified rather than assumed. |
| Technique: | A fixture creates a throwaway schema per test and runs the project's real `alembic upgrade head` against it, so the schema under test is the schema that will ship.<br>Each test runs in an outer transaction with a savepoint and is rolled back afterwards; tests that need real commits truncate instead.<br>Repository methods are invoked directly with synthetic aggregates, then the rows are read back and asserted, including version columns.<br>Concurrency is exercised with two independent sessions racing on the same row, for the audit chain and the usage quota.<br>Migration integrity is checked by comparing the ORM models against the migration head with Alembic autogenerate, and by walking every migration up and down.<br>Data at rest is checked by dumping the live database and searching the dump, including the hexadecimal form of binary columns, for any plaintext client identifier. |
| Oracles: | Row state read back through a second session; version columns incremented exactly once per write; the audit chain recomputed independently and compared link by link; the autogenerate diff, which must be empty apart from a declared drift list; the database dump, which must contain no plaintext identifier; database constraint violations surfaced as typed domain errors rather than raw driver errors. |
| Required Tools: | pytest with pytest-asyncio; SQLAlchemy (async) and psycopg; PostgreSQL 16 in Docker; Alembic; pytest-cov; a synthetic seed script that builds a matter through the real services. |
| Success Criteria: | Every repository that the application ships has a test file; every versioned aggregate has a stale-write test; the audit chain cannot fork under concurrency; the quota cannot be overspent or double-refunded under concurrency; the migration drift list is explicit and shrinking; no plaintext identifier appears in a dump. |
| Special Considerations: | Party tables use JSONB columns that do not build on SQLite, so database tests must not fall back to an in-memory engine. On Windows the asynchronous driver requires a selector event loop, which the test configuration supplies. Tests must never run against a developer's own database: the fixture refuses to start unless a test database URL is configured. |

#### 3.1.2 Function Testing

Function testing verifies the business rules and the lawyer workflow: proper
acceptance, processing and retrieval of data, and the refusals the product must
make.

| | |
|---|---|
| Technique Objective: | Exercise each documented workflow step and each refusal in Appendix A of the detailed plan, through the real service graph, and verify that the system stops where it must stop rather than finding a way through. |
| Technique: | Domain policies are tested as pure functions across the full decision table, for example every combination of checklist statuses and every intake answer in the question catalogue.<br>Application services are driven through their real repositories over PostgreSQL, wired exactly as the application bootstrap wires them.<br>Each refusal is asserted as a refusal: an open statutory blocker stops draft generation; an unapproved draft cannot be exported; a machine value with high confidence never fills a field; a declared instrument without its legal basis is rejected.<br>Intake routing is cross-checked against the committed rule pack, so a contract change in the rule pack fails a test rather than silently altering behaviour.<br>State transitions are exercised for the matter lifecycle, draft approval and export, and outbox job states. |
| Oracles: | The domain error type raised, not merely that an error occurred; the persisted state after the call, read back independently; the audit event appended for the action, including its action name and target; the compiled checklist snapshot compared with the rule pack; committed contract files, which fail the build if the behaviour drifts from them. |
| Required Tools: | pytest; the application's own dependency-injection bootstrap; PostgreSQL 16; the synthetic seed script; committed JSON contract fixtures for the rule pack and OpenAPI description. |
| Success Criteria: | Every service that carries a legal gate has a test file; each refusal is covered at the service layer, not only in the browser; no test asserts only that a mock was called; the rule-pack contract test fails when a committed contract changes. |
| Special Considerations: | The happy path cannot currently reach a registration-ready export, because every form template in the repository is an unverified transcription and the system correctly refuses. Verifying the wording of a statutory template is a human task owned by the legal team, and a test must not work around it. |

#### 3.1.3 User Interface Testing

| | |
|---|---|
| Technique Objective: | Verify that a lawyer can complete the demonstration workflow in a browser, that every status is readable as text and not by colour alone, that both interface languages render without raw message keys or clipping, and that the screens meet accessibility rules. |
| Technique: | Component tests render individual React components in a browser-like environment with the real translation catalogue, so a missing key fails the test rather than the page.<br>Browser journeys drive the running application with Playwright over Chromium: the demonstration path end to end, the refusal paths, a route inventory sweep, and locale sweeps in English and Sinhala.<br>Design conformance is asserted from computed styles rather than by eye: design tokens, corner radius, row height, fonts actually loaded, and the absence of gradients and shadows in the dense workspace.<br>Accessibility is asserted with an automated axe sweep over every route, plus keyboard-only navigation, focus visibility, Escape handling, reduced motion and 200 per cent reflow.<br>Pure presentation logic, such as label maps and the stage map, is unit tested so the browser suite is not the only place they are checked. |
| Oracles: | The translation catalogue, which must resolve every key used; the design tokens declared in the design plan, compared with computed styles; the axe rule set at serious and critical level; the visible text of a status, which must accompany its colour and icon; the audit feed, which must show an action after the user performs it. |
| Required Tools: | Vitest with happy-dom and Testing Library for components; Playwright with Chromium for journeys; axe-core for accessibility; the Next.js development server for local runs and a production build in CI. |
| Success Criteria: | The demonstration journey completes; each refusal that the interface owns is blocked with a visible reason; no route shows a raw message key in either language; no serious or critical accessibility violation; the declared design tokens match the computed ones on every route. |
| Special Considerations: | Several screens require a signed-in session from the authentication provider, and test credentials for it are not yet available, so those journeys are covered at the API layer instead. Browser specs must run one worker at a time: parallel workers starve a single development server and produce timeouts that look like defects. The two sweeping specs belong against a production build rather than a development server. |

#### 3.1.4 Performance Profiling

| | |
|---|---|
| Technique Objective: | Measure response time for the transactions a lawyer performs most often — opening a matter, listing matters, compiling a checklist, generating a draft — and establish a baseline before optimisation, so that a later change can be shown to help or harm. |
| Technique: | Instrument the API with per-request timing already emitted in the structured logs, then drive each transaction repeatedly against a database seeded to a realistic size.<br>Record the median and 95th percentile per transaction, separating database time from application time.<br>Profile the two operations known to be heaviest: checklist compilation, which walks the rule pack, and document processing, which calls an external model. |
| Oracles: | A recorded baseline per transaction; the database's own query plans for the slowest statements; timing already captured per test by the test runner, which flags a case that becomes markedly slower. |
| Required Tools: | The application's structured logs; PostgreSQL `EXPLAIN ANALYZE`; pytest durations; a seeded database at a realistic row count. |
| Success Criteria: | Every lawyer-facing transaction has a recorded median and 95th percentile; no transaction depends on a query without an index on its filter columns; the figures are published beside the coverage figures. |
| Special Considerations: | **Not executed in this iteration.** The system has no production deployment and no production data volume, so a measurement taken now would describe a laptop rather than the deployed system. The deployment plan states the first bottleneck is expected to be database cold start on the managed provider, which cannot be reproduced locally. This technique is scheduled for the first staging deployment. |

#### 3.1.5 Load Testing

| | |
|---|---|
| Technique Objective: | Determine whether the system behaves correctly under concurrent use by several notarial offices, and whether the background worker keeps up when jobs arrive faster than they are processed. |
| Technique: | Drive the API with a scripted workload at increasing concurrency, using synthetic matters, and record error rate and response time at each level.<br>Enqueue a backlog of background jobs and observe claim rate, retry behaviour, lease expiry and dead-lettering under sustained load.<br>Repeat the concurrency tests that exist today, the audit chain and the quota, at a higher number of parallel writers. |
| Oracles: | Error envelope counts by status code; the outbox table, which must show no job claimed twice and none stuck; the audit chain, which must remain unbroken at every load level; quota rows, which must never fall below zero. |
| Required Tools: | A load driver such as k6 or Locust; PostgreSQL statistics views; the worker's own metrics; Docker for a multi-instance run. |
| Success Criteria: | No lost or duplicated job at the target concurrency; no broken audit chain; error rate within the agreed threshold; the system degrades by slowing rather than by corrupting. |
| Special Considerations: | **Not executed in this iteration.** Load testing against a shared managed database would distort the measurement and could exhaust a free tier. The concurrency correctness this technique protects is already covered at small scale by database tests that race two real sessions, which is where the defects were found. |

#### 3.1.6 Security and Access Control Testing

| | |
|---|---|
| Technique Objective: | Verify both layers of access control: system-level, that only a validly authenticated caller reaches the application; and application-level, that a caller sees and changes only what their role and their organisation permit. |
| Technique: | The real token path is exercised end to end: the bearer token is minted locally by the test, and only the provider's key source is substituted, so the application's own validation, audience checks and expiry handling run as in production.<br>Roles and capabilities are asserted per route: a caller without the capability receives 403, and a caller from another organisation receives 404 rather than 403, so that no identifier leaks through an error.<br>A tenancy sweep is generated from the OpenAPI description and applied to every matter-scoped route, so a new route cannot quietly omit the check.<br>Unauthenticated surfaces are swept: every route that takes no bearer token is listed and justified, and every other route must answer 401 without one.<br>Conditional requests are swept: every versioned write must demand `If-Match`, answer 428 when it is missing and 412 when it is stale.<br>Public webhooks are fuzzed at the signature boundary with forged, truncated, non-ASCII and non-UTF-8 payloads.<br>Signed pagination cursors are attacked with forged, truncated and re-signed values. |
| Oracles: | The HTTP status code and the error envelope, including the stable error code and the echoed correlation identifier; the absence of any resource identifier in a refusal body; the audit log, which must record the refusal; the database, which must be unchanged after a refused write. |
| Required Tools: | pytest with httpx against the real application; a locally minted JSON Web Key Set; the OpenAPI description as the source of the route list; PostgreSQL for tenancy fixtures. |
| Success Criteria: | No route bypasses authentication; no cross-organisation read or write succeeds; a foreign resource is indistinguishable from a missing one; every versioned write demands its version; a forged signature or cursor is refused rather than raising an unhandled error. |
| Special Considerations: | Step-up authentication for legally significant actions is specified but the policy for approval is still open, so the test records the current behaviour and will be tightened when the policy lands. Access to the production authentication tenant is not required: the tests mint their own keys, which is what allows them to run offline in CI. |

#### 3.1.7 Failover and Recovery Testing

| | |
|---|---|
| Technique Objective: | Verify that the system recovers from a failed dependency without losing or duplicating work: a database that goes away mid-transaction, an external model that times out, a worker killed while holding a job, and a storage bucket that refuses a write. |
| Technique: | Kill a worker process while it holds a claimed job and observe that the lease expires and the job is reclaimed exactly once.<br>Point the application at an unreachable database and assert that readiness reports unhealthy rather than hanging.<br>Fail an external call deterministically and assert that the job retries with backoff and eventually dead-letters rather than looping.<br>Interrupt a multi-step write and assert that the transaction leaves no partial aggregate behind.<br>Exercise restore: take a backup, drop the schema and restore it, then run the migration chain to head. |
| Oracles: | The outbox table, which must show one completed attempt per job and a dead-letter row after the retry budget; the audit chain, which must remain unbroken across the failure; the readiness endpoint; the restored database compared with the original by row counts and chain verification. |
| Required Tools: | Docker to stop and start dependencies; the worker's lease configuration; the database's point-in-time recovery tooling; pytest for the deterministic failure injection. |
| Success Criteria: | No job is executed twice; no job is lost; no partial aggregate survives a failure; a restore has been performed at least once and recorded, because a restore that has never been executed is not a backup. |
| Special Considerations: | **Partly executed in this iteration.** Lease expiry, retry, backoff and dead-lettering are covered by tests against a real database, and a defect was found and fixed there. Process-level failover and restore rehearsal need a deployed environment and are scheduled with the first staging deployment. |

#### 3.1.8 Configuration Testing

| | |
|---|---|
| Technique Objective: | Verify that the system behaves identically on the configurations it must support: the developers' Windows machines, the Linux continuous-integration runner, and the target deployment; and in both interface languages, on the supported viewport range and browsers. |
| Technique: | Run the entire suite on both Windows locally and Linux in continuous integration, and treat any difference as a defect in the code or the test, not as an environment quirk.<br>Run the browser suites at the supported viewport widths and in both English and Sinhala.<br>Run the test suite in randomised order three times, so that no test depends on another test's state.<br>Pin every dependency and verify the lock file in continuous integration, so an environment cannot drift silently. |
| Oracles: | Identical pass and fail sets across operating systems; the lock file check; the randomised-order runs; the layout probes, which must show no horizontal overflow at any supported width. |
| Required Tools: | GitHub Actions with a PostgreSQL service; Docker; pytest-randomly; Playwright device and viewport configuration; `uv lock --check` and a frozen pnpm install. |
| Success Criteria: | The suite passes on both operating systems; three consecutive randomised-order runs pass; both locales render without raw keys; no supported viewport overflows. |
| Special Considerations: | Browser coverage is Chromium only in this iteration. The application targets desktop use in notarial offices, so mobile browsers are out of scope, but the layout is still asserted down to 768 pixels. Windows requires a selector event loop for the asynchronous database driver, which the test configuration supplies rather than the application. |

## 4. Deliverables

| Deliverable | Form | Audience |
|---|---|---|
| Automated test suites | Code in the repository, run by continuous integration on every pull request | Development team |
| Test completion report | `docs/review/testing-report.md`, following ISO/IEC/IEEE 29119-3 | Supervisor, team, assessor |
| Defect records | Commit history, each fix paired with the test that proves it | Development team |
| Coverage reports | Terminal summary per run, plus a machine-readable report for the gate | Development team |
| Continuous-integration results | GitHub Actions run, with a JUnit XML file and an HTML report for browser runs | Whole team |
| Reusable test assets | Factories, database fixtures, security harness, seed script, request recorder | Anyone writing the next test |

### 4.1 Test Evaluation Summaries

A summary is produced at the end of each stage of work and at the end of the
iteration. Each states: the suites run and their pass, fail and skip counts;
the defects found, with severity and the test that now protects each fix; the
coverage figures for both stacks; the criteria from the plan that are met, and
those that are not, with the reason and the owner. The end-of-iteration summary
is the test completion report named above.

### 4.2 Reporting on Test Coverage

Coverage is measured on every continuous-integration run: `pytest-cov` for the
backend and the v8 provider through Vitest for the frontend, both reported in
the run log and written to a machine-readable file.

Coverage is gated by a ratchet rather than a fixed target. Each floor sits one
point below the number last measured and is raised when the suite beats it, so
coverage can rise but never fall. A fixed target on a repository with no
existing number fails the next change and is switched off within a week.

The report distinguishes line coverage from branch coverage, and reports the
logic layers separately from the presentation layers, because a single
repository-wide number lets a well-tested module hide an untested one.
Coverage is treated as a floor, not a goal: a highly covered module whose tests
assert only that a call returned something is worse than a less covered one
with real assertions, and the review checklist rejects a coverage-only
justification.

## 5. Risks, Dependencies, Assumptions, and Constraints

| # | Risk, dependency or constraint | Likelihood | Impact | Mitigation or contingency |
|---|---|---|---|---|
| 1 | Authentication test credentials are unavailable, so the screens that need a signed-in session cannot be driven in a browser | High | Medium | Cover the same rules at the API layer, where they are enforced; request test credentials; keep the browser specs written and skipped rather than deleted |
| 2 | Statutory template wording is not verified, so the workflow cannot reach an approved export | High | Medium | Test the refusals instead, which do not depend on the wording; escalate verification to the legal team; never work around the gate in a test |
| 3 | Paid external services (model, vision, storage) cannot run in routine testing | High | Medium | Mark those tests `live` and exclude them from routine runs; test the adapter boundary with recorded and fuzzed payloads; run the live suite manually when a key is available |
| 4 | Open decisions (database in CI, coverage gate style, a showcase route, the missing scheduler) block the tests that depend on them | Medium | Medium | Record each as a failing-on-purpose test with a named owner, so the decision is visible in the build |
| 5 | A single development server cannot serve parallel browser workers, producing timeouts that look like defects | Medium | Medium | Pin the browser suite to one worker; run the sweeping specs against a production build in CI |
| 6 | Tests that need a real database are skipped silently when one is absent, hiding loss of coverage | Medium | High | A configuration flag makes a missing database a failure rather than a skip, and CI always provides one |
| 7 | Synthetic fixtures could drift towards real client data | Low | High | All fixtures are synthetic and labelled; a privacy assertion fails the run if a value-bearing column reaches a tracked path; nothing is copied from the research data |
| 8 | Test data that is not deterministic makes failures unreproducible | Medium | Medium | Fixed identifiers and a fixed clock in every factory; no random values; randomised execution order is proven safe separately |
| 9 | Performance and load characteristics remain unmeasured until a deployment exists | High | Medium | Schedule both techniques with the first staging deployment; keep the concurrency correctness tests that already exist |
| 10 | The plan depends on continuous integration actually running every suite | Low | High | CI runs the whole suite with a database service and fails on coverage regression; a vacuous path is treated as a defect in the pipeline |

**Assumptions.** The team continues to use PostgreSQL as the only production
database engine; the rule pack remains the single source of truth for legal
structure; all testing before deployment uses synthetic data; and lawyer
verification remains a human step that no test may simulate.

## 6. Software testing results

### 6.1 Test execution

Final runs on 2026-09-19:

| Suite | Run | Passed | Failed | Skipped or excluded | Expected failures |
|---|---|---|---|---|---|
| Backend (pytest, real PostgreSQL) | 3922 collected | 3906 | 0 | 1 skipped, 5 `live` excluded | 10 |
| Frontend unit and component (Vitest) | 348 | 348 | 0 | 0 | 1 (see 6.2) |
| Browser: refusal journey (Playwright, new) | 3 | 3 | 0 | 0 | 0 |

The expected failures are the known-gap tests described in section 3, the
fourth practice of the test approach. None of them hides a failure: each would fail the build
if it started to pass.

**Growth over the test period:**

| Measure | Before | After |
|---|---|---|
| Backend tests run by CI | 245 | 3906 |
| Frontend unit tests run by CI | 0 (13 files existed) | 348 (30 files) |
| Backend suites run by CI | 3 folders | all (`-m "not live"`) |
| Tests on real PostgreSQL in CI | 0 | the whole `tests/db` and `tests/security` suites |

### 6.2 Stability

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

### 6.3 Coverage

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
are blocked on the authentication test credentials named in section 5.

**Coverage gates.** CI now fails if coverage falls below a floor set one point
under the numbers above: backend combined 81%; frontend lines 26% overall,
92% in `src/lib/`, 2% in `src/components/`. Each floor is raised when the
suite beats it, so coverage can rise but never fall. Both gates were checked by
raising a floor above the real number and confirming that the run failed.

### 6.4 Defect measures

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

### 6.5 Defects found and fixed

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

## 7. Test completion evaluation

### 7.1 Exit criteria (plan Appendix D)

| Criterion | Status | Evidence or reason |
|---|---|---|
| All Critical findings (F1–F4) have passing tests | Met | the traceability table in the completion report; the Clerk-signed browser run for F3 needs keys |
| All High findings (F5–F12) have passing tests or an owned exception | Met | the traceability table in the completion report |
| CI runs every suite, with no vacuous path | Partly met | All backend and frontend unit suites run; browser tests are not in CI (Clerk keys) |
| A coverage number exists, is published and ratchets | Met | Section 6.3 |
| Each of the seven safety rules maps to a named test file | Met | the traceability table in the completion report |
| No new fake duplicates the shared factories | Met for this cycle | New tests use `tests/factories/` |
| Random-order runs pass three times in a row | Met | Section 6.2 |

**Summary:** of the criteria assessed this cycle, 6 are met and 1 is partly
met. Four further criteria from Appendix D are carried to the next phase, for
the reasons in section 5.

### 7.2 Overall assessment

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
and the browser journeys run in CI, and until each known gap recorded as a
failing-on-purpose test has an owner and a date.

## 8. Evaluation of the data-science parts

Draftly's data-science components are evaluated in the research repository
(`evaluation/runs/`, `ocr-benchmark/`), separately from the platform. This
section reports their measured results as they stand on 2026-09-20. Every
number below comes from a committed metrics file in that repository.

**In one line:** the retrieval components have real numbers and they are low;
the document-reading components have no accuracy number at all, because the
paid runs are blocked on credentials.

### 8.1 Components and how each is measured

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

### 8.2 Retrieval results

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

### 8.3 Similar-case retrieval, by variant

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

### 8.4 Document reading

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

### 8.5 How far these results can be trusted

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
and the workflow refusal tests hold it.

## 9. Error analysis of the data-science parts

The failures are concentrated, not spread evenly: the same questions fail in
every configuration, and the weakest slice is statutes that changed after the
judgment was written.

### 9.1 Statute retrieval: most questions return nothing usable

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

### 9.2 Small question sets flattered the baseline

The BM25 baseline scored recall@10 of 0.590 on 10 questions. Retrieval on 462
questions scores 0.238. The 10-question figure was not wrong, it was
unrepresentative: a difference of more than two times, produced by sample size
alone. Any decision taken on a 10-question result should be taken again.

### 9.3 A hard core of similar-case queries

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

### 9.4 Two features made the results worse

Lexical IDF weighting dropped accuracy from 0.70 to 0.30, and combining it with
verified-only edges dropped it to 0.25. Catchword edges and statute links were
the only features that stayed near the baseline. This negative result is worth
recording: the intuitive improvement was the harmful one.

### 9.5 The grader itself is unstable

The baseline was graded 0.70 in one run and 0.50 in a repeat of the same
configuration. The corpus fingerprint also changed between the two, so the
experiment cannot separate grader variance from corpus change. Either way, a
20-point swing on an unchanged pipeline is larger than most of the differences
the variants are trying to measure, so no ranking of these variants is safe.

### 9.6 Where the headnote extractor gives up

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

### 9.7 Document reading: the error is in the experiment, not the model

The dominant failure is environmental, not statistical: five of six pipelines
never ran. The credential error is a configuration fix, and the licence
question needs a decision rather than research. Until both are cleared, the
project has no evidence for its most lawyer-visible claim, that it can read a
scanned deed accurately.

The one signal available is script-dependent confidence: the overall mean is
0.904, but the Sinhala-dominant identity-card pages read at 0.818. Sinhala is
21.7% of all characters in the corpus, so a weakness there is not a corner
case.

### 9.8 What to do next

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

## 10. References

Tools used for testing:

1. pytest, available at <https://docs.pytest.org/>
2. pytest-asyncio, available at <https://pytest-asyncio.readthedocs.io/>
3. pytest-cov, available at <https://pytest-cov.readthedocs.io/>
4. pytest-randomly, available at <https://github.com/pytest-dev/pytest-randomly>
5. Vitest, available at <https://vitest.dev/>
6. Testing Library (React), available at <https://testing-library.com/>
7. happy-dom, available at <https://github.com/capricorn86/happy-dom>
8. Playwright, available at <https://playwright.dev/>
9. axe-core, available at <https://github.com/dequelabs/axe-core>
10. PostgreSQL 16, available at <https://www.postgresql.org/docs/16/>
11. Alembic, available at <https://alembic.sqlalchemy.org/>
12. Docker, available at <https://docs.docker.com/>
13. GitHub Actions, available at <https://docs.github.com/actions>

Standards and methods:

1. ISO/IEC/IEEE 29119-3:2021, *Software and systems engineering — Software
   testing — Part 3: Test documentation*.
2. IEEE Std 829-2008, *IEEE Standard for Software and System Test
   Documentation*.
3. Rational Unified Process, *Master Test Plan template*, IBM Rational
   Software, from which this document's structure is taken.
4. Web Content Accessibility Guidelines (WCAG) 2.2, W3C Recommendation,
   available at <https://www.w3.org/TR/WCAG22/>.

Project documents:

1. `docs/TESTING_PLAN.md` — the detailed test plan, its audit of existing
   coverage, and its sign-off criteria.
2. `docs/review/testing-report.md` — the test completion report for this
   iteration.
3. `docs/DEPLOYMENT_PLAN.md` — deployment readiness, which sets when
   performance, load and failover testing become meaningful.
