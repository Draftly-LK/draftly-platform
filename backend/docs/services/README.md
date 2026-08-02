# Backend service catalogue

One design document per service. This file is the index: what exists, who owns
what, which endpoint reaches which service, and how far along each one is.

Read these four first — they hold the rules the service docs stopped repeating:

| Document | Holds |
| --- | --- |
| [`../security-model.md`](../security-model.md) | Organisation boundary, capability catalogue, role map, 404-not-403 |
| [`../api-conventions.md`](../api-conventions.md) | Paths, pagination, concurrency, idempotency, errors, jobs |
| [`../events.md`](../events.md) | Every domain event: name, payload, publisher, consumers |
| [`../jobs-and-workers.md`](../jobs-and-workers.md) | Outbox, claim protocol, retries, scheduled jobs |

Then:
[`../infrastructure.md`](../infrastructure.md) for datastores and deployment,
[`../service-definition-of-done.md`](../service-definition-of-done.md) for how a
service is judged finished, and
[`../frontend-contract-migration.md`](../frontend-contract-migration.md) for
every breaking change to the frontend types.

## 1. How to read a service doc

Every doc follows the same shape: what it owns and does not own, where it sits,
domain models, ports, methods, entitlement and metering where relevant,
invariants, failure modes, tests, and decisions. When a doc and one of the four
cross-cutting files disagree, the cross-cutting file wins and the doc is wrong.

Implementation is a modular monolith organised under
`src/modules/<owner>/`. Older diagrams use horizontal shorthand
such as `application/document_service.py`, `domain/documents.py`, `ports/`, or
`workers/document_jobs.py`; resolve each path inside its owning module according
to `backend-implementation-plan-v0.md` §4. Only technical shared-kernel code
belongs under `platform/`.

## 2. The services

Status levels are defined in `service-definition-of-done.md` §1. The machine
readable form of this table is `backend/contracts/services.yaml`; a CI check
fails if the two drift.

One row here has no registry entry: **document-processing** is the worker
pipeline behind `DocumentProcessingPort`, not a separate application service. It
is registered as part of `document_service`, and its own doc exists because the
OCR escalation ladder is large enough to need one.

| Service | Owns | Plan phase | Status |
| --- | --- | --- | --- |
| [auth-service](auth-service.md) | Identity, roles, organisation and matter membership, capability checks | 2 | L0 |
| [billing-service](billing-service.md) | Plans, subscriptions, entitlements, usage, PayHere webhooks | 2B | L0 |
| [matter-service](matter-service.md) | Matter identity, classification, lifecycle, party references | 2 | L0 |
| [party-service](party-service.md) | Party records, identity evidence, beneficial ownership, CDD, screening | 2 | L0 |
| [document-service](document-service.md) | Immutable upload, versioning, processing state, viewer manifest | 3 | L0 |
| [storage-service](storage-service.md) | Provider-neutral blob metadata, immutable operations, signed grants, reconciliation | 3 | L0 |
| [document-processing](document-processing.md) | Worker pipeline: rasterise, classify, OCR ladder, extract | 3 | L0 |
| [verification-service](verification-service.md) | The verified fact tier — verify, correct, conflicts, evidence spans | 4 | L0 |
| [check-service](check-service.md) | Deterministic rules, findings, cross-document reconciliation | 5 | L0 |
| [task-service](task-service.md) | Workflow compilation, step runs, document requirements, question responses, readiness | 5 | L0 |
| [obligations-service](obligations-service.md) | Dated deadlines and commitments, governed deadline rules, reminders | 5 | L0 |
| [notarial-register-service](notarial-register-service.md) | Attestations, protocol, Form F register, monthly returns, registration lifecycle | 5 | L0 |
| [content-governance-service](content-governance-service.md) | Seven governed content families and their approval lifecycle | 5, 7 | L0 |
| [corpus-governance-service](corpus-governance-service.md) | Legal source provenance, rights policy, audience releases, quarantine | 6 | L0 |
| [library-service](library-service.md) | Read-only browse of the approved public catalogue | 6 | L0 |
| [research-service](research-service.md) | Grounded answers, citation validation, abstention, assistant conversations | 6 | L0 |
| [memory-service](memory-service.md) | Non-authoritative per-matter session memory | 6 | L0 |
| [draft-service](draft-service.md) | Draft creation, versioning, restore, submit for review | 7 | L0 |
| [approval-service](approval-service.md) | The approval gate, content-hash pinning, invalidation | 7 | L0 |
| [export-service](export-service.md) | Rendering approved instruments and supporting documents, manifests | 7 | L0 |
| [notification-service](notification-service.md) | Preferences, templates, delivery, retries, provider webhooks | 5 | L0 |
| [voice-service](voice-service.md) | Live transcription, candidate transcripts, review and confirmation | V0/V1 by schedule | L0 |
| [retention-service](retention-service.md) | Retention policies, legal holds, disposition, tombstones | 8 | L0 |
| [audit-service](audit-service.md) | The append-only, hash-chained event log and its read surface | all | L0 |

## 3. Ownership at a glance

The question these docs get asked most often is "which service owns X".

| Concept | Owner | Not |
| --- | --- | --- |
| Who is using Draftly | `auth_service` | `party_service` |
| Who the matter is about | `party_service` | `matter_service`, `auth_service` |
| What a document says about a person | `verification_service` | `party_service` |
| Matter and organisation membership rows | `auth_service` | `matter_service` |
| Transaction role of a party in a matter | `matter_service` | `party_service` |
| Logical documents and versions | `document_service` | `storage_service`, `notarial_register_service` |
| Stored bytes, provider references, and upload reservations | `storage_service` | `document_service`, `export_service` |
| OCR, classification, extraction | `document-processing` worker | `document_service` |
| Candidate particulars | `document-processing` → `verification_service` | anyone else |
| Verified facts | `verification_service` | `check_service`, `task_service` |
| Rule definitions | `content_governance_service` | `check_service` |
| Rule evaluation and findings | `check_service` | `task_service` |
| Remediation work for a finding | `task_service` | `check_service` |
| Workflow definitions and modules | `content_governance_service` | `task_service` |
| Workflow runs and step state | `task_service` | `matter_service` |
| Question sets | `content_governance_service` | `task_service` |
| Question answers | `task_service` | `content_governance_service` |
| Deadline rules | `content_governance_service` | `obligations_service` |
| Deadline calculation and occurrences | `obligations_service` | `task_service` |
| Retention policies | `content_governance_service` | `retention_service` |
| Holds, schedules, destruction | `retention_service` | `obligations_service` |
| Attestation, protocol, register | `notarial_register_service` | `document_service`, `task_service` |
| Draft text and versions | `draft_service` | `content_governance_service` |
| `working ⇄ in-review` | `draft_service` | `approval_service` |
| `in-review → approved` | `approval_service` | `draft_service` |
| `approved → exported` | `export_service` | `approval_service` |
| Form templates and prescribed wording | `content_governance_service` | `draft_service` |
| Rendering anything to DOCX or PDF | `export_service` | `content_governance_service` |
| Legal source rights and releases | `corpus_governance_service` | `library_service`, `research_service` |
| Public catalogue reads | `library_service` | `research_service` |
| Grounded answers | `research_service` | `library_service`, `memory_service` |
| Session working memory | `memory_service` | `verification_service` |
| Email templates and delivery | `notification_service` | `content_governance_service` |
| Authentication email | Clerk | `notification_service` |
| Plans, quotas, payment state | `billing_service` | `auth_service` |
| The audit log | `audit_service` | everyone writes, nobody else owns |

## 4. Endpoint map

Every path is under `/api/v1` (`api-conventions.md` §1).

| Service | Routes |
| --- | --- |
| auth | `GET /me` |
| billing | `GET /billing/plans`, `/subscription`, `/usage`; `POST /billing/checkout`, `/customer-portal`, `/cancel`, `/reactivate`, `/webhooks/payhere` |
| matter | `GET`, `POST /matters`; `GET`, `PATCH /matters/{id}`; `POST /matters/{id}/activate`, `/reclassify`, `/close`, `/reopen`, `/archive` |
| party | `GET`, `POST /parties`; `GET`, `PATCH /parties/{id}`; `POST /parties/{id}/identity-evidence`, `/beneficial-owners`, `/cdd`, `/screening`; `GET /matters/{id}/parties` |
| document | `GET`, `POST /matters/{id}/documents`; `GET /documents/{id}`; `POST /documents/{id}/versions`; `GET /documents/{id}/processing`; `GET /document-versions/{id}/manifest`; `POST /processing/{job}/retry` |
| storage | No public routes; called through `ObjectStoragePort` after the owning service authorizes access |
| verification | `GET`, `POST /matters/{id}/facts`; `POST /matters/{id}/facts/{factId}/verify`, `/correct` |
| check | `GET /matters/{id}/checks`, `/cross-checks`; `POST /matters/{id}/checks/{id}/resolve`, `/remediation` |
| task | `GET`, `POST /matters/{id}/workflows`; `POST …/re-evaluate`; `POST …/steps/{id}/complete`; `GET`, `POST /matters/{id}/document-requirements`; `GET /matters/{id}/readiness`; question responses |
| obligations | `GET`, `POST /obligations`; `POST /obligations/{id}/confirm`, `/complete`, `/cancel`; `GET /obligation-rules` |
| notarial-register | `POST /matters/{id}/attestations`; `POST /attestations/{id}/protocol`, `/registration-submission`, `/registration-acknowledgement`, `/collection`; `GET /register/entries`, `/periods`; `POST /register/periods/{id}/certify` |
| content-governance | `GET`, `POST /templates`, `/questions`, `/question-sets`, `/workflow-definitions`, `/deadline-rules`, `/check-rules`, `/retention-policies`, each with `versions`, `approve`, `retire` |
| library | `GET /library`, `GET /library/{id}` |
| research | `GET`, `POST /assistant/conversations`; `GET`, `POST …/messages`; `GET /assistant/jobs/{id}/events`; `POST /assistant/messages/{id}/branch`; `POST /assistant/actions`; `GET /assistant/answers` |
| memory | `GET /matters/{id}/memory/context`, `/memory/search` |
| draft | `GET`, `POST /matters/{id}/drafts`; `POST …/versions`, `/restore`, `/submit`, `/withdraw` |
| approval | `POST /matters/{id}/drafts/{id}/approve`; `GET …/approval` |
| export | `POST /matters/{id}/drafts/{id}/exports`; `POST /reports`; `GET /exports/{id}` |
| voice | `POST /transcriptions/sessions`; `POST /transcriptions/{id}/finalise`, `/revisions`, `/confirm`; `GET /transcriptions/{id}` |
| retention | `GET /retention/policies`, `/schedules`, `/holds`, `/erasure-requests`; `POST /retention/policies`, `/holds`, `/holds/{id}/release`, `/dispositions/{id}/approve` |
| notification | `GET`, `PATCH /notification-preferences`; `GET /notifications`; `POST /notifications/{id}/read` |
| audit | `GET /matters/{id}/audit`; `GET /history` |
| platform | `GET /jobs/{jobId}`; `GET /health/live`, `/health/ready` |

## 5. Where the corpus boundary sits

Three tiers, three access paths, deliberately not interchangeable
(`corpus-governance-service.md` §1):

```text
public-catalogue release       → library_service  (LegalCataloguePort)
internal-research release      → research_service (LegalRetrievalPort)
confidential matter storage    → matter-scoped services only
```

No port crosses a tier. The library cannot reach restricted case law, and
neither corpus port can reach matter storage.

## 6. Known open items across the set

Tracked here so they are not rediscovered per doc.

| Item | Owner | Blocking |
| --- | --- | --- |
| Prescribed wording for RTA forms, Form E, Form F | Conveyancing lawyer | Approval of any `FormTemplate`; submittable returns |
| Deadline rule approval (annual certificate, monthly return, 30/60-day, RTA 7-working-day) | Legal review | Authoritative deadlines |
| Retention periods per record class | Legal review | Any disposition; `retention_service` ships with an empty policy set |
| Written Sri Lankan IP review for NLR/SLR/CommonLII | Legal review | Broadening case law beyond restricted research |
| Document AI and Gemini region, retention, training-use terms | Ops + legal | Processing any real client bundle |
| PayHere onboarding, prices, grace policy | Product | Charging a customer |
| Retrieval-engine package boundary | Engineering | `LegalRetrievalPort` implementation |
| Voice ship date (V0 or V1) | Schedule | Nothing — the design is settled either way |
| Four-eyes approval policy per organisation | Product | Self-approval behaviour in a solo organisation |
