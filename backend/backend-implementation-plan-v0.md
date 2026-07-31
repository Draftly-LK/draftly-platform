# Backend Implementation Plan — V0

## 1. Purpose

This document defines the implementation plan for the V0 backend of the
lawyer-in-the-loop RTA workbench. The backend is the server-enforced boundary
between the browser, confidential matter data, controlled legal content,
document processing, grounded research, deterministic checks, drafting,
approval, export, and audit history.

The plan is intentionally implementation-oriented. It describes the first
usable backend structure, the order in which it should be built, the contracts
that must be stable, and the gates that prevent an attractive demo from
becoming an unsafe legal system.

## 2. Scope and Boundary

### 2.1 V0 backend scope

The V0 backend shall provide:

- authenticated users, organisation workspaces, roles, and matter membership
  checks;
- organisation-owned subscriptions, plan entitlements, usage quotas, and
  provider-neutral recurring billing;
- matter creation, assignment, lifecycle, and privacy-safe references;
- immutable document upload and versioning;
- asynchronous document-processing jobs with visible states;
- a provider adapter for Google Document AI OCR and quality analysis;
- document classification, source spans, candidate particulars, and manual
  review states;
- lawyer verification, correction, rejection, conflict, and blocked states;
- the verified RTA matter record for current title, parcel, parties,
  instrument, interests, and supporting evidence;
- versioned deterministic checks and findings;
- guided task definitions, step runs, decisions, and authorised overrides;
- grounded legal search and citation validation over a separate controlled
  legal corpus;
- approved Form 8 template binding and draft snapshots;
- approval gates, DOCX/PDF export manifests, and append-only audit events; and
- API contracts consumed by the Next.js frontend.

### 2.2 Explicit non-goals

V0 does not provide registration filing, autonomous legal advice, historical
title-chain reconstruction, AT-form extraction, reliable automatic acceptance
of handwriting or severely degraded scans, or voice input. Voice dictation and
playback remain conditional V1 work. Any later voice feature must create a
reviewable candidate and cannot silently verify facts, alter prescribed
wording, approve a draft, or bypass audit.

The existing static frontend remains a consumer of mock data until each slice
is connected. The backend must not import frontend code, fixtures, or UI
state. It must not copy private material from the research repository's raw
data directory.

## 3. Tooling and Package Management

### 3.1 Package-manager decision

Use **uv** for the Python backend. `uv` owns `pyproject.toml`, dependency
resolution, `uv.lock`, virtual-environment creation, command execution, and
Python version selection. Use **pnpm** only for the existing Next.js frontend.
The repositories remain separate; this is not a mixed pnpm/uv workspace.

The backend must commit `pyproject.toml` and `uv.lock`. Developers and CI run
Python commands through `uv run`, so the command does not depend on a global
Python installation or an accidentally activated environment.

### 3.2 Initial uv commands

Run these commands from `draftly-platform/backend` when implementation begins:

```powershell
uv python pin 3.12
uv init --package --name draftly-api
uv add fastapi "uvicorn[standard]" pydantic-settings
uv add sqlalchemy "psycopg[binary]" alembic
uv add python-multipart httpx structlog
uv add google-cloud-documentai google-cloud-storage
uv add --dev pytest pytest-asyncio httpx ruff mypy
uv lock
uv run uvicorn draftly_api.main:app --reload
```

The exact Google Cloud packages and authentication library must be confirmed
against the approved deployment and provider assessment before live matter
data is processed. Do not add an SDK merely because a screen has a button for
that capability.

### 3.3 Tooling rules

- `uv run ruff check .` and `uv run ruff format --check .` are required.
- `uv run mypy src` is required for typed application and domain modules.
- `uv run pytest` is required for unit, integration, and contract tests.
- `uv lock --check` is required in CI.
- Secrets are loaded from environment or an approved secret manager, never
  from committed `.env` files.
- Local development may use a disposable PostgreSQL instance and local object
  storage emulator, but production interfaces must remain provider-neutral.

## 4. Target Backend Structure

Create this structure before implementing endpoint logic:

```text
backend/
├─ pyproject.toml
├─ uv.lock
├─ README.md
├─ .env.example
├─ Dockerfile
├─ migrations/
│  ├─ env.py
│  └─ versions/
├─ src/
│  └─ draftly_api/
│     ├─ __init__.py
│     ├─ main.py                 # FastAPI application factory and lifespan
│     ├─ config.py               # typed settings and environment validation
│     ├─ api/
│     │  ├─ deps.py              # request context, auth, DB session
│     │  ├─ errors.py            # safe error mapping
│     │  └─ v1/
│     │     ├─ router.py
│     │     ├─ auth.py
│     │     ├─ billing.py
│     │     ├─ matters.py
│     │     ├─ documents.py
│     │     ├─ particulars.py
│     │     ├─ checks.py
│     │     ├─ tasks.py
│     │     ├─ research.py
│     │     ├─ drafts.py
│     │     ├─ exports.py
│     │     ├─ audit.py
│     │     └─ health.py
│     ├─ application/
│     │  ├─ auth_service.py
│     │  ├─ billing_service.py
│     │  ├─ matter_service.py
│     │  ├─ document_service.py
│     │  ├─ verification_service.py
│     │  ├─ check_service.py
│     │  ├─ task_service.py
│     │  ├─ corpus_governance_service.py
│     │  ├─ library_service.py
│     │  ├─ research_service.py
│     │  ├─ draft_service.py
│     │  ├─ approval_service.py
│     │  └─ export_service.py
│     ├─ domain/
│     │  ├─ enums.py
│     │  ├─ organisations.py
│     │  ├─ billing.py
│     │  ├─ matter.py
│     │  ├─ documents.py
│     │  ├─ evidence.py
│     │  ├─ particulars.py
│     │  ├─ entities.py
│     │  ├─ findings.py
│     │  ├─ tasks.py
│     │  ├─ legal_sources.py
│     │  ├─ drafts.py
│     │  ├─ approvals.py
│     │  ├─ audit.py
│     │  └─ invariants.py
│     ├─ schemas/
│     │  ├─ common.py
│     │  ├─ billing.py
│     │  ├─ matter.py
│     │  ├─ document.py
│     │  ├─ particular.py
│     │  ├─ finding.py
│     │  ├─ research.py
│     │  ├─ draft.py
│     │  ├─ export.py
│     │  └─ audit.py
│     ├─ ports/
│     │  ├─ repositories.py
│     │  ├─ object_storage.py
│     │  ├─ jobs.py
│     │  ├─ document_processing.py
│     │  ├─ legal_retrieval.py
│     │  ├─ legal_catalogue.py
│     │  ├─ identity.py
│     │  ├─ billing.py
│     │  └─ rendering.py
│     ├─ infrastructure/
│     │  ├─ db/
│     │  │  ├─ session.py
│     │  │  ├─ models.py
│     │  │  └─ repositories/
│     │  ├─ storage/
│     │  │  └─ object_store.py
│     │  ├─ queue/
│     │  │  └─ adapter.py
│     │  ├─ document_ai/
│     │  │  └─ google_adapter.py
│     │  ├─ retrieval/
│     │  │  └─ engine_adapter.py
│     │  ├─ identity/
│     │  │  └─ clerk_adapter.py
│     │  ├─ billing/
│     │  │  └─ payhere_adapter.py
│     │  └─ rendering/
│     │     └─ office_renderer.py
│     ├─ workers/
│     │  ├─ runner.py
│     │  ├─ document_jobs.py
│     │  ├─ research_jobs.py
│     │  └─ export_jobs.py
│     └─ observability/
│        ├─ logging.py
│        ├─ metrics.py
│        └─ tracing.py
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  ├─ security/
│  └─ e2e/
└─ scripts/
   ├─ seed_synthetic_matter.py
   └─ rebuild_legal_index.py
```

The folders are boundaries, not a requirement to implement every module on
day one. Empty packages should not be created only for visual completeness;
each added package must have a test or a concrete next implementation task.

## 5. Architecture Rules

### 5.1 Dependency direction

The domain layer contains legal-workflow invariants and does not import
FastAPI, SQLAlchemy, Google SDKs, queue clients, or frontend types. Application
services orchestrate domain operations and ports. Infrastructure implements
ports. API routers translate HTTP requests into application commands and never
make legal decisions themselves.

```text
HTTP/API → application services → domain + ports
                                      ↑
                             infrastructure adapters
```

### 5.2 Trust and data boundaries

The backend must keep these stores and concepts separate:

| Boundary | Rule |
| --- | --- |
| Original evidence | Immutable object version; never overwritten by OCR or correction |
| Derivatives | OCR, layout, quality, previews, and candidate extraction are rebuildable and never authoritative |
| Verified matter record | Only lawyer-verified or lawyer-corrected particulars may feed approved matter outputs |
| Legal corpus | Separate audience-specific releases, indexes, and access paths; confidential matter documents are not public authority |
| Restricted case-law corpus | CommonLII-derived and unreviewed NLR/SLR text may feed internal research retrieval but has no Library source-reader, bulk-download, export, or public-dataset path |
| Draft | Versioned snapshot bound to exact fact and template versions |
| Approval/export | Approval targets one content hash; export records its manifest and checksum |
| Audit | Append-only events for upload, review, correction, override, approval, export, access, and content governance |
| Organisation | Every matter and subscription belongs to one server-verified workspace; cross-organisation access is denied |
| Billing | Provider events are verified and idempotent; role permission and paid entitlement are independent gates |

### 5.3 State invariants

The first domain tests must enforce:

1. Every accepted extracted particular has a source span tied to an immutable
   document version.
2. Corrections create a successor value and preserve the extracted value.
3. Only an authorised lawyer can make a legal verification decision.
4. A final draft references only verified or corrected particular versions.
5. A mandatory blocked task requires new evidence or a recorded authorised
   override.
6. Approved wording can change only through a new approved template version.
7. Replaced documents remain in history but cannot silently feed new output.
8. Every material mutation writes an audit event with actor, target, before or
   after references, reason where required, and correlation ID.
9. No legal source enters a production catalogue or retrieval index without an
   approved provenance record, rights policy, reviewed checksum, and corpus
   release entry.

## 6. Implementation Phases

### Phase 0 — Backend foundation

Create the uv project, lockfile, settings model, application factory, health
route, error envelope, structured logging, test layout, and CI commands.

Exit gate:

- `uv lock --check`, Ruff, mypy, and pytest pass;
- `/health/live` works without a database;
- `/health/ready` reports dependency state without leaking credentials; and
- no frontend or research raw-data files are imported.

### Phase 1 — Contracts and database

Implement Pydantic request/response schemas and domain enums for Organisation,
OrganisationMembership, PlanVersion, PlanEntitlement, Subscription, usage,
Matter, Document, DocumentVersion, SourceSpan, Particular,
ParticularVersion, Party, Parcel, Instrument, Interest, Finding, StepRun,
LegalSource, CorpusReleaseManifest, Draft, Approval, Export, and AuditEvent.
Add SQLAlchemy models, Alembic migrations, optimistic version columns, and
repository interfaces.

Exit gate:

- schemas reject invalid state transitions;
- migrations build an empty database and roll back in a disposable database;
- repository tests prove matter membership isolation; and
- corrections and document replacements preserve history.

### Phase 2 — Authentication, authorisation, and matters

Add Clerk-compatible OIDC identity validation, user and role mapping,
organisation and matter membership, server-side policy checks, safe 404/403
behaviour, and matter CRUD. The browser never supplies a trusted role,
organisation boundary, or unrestricted matter access.

Exit gate:

- a reviewer cannot approve;
- an unauthorised user cannot infer another matter's existence;
- all account, role, assignment, and matter mutations are audited; and
- cross-organisation and cross-matter security tests pass.

### Phase 2B — Organisation billing and entitlements

Add immutable plan versions, organisation subscriptions, feature entitlements,
atomic usage reservations and consumption, PayHere checkout behind
`BillingProviderPort`, verified webhook processing, billing audit/outbox
events, and grace/restricted policy. Payment details remain provider-hosted.

Exit gate:

- a subscription belongs to an organisation, never directly to a user;
- forged checkout-return state cannot grant an entitlement;
- duplicate or out-of-order provider events cannot duplicate or regress state;
- role, organisation, matter, feature, and quota gates are server-enforced;
- payment failure preserves existing legal records and approved exports; and
- cross-organisation billing and usage tests pass.

### Phase 3 — Evidence intake and asynchronous processing

Implement multipart upload validation, checksum calculation, protected object
storage, document versions, job records, authenticated queue messages,
idempotent worker claims, retry/dead-letter behaviour, and processing states.
Add the Google Document AI adapter behind `DocumentProcessingPort`. Record the
processor, version, region, purpose, timing, quality result, and outcome.

Exit gate:

- upload acknowledgement is independent of OCR completion;
- provider failure preserves the original and produces explicit retry/manual
  review state;
- no provider response can set a particular to verified; and
- a typical 15-document test matter reaches review or explicit failure within
  the approved V0 target.

### Phase 4 — Verification and structured matter record

Implement source-span retrieval, candidate review, conflict comparison,
manual particulars, correction history, and the verified RTA matter record.
Expose evidence beside each candidate through matter-scoped URLs or
short-lived authorised access, never public storage paths.

Exit gate:

- every accepted particular opens the correct source document version and
  page/region;
- verified/corrected transitions require the correct role;
- missing or unreadable evidence remains blocked; and
- the structured record can be rebuilt from its persisted versions without
  changing legal decisions.

### Phase 5 — Checks and guided tasks

Implement versioned rule definitions, applicability conditions, deterministic
check execution, findings, missing-document checks, step runs, decisions, and
recorded overrides. Keep generated prose outside the check engine.

Exit gate:

- each active rule has authority metadata, version, effective date, and tests;
- pass, warning, fail, and needs-review remain distinct;
- unresolved blockers prevent approval; and
- lawyer-labelled evaluation reports precision, recall, and abstentions.

### Phase 6 — Grounded research

Implement corpus governance before retrieval. Record source provenance,
rights/licence status, indexing, display, quotation, and download policies;
approve sources into signed audience-specific releases; and expose a catalogue
of approved official statutes, amendments, and gazettes.

Classify the CommonLII-derived and unreviewed NLR/SLR collection for restricted
internal research. It may feed case search, citation graphs, grounded answer
composition, embeddings, and internal evaluation. It must not feed Library
source-text display, bulk downloads, exports, or public datasets. The
curriculum supplies a coverage taxonomy and acquisition priority only; each
source and amendment relationship is independently verified.

Create the legal-catalogue port over the public release and the
legal-retrieval port over the internal research release.
Expose search first, then bounded answer composition with claim-level citation
and source-policy validation. The first integration may wrap approved outputs
from the existing Python retrieval engine through a versioned
package/interface; it must not walk or import arbitrary research paths in
production.

Exit gate:

- every retained claim resolves to a source passage and authority status;
- every source and passage resolves to an approved release entry, reviewed
  checksum, and policy permitting that use;
- unsupported questions abstain;
- CommonLII-derived and unreviewed NLR/SLR text is searchable by the research
  engine but absent from Library source-text and download responses;
- the legal corpus cannot query confidential matter storage; and
- search and answer latency are measured against the V0 targets.

### Phase 7 — Drafting, approval, and export

Implement controlled template versions, fact binding, draft snapshots, locked
wording checks, unresolved-placeholder checks, approval gates, renderer
workers, export manifests, checksums, and expiring download access. Form 8 is
the first active V0 instrument; legal wording remains lawyer-owned.

Exit gate:

- no unverified mandatory fact can reach approval;
- every approved export identifies the exact draft/template/fact versions;
- English and Sinhala output survives reopen validation; and
- any edit after approval creates a new unapproved version.

### Phase 8 — Frontend integration and release hardening

Replace frontend mock accessors slice by slice: Assistant/research first,
then matters and documents, verification, checks, drafts, approval/export,
and audit. Add API contract fixtures, progress polling or authenticated event
updates, accessibility checks, privacy review, backup/restore tests, and
operator runbooks.

Exit gate:

- core V0 user journeys complete through the real API;
- no mock fixture or client-only permission decision remains on production
  paths;
- security, legal-output safety, export, accessibility, and recovery gates
  pass; and
- deployment records application, schema, controlled-content, provider, and
  processor versions.

## 7. Initial API Surface

Use `/api/v1` from the first endpoint. Exact fields come from the Pydantic
schemas and frontend contract review; the following is the initial resource
map:

| Resource | Initial endpoints | State-changing controls |
| --- | --- | --- |
| Auth/session | `GET /me` | Identity provider owns authentication; API derives role and memberships |
| Billing | `GET /billing/plans`, `GET /billing/subscription`, `GET /billing/usage`, `POST /billing/checkout`, `POST /billing/customer-portal`, `POST /billing/cancel`, `POST /billing/reactivate` | Organisation owner/admin policy; server-side plan data; audit changes |
| Billing webhooks | `POST /billing/webhooks/payhere` | Provider checksum/signature, body limit, idempotency, transactional state and outbox |
| Matters | `GET/POST /matters`, `GET/PATCH /matters/{id}` | Membership and role policy; audit create, assignment, archive |
| Documents | `POST /matters/{id}/documents`, `GET /documents/{id}`, `POST /documents/{id}/versions` | Original preservation, checksum, type/size validation, replacement history |
| Processing | `GET /documents/{id}/processing`, `POST /processing/{job}/retry` | Matter-scoped access, idempotent retry, audit outcome |
| Particulars | `GET /matters/{id}/particulars`, `POST /particulars/{id}/verify`, `POST /particulars/{id}/correct` | Lawyer verification policy, source span, optimistic concurrency |
| Findings | `GET /matters/{id}/findings`, `POST /findings/{id}/resolve`, `POST /findings/{id}/override` | Rule version, authority, lawyer reason, audit |
| Tasks | `GET /matters/{id}/tasks`, `POST /tasks/{id}/run`, `POST /tasks/{id}/decision` | Applicability, blocking behaviour, decision role |
| Research | `POST /research/search`, `POST /research/answers/{job}` | Corpus version, citation validation, abstention |
| Drafts | `GET/POST /matters/{id}/drafts`, `POST /drafts/{id}/versions` | Verified fact bindings, locked wording, version hash |
| Approval | `POST /draft-versions/{id}/approve` | Lawyer role, latest hash, blockers, placeholders |
| Exports | `POST /approvals/{id}/exports`, `GET /exports/{id}` | Manifest, checksum, expiry, audit |
| Audit | `GET /matters/{id}/audit` | Read access only; ordinary users cannot edit/delete |
| Health | `GET /health/live`, `GET /health/ready` | No matter data or secret leakage |

Long-running endpoints return a job identifier and current state. They do not
hold an HTTP request open while OCR, retrieval, or rendering runs.

## 8. Frontend Integration Order

Connect the frontend in this order:

1. Shared API client, session identity, and error envelope.
2. Organisation selection, subscription state, plan, and usage surfaces.
3. Matters list, create, assignment, and overview.
4. Document upload, processing status, original/derivative viewer.
5. Candidate particulars, source evidence, verification, correction, and
   conflict comparison.
6. Findings and guided task runs.
7. Legal search and grounded answers with citation chips.
8. Draft snapshots, review, approval, export, and audit history.

Each replacement of a mock accessor must retain loading, empty, blocked,
failure, and permission-denied states. The frontend must not infer that a
successful HTTP response means a fact is legally verified.

## 9. Testing and Quality Gates

### 9.1 Required test layers

- Unit: domain state transitions, policies, normalisation, check rules,
  citation validation, template binding, and export gates.
- Contract: OpenAPI schemas, frontend fixtures, job messages, provider result
  normalisation, and export manifests.
- Integration: PostgreSQL transactions, migrations, object storage, queue
  retries, Document AI adapter, legal index, identity adapter, billing adapter,
  webhook replay, and renderer.
- Security: cross-organisation and cross-matter isolation, role escalation,
  forged entitlements, invalid billing webhooks, upload validation, signed URL
  expiry, CSRF/CORS policy, secret/log inspection, and approval bypass.
- End-to-end: the complete V0 path from matter creation to approved export.
- Domain evaluation: lawyer-labelled extraction, provenance, checks, citation
  support, draft correctness, abstentions, and disagreements.

### 9.2 Release-blocking failures

The backend cannot be accepted if it permits an invented citation, unsupported
retained legal claim, cross-matter disclosure, silent original loss, mandatory
unverified fact in an approved export, altered locked wording, hidden
placeholder, missing audit event, approval attached to changed content, or a
legal source crossing its approved audience, indexing, quotation, display, or
download boundary.

## 10. Operational Requirements

- Use separate development, evaluation, and demonstration data.
- Keep real client data out of fixtures, logs, traces, screenshots, and error
  reports.
- Record application, migration, controlled-content, identity, billing,
  processor, and renderer versions for each evaluation and export.
- Provide retry, dead-letter, manual-review, and operator reprocessing paths.
- Add database and object-storage backup/restore procedures before lawyer
  testing.
- Keep original evidence, derivatives, and exports in separate storage
  prefixes and retention policies.
- Document Google Document AI region, retention, deletion, training-use,
  quota, cost, and exit controls before live processing.
- Document payment-provider onboarding, settlement, webhook reconciliation,
  refund, grace, restriction, and billing-data retention procedures before
  charging a customer.

## 11. Deliverables

The V0 backend implementation is complete only when these are present:

1. `pyproject.toml` and committed `uv.lock`.
2. The structured `src/draftly_api` package and migration history.
3. Versioned OpenAPI output and frontend contract fixtures.
4. Working organisation, billing, matter, document, verification, checks,
   corpus-governance, library, research, drafting, approval, export, audit, and
   health endpoints.
5. Authenticated workers for document, research, and export jobs.
6. Synthetic seed data and reproducible local setup.
7. Unit, integration, contract, security, domain, and end-to-end tests.
8. Deployment configuration, backup/restore runbook, and operator notes.
9. Evidence for every V0 acceptance gate, including abstentions and explicit
   failures.

## 12. Decisions Requiring Approval

- The exact Python package boundary for the existing retrieval engine.
- The written production source policy and legal review for official texts,
  historical reports, NLR/SLR, and any licensed third-party corpus.
- PostgreSQL and object-storage deployment choices for the reference
  environment.
- Queue technology and worker runtime.
- Clerk environment and account, organisation, and matter role mapping.
- PayHere business onboarding, settlement account, plan prices, currencies,
  allowances, taxes, refunds, grace period, and restricted-mode policy.
- Google Document AI processor version, region, and approved document classes.
- Form 8 schema, wording, legal rules, and template approval.
- Retention, deletion, backup, and external-processing policy.
- Numerical holdout thresholds and lawyer-review ownership.

Until these decisions are approved, adapters may use local test doubles, but
the domain contracts and safety gates must remain real.
