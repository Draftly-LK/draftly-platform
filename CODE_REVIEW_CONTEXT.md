# Draftly repository review context

Use this context only for pull-request review. `AGENTS.md` and `CLAUDE.md`
remain the instructions for agents implementing changes.

## Sources of truth

- Frontend behavior follows `docs/plan.md` and
  `docs/reference/draftly-interface-spec.md`.
- Backend behavior follows `backend/backend-implementation-plan-v0.md`,
  `backend/docs/infrastructure.md`, and the affected plans under
  `backend/docs/services/`, indexed by `backend/docs/services/README.md`.
- Rules that apply to every backend service live in five cross-cutting
  documents: `backend/docs/security-model.md` (organisation boundary,
  capability catalogue, role map, 404-not-403), `api-conventions.md`
  (paths, pagination, concurrency, idempotency, errors, job envelopes),
  `events.md` (the domain-event registry), `jobs-and-workers.md` (outbox,
  claim protocol, scheduled jobs), and `service-definition-of-done.md` (the
  level ladder and the cross-service conformance suite). **Where a service plan
  and one of those five disagree, the cross-cutting document wins.**
- `backend/contracts/services.yaml` is the machine-readable service registry
  that the conformance suite is parameterised over. A new service, event,
  capability, metered operation, owned table, or job must be registered there,
  and `backend/docs/services/README.md` must agree with it.
- Frontend contract breaks are recorded in
  `backend/docs/frontend-contract-migration.md`.
- Backend service plans are private, authoritative implementation inputs. Code
  may implement them, and a change may update them when it changes a documented
  API, invariant, data model, port, provider decision, or phase status.
- Open decisions and approval gates remain unresolved until their named owner or
  the user approves them. Do not infer a production provider or legal policy.

## Repository-wide boundaries

- Never accept real client data, including real names, NICs, addresses, matter
  identifiers, deeds, registry numbers, pedigree chains, production logs, or
  private legal instructions.
- Do not accept Harvey screenshots, logos, wording, or proprietary assets.
- Do not import or copy arbitrary raw material from `../draftly-research`.
- Treat statutory text, form-template legal copy, and approval or waiver
  language as human-owned. Review structure and enforcement, not the wording.

## Backend invariants

- Use Python 3.12 and `uv` for backend dependency management and commands.
- Preserve the dependency direction: API routers call application services;
  application services use domain logic and ports; infrastructure implements
  ports. Domain modules must not import FastAPI, SQLAlchemy, provider SDKs,
  frontend types, or frontend fixtures.
- Keep original evidence immutable. Machine derivatives and working memory are
  non-authoritative. Only lawyer-verified or lawyer-corrected facts may feed an
  approved output.
- Enforce organization and matter isolation on the server. Do not rely on UI
  filtering, client-supplied tenant identifiers, or unscoped repository queries.
- Append audit events for material mutations. Approval, correction, export, and
  deletion paths must not bypass their required audit trail.
- Do not silently weaken trust boundaries, verification requirements, retention
  rules, or approval gates documented in backend service plans.
- A record under an active legal hold cannot be destroyed, merged, expired, or
  collected by any sweep.
- Every lifecycle state has exactly one owning service that can enter it. Flag a
  change that leaves a state reachable only from a service that refuses to enter
  it.
- Relevant backend gates are `uv lock --check`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest`
  including `tests/conformance`, limited to gates available in the current
  implementation phase.

### Registry checks

These are mechanical and worth checking on any backend change:

- An event published or consumed in code that is absent from
  `backend/docs/events.md`, or spelled differently there. A consumed event with
  no publisher never fires, and the failure is silent.
- A service, owned table, capability, job, or metered operation added without a
  matching entry in `backend/contracts/services.yaml`.
- A metered operation added with no `require_feature` and `reserve_usage` pair,
  or with no release on terminal failure.
- A new customer-owned table with no `organisation_id` column.
- A mutating application method with no corresponding audit write.

## Frontend invariants

- Use pnpm through Corepack. Do not introduce npm or yarn workflows.
- Keep TypeScript strict. Any `any` escape requires a justification comment.
- Route all user-facing strings through `next-intl`; use typed English and
  Sinhala label maps for enum labels.
- Keep mock data deterministic. Do not use `Date.now()` or `Math.random()` in
  render paths.
- Keep mock accessors asynchronous and retain the named `TODO(api)` endpoint
  boundary until the real API replaces them.
- Bind both Ctrl+K and Command+K. Load Tiptap client-side with SSR disabled.
- Never communicate status through color alone; include an icon and text label.
- Enforce the design tokens and Aceternity boundary defined in `docs/plan.md`.
- Relevant frontend gates are `pnpm typecheck`, `pnpm lint`, and `pnpm build`.

## Review limits

- Do not invent details from a plan that is unavailable in the review context.
- When correctness depends on an unavailable contract, identify the missing
  evidence without claiming that the implementation violates the contract.
- Treat AI review as advisory. Deterministic CI and a human reviewer remain the
  merge authority, and legal judgment always remains human-owned.
