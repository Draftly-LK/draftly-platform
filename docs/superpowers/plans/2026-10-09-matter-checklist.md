# Matter checklist implementation plan

> **For agentic workers:** Use superpowers:executing-plans with independent
> implementation and review agents. Follow test-driven development.

**Goal:** Make the full matter journey actionable from Overview, preserving the
existing legal decisions and evidence history.

**Architecture:** Task-owned operational records and a combined read projection
join existing owner state. AI suggestions remain proposals until lawyer acceptance.
The frontend follows typed action targets and displays server-computed progress.

**Tech stack:** FastAPI, SQLAlchemy, PostgreSQL, Next.js, next-intl, Vitest,
pytest and Playwright.

**Spec:** [Approved design](../specs/2026-10-09-matter-checklist-design.md).

## Global constraints

Preserve legal policy, original evidence, decision history, explicit scope pins,
capabilities and exact mutation retries. Keep 75% global branch coverage and all
repository gates. Synthetic fixtures only. Never commit or push to main.

## Tasks and commit boundaries

- [x] Persist operational tasks, suggestions and append-only history with an
  additive migration and task-owned authorized/versioned commands. Test isolation,
  concurrency, replay, source pins, completion and cancellation before implementing.
- [x] Project requirements, document/fact/check/form/event state and custom tasks
  into six display groups, known leaf counts, assessment state and next action.
  Test empty/unknown, stale, duplicate and incomplete dependencies.
- [x] Connect existing agent follow-through to durable proposals. Test duplicate
  events, accepted/dismissed proposals and invalidated source versions.
- [x] Build Overview progress, grouped tasks, task creation, suggestions, actions
  and history. Preserve the matter assistant behind an expandable section. Test
  mutations, failed requests, refresh, obsolete responses and bilingual layout.
- [x] Connect shared transaction setup on Checks, explicit requirement dimensions,
  live evidence actions, neutral issue gates and truthful shell completion. Test
  missing associations, explicit selection, stale versions and unresolved evidence.
- [x] Run synthetic browser acceptance and accessibility checks; record durable
  review evidence. Obtain independent review, resolve important findings and run
  final gates before pushing the feature branch and opening a PR.

Each coherent change is committed only after its relevant checks pass. Before
any screen-done commit run frontend typecheck, lint and build. Backend changes
run lock, Ruff, format, mypy and pytest gates; exercise the additive migration.

## Integration and delivery

Update OpenAPI and private service documentation with actual interfaces. Keep
existing routes compatible. New backend support precedes the frontend rollout;
rollback must retain operational records. The PR reports the implemented journey,
review findings/resolutions, test evidence, commit list and remaining limits.
