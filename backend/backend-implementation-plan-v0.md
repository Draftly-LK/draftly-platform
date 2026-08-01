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

### 1.1 Relationship to the service designs

Per-service implementation detail lives in `backend/docs/services/`, indexed by
[`docs/services/README.md`](docs/services/README.md). Rules that apply to every
service were extracted out of the individual docs and live in five
cross-cutting files, which this plan defers to rather than restating:

| Document | Holds |
| --- | --- |
| [`docs/security-model.md`](docs/security-model.md) | Organisation boundary, capability catalogue, role map, 404-not-403 |
| [`docs/api-conventions.md`](docs/api-conventions.md) | Paths, pagination, concurrency, idempotency, errors, job envelopes |
| [`docs/events.md`](docs/events.md) | Every domain event: name, payload, publisher, consumers |
| [`docs/jobs-and-workers.md`](docs/jobs-and-workers.md) | Outbox, claim protocol, retries, scheduled jobs |
| [`docs/service-definition-of-done.md`](docs/service-definition-of-done.md) | How a service is judged finished, and the conformance suite |

Where this plan and a service doc disagree on detail, the service doc is more
current. Where a service doc and one of the five cross-cutting files disagree,
the cross-cutting file wins.

## 2. Scope and Boundary

### 2.1 V0 backend scope

The V0 backend shall provide:

- authenticated users, organisation workspaces, roles, capability-based
  authorisation, and matter membership checks;
- organisation-owned subscriptions, plan entitlements, usage quotas, and
  provider-neutral recurring billing;
- matter creation, assignment, lifecycle, and privacy-safe references;
- a protected party tier holding identity evidence, beneficial ownership, CDD,
  and screening outcomes;
- the notarial register: attestation records, protocol custody, Form F entries,
  and monthly returns;
- dated obligations driven by governed deadline rules, with lawyer confirmation;
- notification preferences, templates, and delivery;
- retention policies, legal holds, and an approval-gated disposition path;
- non-authoritative per-matter session memory;
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
title-chain reconstruction, AT-form extraction, or reliable automatic acceptance
of handwriting or severely degraded scans.

**Voice is schedule-gated rather than a non-goal.** Its design, guardrails, and
contracts are settled in [`docs/services/voice-service.md`](docs/services/voice-service.md);
it ships in V0 if the schedule allows and otherwise in V1. Either way a voice
feature creates a reviewable candidate and cannot silently verify facts, alter
prescribed wording, approve a draft, or bypass audit. Nothing else may depend on
it, and `memory_service` treats its events as a conditional contract.

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
│     │  ├─ party_service.py
│     │  ├─ document_service.py
│     │  ├─ verification_service.py
│     │  ├─ check_service.py
│     │  ├─ task_service.py
│     │  ├─ obligations_service.py
│     │  ├─ notarial_register_service.py
│     │  ├─ content_governance_service.py
│     │  ├─ corpus_governance_service.py
│     │  ├─ library_service.py
│     │  ├─ research_service.py
│     │  ├─ memory_service.py
│     │  ├─ draft_service.py
│     │  ├─ approval_service.py
│     │  ├─ export_service.py
│     │  ├─ notification_service.py
│     │  ├─ voice_service.py
│     │  ├─ retention_service.py
│     │  └─ audit_service.py
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
│     │  ├─ events.py
│     │  ├─ audit.py
│     │  ├─ clock.py
│     │  ├─ document_processing.py
│     │  ├─ legal_retrieval.py
│     │  ├─ legal_catalogue.py
│     │  ├─ session_memory.py
│     │  ├─ identity.py
│     │  ├─ billing.py
│     │  ├─ email.py
│     │  ├─ transcription.py
│     │  ├─ screening.py
│     │  ├─ destruction.py
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
│     │  ├─ runner.py                # also the leader-elected scheduler mode
│     │  ├─ document_jobs.py
│     │  ├─ research_jobs.py
│     │  ├─ export_jobs.py
│     │  ├─ notification_jobs.py
│     │  ├─ obligation_reminder_jobs.py
│     │  ├─ memory_jobs.py
│     │  ├─ corpus_jobs.py
│     │  └─ voice_jobs.py
│     └─ observability/
│        ├─ logging.py
│        ├─ metrics.py
│        └─ tracing.py
├─ contracts/
│  ├─ openapi.v1.json
│  └─ services.yaml               # the registry the conformance suite reads
├─ email-templates/               # separate pnpm project, React Email
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ conformance/                # cross-service, parameterised over services.yaml
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
10. Every row belonging to a customer carries an organisation id, and every
    query filters on it before any other check.
11. A record under an active legal hold cannot be destroyed, merged, expired, or
    collected by any sweep.
12. Every state in a lifecycle has exactly one owning service that can enter it.
    No state may be reachable only from a service that refuses to enter it.

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

### Phase 3B — Protected party tier

Implement `party_service`: party records, encrypted identity evidence pinned to
immutable document versions, beneficial ownership, CDD assessments against a
pinned policy version, and screening results at `restricted-compliance`. Reading
a full identifier is a capability-gated, purpose-recorded, audited read.

Exit gate:

- no plaintext identifier appears in a dump of the party tables;
- a list response never returns a full identifier;
- identity evidence cannot reach `verified` without a pinned document version;
- screening detail is invisible to an ordinary matter member, with no existence
  signal; and
- no automatic identity merge occurs on a name match.

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

### Phase 5B — Register, obligations, and notifications

Implement `notarial_register_service` (attestation, gapless per-notary register
serials, protocol custody, monthly return periods, registration lifecycle),
`obligations_service` over governed deadline rules, and `notification_service`
with the console adapter, then Resend.

This phase exists because Phase 5 as originally written had nowhere to record an
attestation, which left the monthly return and the registration deadline — two
of the ten V0 obligations — with no input.

Exit gate:

- register serials are gapless per notary and year, and a cancelled entry
  retains its serial;
- attestation requires an approved and exported instrument, a current practice
  certificate, and identity-verified executants;
- practising jurisdiction is snapshotted at attestation;
- each of the deed 30-day, deed 60-day, and RTA seven-working-day branches
  resolves correctly on fixtures, and an unknown regime produces no
  authoritative deadline;
- a nil month still produces a return period and an obligation;
- no hard legal deadline becomes authoritative without lawyer confirmation; and
- a delivery failure never mutates an obligation, and each channel sends at most
  once.

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

- a draft travels create → submit → approve → export end to end, and no state in
  that chain is reachable only from a service that refuses to enter it;
- no unverified mandatory fact can reach approval;
- every approved export identifies the exact draft/template/fact versions;
- English and Sinhala output survives reopen validation;
- superseding a bound fact's source document invalidates the approval and stops
  a queued render; and
- any edit after approval creates a new unapproved version.

### Phase 7B — Retention and legal hold

Implement `retention_service`: governed retention policies, scope-based legal
holds, schedule evaluation, the approval-gated disposition path, tombstones, and
the `DestructionCommandPort` each owning service implements.

Exit gate:

- nothing is destroyed by a timer; maturity creates a human review obligation;
- a hold blocks disposition at both approval and execution, and blocks the
  orphan-blob sweep and party merge;
- a tombstone is written before any bytes are removed, and tombstones survive;
- a partial destruction failure never reports `destroyed`; and
- a restore followed by tombstone reconciliation detects reinstated records.

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
| Matters | `GET/POST /matters`, `GET/PATCH /matters/{id}`, lifecycle commands | Membership and role policy; audit create, assignment, archive |
| Parties | `GET/POST /parties`, `GET/PATCH /parties/{id}`, `POST /parties/{id}/identity-evidence`, `/cdd`, `/screening` | Capability plus recorded purpose to read an identifier; screening restricted |
| Documents | `GET/POST /matters/{id}/documents`, `GET /documents/{id}`, `POST /documents/{id}/versions`, `GET /document-versions/{id}/manifest` | Original preservation, checksum, type/size validation, replacement history |
| Processing | `GET /documents/{id}/processing`, `POST /processing/{job}/retry` | Matter-scoped access, idempotent retry, audit outcome |
| Particulars | `GET /matters/{id}/facts`, `POST /matters/{id}/facts/{id}/verify`, `/correct` | Lawyer verification policy, source span, optimistic concurrency |
| Findings | `GET /matters/{id}/checks`, `/cross-checks`, `POST …/{id}/resolve`, `/remediation` | Rule version, authority, lawyer reason, audit |
| Tasks | `GET/POST /matters/{id}/workflows`, `POST …/steps/{id}/complete`, `/document-requirements`, `/readiness` | Applicability, blocking behaviour, decision role |
| Obligations | `GET/POST /obligations`, `POST /obligations/{id}/confirm`, `/complete`, `/cancel` | Approved rule, lawyer confirmation, restricted visibility |
| Register | `POST /matters/{id}/attestations`, `POST /attestations/{id}/*`, `GET /register/*` | Practising notary, approved instrument, gapless serial |
| Governed content | `GET/POST /templates`, `/questions`, `/question-sets`, `/workflow-definitions`, `/deadline-rules`, `/check-rules`, `/retention-policies` plus `versions`/`approve`/`retire` | Maintainer gate; approved-only reads for matter work |
| Research | `POST /assistant/conversations/{id}/messages`, `GET /assistant/jobs/{id}/events`, `GET /assistant/answers` | Corpus version, citation validation, abstention |
| Library | `GET /library`, `GET /library/{id}` | Policy-filtered representation; public release only |
| Memory | `GET /matters/{id}/memory/context`, `/memory/search` | Read-only, non-authoritative, matter-scoped |
| Drafts | `GET/POST /matters/{id}/drafts`, `POST …/versions`, `/restore`, `/submit`, `/withdraw` | Verified fact bindings, locked wording, version hash |
| Approval | `POST /matters/{id}/drafts/{id}/approve` | Approver capability, practising notary, submitted hash, blockers, placeholders |
| Exports | `POST /matters/{id}/drafts/{id}/exports`, `POST /reports`, `GET /exports/{id}` | Manifest, checksum, expiry, audit |
| Voice | `POST /transcriptions/sessions`, `POST /transcriptions/{id}/finalise`, `/revisions`, `/confirm` | Candidate only; no downstream action |
| Retention | `GET/POST /retention/policies`, `/holds`, `/dispositions/{id}/approve` | Hold beats policy; destruction needs approval |
| Notifications | `GET/PATCH /notification-preferences`, `GET /notifications` | Own records only; no arbitrary recipient |
| Audit | `GET /matters/{id}/audit`, `GET /history` | Read access only; ordinary users cannot edit/delete |
| Jobs | `GET /jobs/{jobId}` | Uniform job envelope for every long-running operation |
| Health | `GET /health/live`, `GET /health/ready` | No matter data or secret leakage |

Long-running endpoints return a job identifier and current state. They do not
hold an HTTP request open while OCR, retrieval, rendering, or transcription
runs.

Pagination, optimistic concurrency, idempotency keys, the error envelope, and
the 404-not-403 rule are uniform across every row above and are specified in
[`docs/api-conventions.md`](docs/api-conventions.md) rather than per resource.

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
- Contract: OpenAPI schemas, frontend fixtures, job messages, event payloads,
  provider result normalisation, and export manifests.
- **Conformance: the cross-service suite in
  [`docs/service-definition-of-done.md`](docs/service-definition-of-done.md) §4,
  parameterised over `contracts/services.yaml` — tenancy, audit coverage, event
  registry parity, API conventions, job contract, metering, and privacy. A new
  service is covered the day it is registered.**
- Integration: PostgreSQL transactions, migrations, object storage, queue
  retries, Document AI adapter, legal index, identity adapter, billing adapter,
  webhook replay, and renderer.
- Security: cross-organisation and cross-matter isolation, capability
  escalation, forged entitlements, invalid billing webhooks, upload validation,
  signed URL expiry, CSRF/CORS policy, secret and log inspection, and approval
  bypass.
- End-to-end: the complete V0 path from matter creation to approved export,
  including the submit step.
- Domain evaluation: lawyer-labelled extraction, provenance, checks, citation
  support, draft correctness, abstentions, and disagreements.

A service is judged finished by the five-level ladder in
`service-definition-of-done.md`, not by whether its endpoints respond.

### 9.2 Release-blocking failures

The backend cannot be accepted if it permits an invented citation, unsupported
retained legal claim, cross-matter or cross-organisation disclosure, silent
original loss, mandatory unverified fact in an approved export, altered locked
wording, hidden placeholder, missing audit event, approval attached to changed
content, destruction of a record under a legal hold, or a legal source crossing
its approved audience, indexing, quotation, display, or download boundary.

Each blocker maps to a named test in `service-definition-of-done.md` §7. Those
tests run on every pull request and every merge, and are never skipped, marked
`xfail`, or quarantined.

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

Items marked **[closed]** were resolved by the service designs and the
cross-cutting documents; they are kept here for the record.

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
- Retention periods per record class, and the erasure-assessment policy. The
  mechanism is **[closed]** in `retention_service`; the periods are a legal
  review item and the service ships with an empty approved-policy set.
- Numerical holdout thresholds and lawyer-review ownership.
- Whether a drafting lawyer may approve their own draft, and whether four-eyes
  approval is configurable per organisation.
- Voice ship date — V0 or V1. The design is **[closed]**; only the schedule is
  open.
- Screening provider, or manual-entry adapter, for sanctions and PEP checks.

**[closed]** by the service designs: queue technology for V0 (PostgreSQL outbox
with `SKIP LOCKED`, swappable behind `JobQueuePort`); the identity provider
(Clerk); the payment provider adapter (PayHere); the capability catalogue and
role map; the event registry and naming rule; API conventions; and the
definition of done.

Until these decisions are approved, adapters may use local test doubles, but
the domain contracts and safety gates must remain real.
