<!-- markdownlint-disable MD033 -->
<!-- The RUP technique tables need <br> to hold several lines in one cell. -->

# Draftly Platform — Master Test Plan

| Field | Value |
|---|---|
| Document | Master Test Plan |
| Version | 1.0 |
| Date | 2026-09-20 |
| Author | Praveen De Silva |
| System | Draftly — legal drafting platform for Sri Lankan notaries |
| Repository | `draftly-platform`, branch `platform/praveen` |
| Companion documents | `docs/TESTING_PLAN.md` (detailed plan), `docs/review/testing-report.md` (completion report) |

## Revision history

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-09-18 | 0.1 | Draft raised with the audit of existing test coverage | Praveen De Silva |
| 2026-09-20 | 1.0 | Approach, techniques, deliverables and risks completed | Praveen De Silva |

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

## 6. References

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
