# document_service — implementation design

## Canonical fact register contract (2026-10-09)

Intake recognition uses `content_governance.contracts.DOCUMENT_CLASSES` before
any transaction subtype, form or checklist exists. The document adapter offers
the governed catalogue and builds schemas only for definitions with an existing
extraction template and governed fact keys: NIC, title certificate, survey plan
and Form 8. Other classes remain recognizable without invented extraction
fields. An unidentified page remains an explicit manual-review outcome. This
read creates no checklist, chooses no subtype and accepts no requirement; the
owning ingestion service still checks source/matter access and provider gates.

`document.contracts.DocumentFactPort` exposes bounded candidate observations and
validates source evidence for verification-owned decisions. Processing rows and
source bytes remain document-owned and immutable through human review. Validation
checks owner/matter, pinned SHA-256, source/candidate state, page bounds, current
document class/group relationship and readable artifacts. It returns page OCR
and an exact supporting text span only when that substring exists in actual OCR;
page-level fallback never manufactures a bounding box.

Extraction grouping validation compares every source/page pair with the
processing logical document. Regrouping to include another source invalidates
an old single-source extraction, even when its original pages still match.
Existing facts citing distinct sources retain every evidence reference, and
verification revalidates each before acceptance/correction. This does not create
new extraction runs or propagate lifecycle invalidation.

The pinned original and corrected page artifact must remain readable. Storage
not-found, integrity and availability failures for those required artifacts
become a blocked evidence result; the register retains that candidate as
unavailable alongside healthy rows. OCR text is optional: if it cannot be read,
the validator returns empty text, no supporting span and page precision while
allowing human page review. No replacement bytes or OCR content are invented.

The legacy document review edit/approval surface now delegates to canonical
verification commands. Edits persist unverified successors; acceptance requires
explicit matter scope, evidence review, capability and practising authorization.
The document review read overlays canonical value/status/version while retaining
the original machine candidate. A generic NIC identifies its holder, not a
transferee. Legacy `transfereeNic` observations from NIC sources read as `holderNic`;
the prescribed Form 8 key is unchanged. Holder name (English/Sinhala), birth date,
address and surveyor registration observations are retained in the register.

Interpretation generation/refresh and dependent invalidation remain Task 4.
It must invoke verification's public `FactEvidenceInvalidationPort` in the same
transaction and honor the matter scope lock used by review commands.

Companion to `backend/backend-implementation-plan-v0.md`. One markdown per
service under `backend/docs/services/`. This is the first.

Maps to plan **Phase 3** (evidence intake and asynchronous processing), API
rows **Documents** and **Processing** (§7), and the trust-boundary rows
*Original evidence* and *Derivatives* (§5.2).

## 1. What it owns

Turning an uploaded file into an **immutable, checksummed, matter-scoped
document version** and starting asynchronous processing — without ever blocking
on OCR and without letting a machine result promote itself to fact. It owns the
write path for evidence and the read path for document metadata and processing
state.

It does **not** run OCR (a worker does), does **not** verify particulars
(`verification_service` does), does **not** decide extraction correctness, and
does **not** decide whether a workflow document requirement is accepted
(`task_service` does). It produces derivatives marked non-authoritative and
hands off.

## 2. Where it sits

```text
GET  /api/v1/matters/{id}/documents        ─┐  (paginated list)
POST /api/v1/matters/{id}/documents         │
POST /api/v1/documents/{id}/versions        ┼─→ api/v1/documents.py
GET  /api/v1/documents/{id}                 │        │
GET  /api/v1/documents/{id}/processing      │        ▼
GET  /api/v1/document-versions/{id}/manifest│  application/document_service.py
POST /api/v1/processing/{job}/retry        ─┘        │ orchestrates
                                                     ▼
                    ports: DocumentRepository, ObjectStoragePort,
                           JobQueuePort, BillingEntitlementPort,
                           EventPort, AuditPort
                    (DocumentProcessingPort is used by the WORKER)
```

The list route was missing from this document even though the frontend already
calls it (`GET /api/matters/{id}/documents`). It is paginated like every other
list (`api-conventions.md` §2).

The router does authentication and parsing only. The service takes an
already-authenticated `RequestContext` (actor, roles, matter memberships) and
orchestrates domain plus ports. Infrastructure implements the ports. The
service imports no SQLAlchemy, no Google SDK, no FastAPI.

## 3. Domain models it needs

In `domain/documents.py` and `domain/evidence.py`:

- **Document** — the logical document in a matter: `id`, `matter_id`,
  `doc_class` (unknown until classified), `current_version_id`, timestamps. No
  file bytes.
- **DocumentVersion** — one immutable uploaded file: `id`, `document_id`,
  `checksum` (SHA-256), `size`, `mime`, `storage_key`, `uploaded_by`,
  `uploaded_at`, `supersedes_version_id`. Never mutated after creation.
- **ProcessingRun** — one processing attempt against one version: `id`,
  `version_id`, `state`, `attempt`, `provider`, `processor_version`, `region`,
  `purpose`, `started_at`, `finished_at`, `quality_result`, `outcome`,
  `correlation_id`. Plan Phase 3 requires every one of those provider fields
  recorded.
- **Derivative** — OCR text, layout, quality, or preview, keyed to a
  `ProcessingRun`. Rebuildable, never authoritative (§5.2).
- **ViewerManifest** — a read projection for one immutable `DocumentVersion`:
  original-file checksum and short-lived URL, page count, page dimensions,
  available page-image and thumbnail derivatives, text-layer availability,
  coordinate-space version, and processing state. It contains no verification
  decision.

Two small state machines, both enforced in the domain layer so the first tests
can hit them without a database:

```text
DocumentVersion:  uploaded → queued → processing → processed
                                    ↘ failed ↘ manual_review
ProcessingRun:    pending → running → succeeded
                                    ↘ failed → (retry) → dead_letter
```

An illegal transition raises a domain error, not an HTTP error.

## 4. Ports it depends on

In `ports/`:

- `DocumentRepository` — persist and load Document, DocumentVersion, and
  ProcessingRun; matter-scoped queries only.
- `ObjectStoragePort` — the provider-neutral facade owned by
  `storage_service`; `put_immutable(scope, owner, stream, metadata)` and
  `issue_download_grant(stored_ref, purpose, ttl)`. The put must fail if the
  trusted key already exists, and the returned reference pins the provider
  generation.
- `JobQueuePort` — `enqueue(ProcessingMessage)` with an authenticated, signed
  message body.
- `AuditPort` — `record(event)`; every mutation goes through here.

## 5. The methods

### upload_document(ctx, matter_id, upload) -> DocumentRead

1. Re-check matter membership from the repository; do not trust the router.
2. Validate the mime allowlist and size cap early, and reject a zero-byte file,
   before touching storage.
3. Stream to a temporary location, computing SHA-256 as you stream. Do not
   buffer the whole file in memory.
4. Store the original with `put_immutable` at a non-public, matter-scoped key:
   `matters/{matter_id}/docs/{doc_id}/v/{version_id}/original`.
5. Persist Document and DocumentVersion (`state=uploaded`) **and** an outbox row
   for the queue message in one database transaction.
6. After commit, the outbox drains to `JobQueuePort` (`state=queued`). This
   ordering is the crux: never enqueue a job for a version the database does not
   have, and never lose a job if enqueue fails — an outbox sweeper reconciles.
7. Audit `document.uploaded`.
8. Return immediately. The response says received and queued, never processed.
   This is the Phase 3 exit gate: upload acknowledgement is independent of OCR
   completion.

### add_version(ctx, document_id, upload) -> DocumentVersionRead

Replacement. Same as upload, but the new DocumentVersion sets
`supersedes_version_id` to the current one. The old version stays in storage and
history (invariant 7). The service emits `document.version-superseded` so
`verification_service` can flag any particulars sourced from the old version as
stale — `document_service` does not reach into verified facts itself; that is
the seam. Enqueue processing for the new version. Audit `document.replaced`.

### get_document(ctx, document_id) -> DocumentRead

Matter-scoped. If the actor is not a member, return **404, not 403** (Phase 2
exit gate: an unauthorised user cannot infer another matter exists). Returns
metadata, version history, and current processing state. Evidence bytes are
reached only through a short-lived signed URL, never a raw storage path.

### get_processing_status(ctx, document_id) -> ProcessingRead

Returns the current ProcessingRun state, the recorded provider metadata
(processor, version, region, purpose, timing, quality, outcome), and which
derivatives exist. Matter-scoped.

The V0 source-file contract is `GET /api/v1/source-files/{id}/processing`.
It requires `rta.document.classify` after resolving the source under `user_id`
and checking its matter. The response has `sourceFile` (the current source
version, also exposed as an ETag) and nullable `latestRun`. No recorded run is
unknown, never success. The latest attempt is ordered by `started_at`, then id.
Its summary includes terminal state, provider, recorded reasons and failure
explanation, meters, timing, and retained page quality/rotation diagnostics. It
excludes OCR text, candidate values, and object-storage paths.

Failure enums already persisted in run reasons restore the recovery details on
read; legacy runs with no recognised reason retain an unknown reason. A
successful V1 run can still contain `ocr_failed`, `ocr_sparse`, likely blank,
or uncertain-rotation pages. `manualReviewRequired` also covers unresolved
document classification/grouping and recorded review reasons. These diagnostics
do not introduce a partial-success lifecycle state or mark evidence accepted.

The current synchronous retry command remains
`POST /api/v1/source-files/{id}/process`, requiring `rta.source.upload` and
`If-Match` against the refreshed source version. A stale replay returns 412
without starting another attempt. Retries preserve original bytes and previous
runs. Existing organised documents are retained by the current processing
contract; extraction-generation correction is a separate workflow slice.

### get_viewer_manifest(ctx, document_version_id) -> ViewerManifestRead

Returns the exact immutable version required by an `EvidenceSpan`, not merely
the document's current version. Re-check matter membership, then issue
short-lived URLs for the original and available viewer derivatives. Include
page dimensions and the coordinate-space version so the frontend can map a
normalised evidence region to the correct PDF.js viewport or stored page
raster. Never return raw object-storage keys.

This endpoint serves evidence. Accept, correct, reject, and conflict-resolution
actions remain in `verification_service`.

Implemented today (V0): `GET /api/v1/source-files/{id}/content` streams the
original upload for the review screen, so a lawyer sees the document while
classifying it. It is matter-scoped like the file's record (another account
gets 404), re-checks the bytes against the hash taken at upload, sends
`Cache-Control: private, no-store` and `nosniff`, and audits
`rta.source-file.viewed`. It stands in for the short-lived signed URL above
until the viewer manifest exists.

### retry_processing(ctx, job_id) -> ProcessingRead

Idempotent. Retrying a `succeeded` run is a no-op that returns the current
state. Retrying a `failed` or `dead_letter` run opens a new attempt
(`attempt+1`) against the same immutable version, bounded to N attempts. Audit
`processing.retried`. This is the manual escape hatch for the exit gate's
explicit retry and manual-review state.

## 5A. Entitlement and metering

Every metered operation passes two independent gates in this order
(`security-model.md` §1). This section previously did not exist, so document
upload and OCR — the most expensive things Draftly does — were free regardless
of plan, and `billing-service.md`'s `document_pages.monthly` and
`storage_bytes.max` keys had no caller.

```text
auth_service.authorize(ctx, "document.upload", matter_id)
billing_service.require_feature(org, "document_processing.enabled")
billing_service.reserve_usage(org, "document_pages.monthly",
                              validated_page_count, operation_id=version_id)
billing_service.reserve_usage(org, "storage_bytes.max",
                              content_length, operation_id=version_id)
   -> store, persist, enqueue
   -> worker consumes actual pages on success
   -> release on terminal failure or dead-letter
```

Rules:

- **Reserve before the work, consume after it.** The page count is validated at
  ingest from the PDF page tree, not taken from the client. If the worker finds
  a different real count, it consumes the actual and the delta is reconciled.
- **`operation_id` is the `DocumentVersion` id**, so a retried processing run
  cannot double-charge (`billing-service.md` §5.3).
- **A dead-lettered run releases its reservation.** A failed OCR is not billable.
- **Quota exhaustion is a 429** with `code: "quota_exhausted"` and the metric in
  `details`, not a silent truncation (`api-conventions.md` §8).
- **Restricted mode blocks new uploads and processing but never existing
  reads.** An organisation in `restricted` can still open every document it
  already has (`billing-service.md` §10).

## 6. The async boundary

`workers/document_jobs.py` is not this service, but it closes the loop, so the
contract matters:

1. Claim the job idempotently — `SELECT … FOR UPDATE SKIP LOCKED`, or a claim
   token with a lease. A worker crash lets the lease expire and another worker
   re-claims. Claiming must be safe to run twice.
2. Set `running` and call `DocumentProcessingPort.process(version_ref)` (the
   Google Document AI adapter).
3. Store derivatives keyed to the run. Never touch the original.
4. On success, set `processed`, record all provider metadata and the outcome,
   and emit `document.processing-completed`. When the run also produced candidate
   particulars, emit `document.extraction-completed` as well — that is the event
   `verification_service.ingest_candidates` subscribes to. The two are
   deliberately separate: the first says derivatives exist, which is what the
   requirement projection needs; the second says candidates exist
   (`events.md` §5.4).
5. On provider failure, preserve the original, set `failed` with backoff retry,
   then `manual_review` or `dead_letter`, and emit `document.processing-failed`
   with `terminal` set accordingly — only the terminal case notifies. Release
   the usage reservation on `dead_letter` (§5A). No provider response ever sets a
   particular to verified (Phase 3 exit gate).

## 7. Processing state is not requirement state

The two state machines answer different questions:

```text
document_service
  uploaded | queued | processing | processed | failed | manual_review
  = what happened to this immutable file version?

task_service
  missing | requested | present | reviewed | accepted | rejected |
  not-applicable
  = does this matter satisfy this governed evidence requirement?
```

A successful processing run may move a matching task requirement from
`missing` or `requested` to `present`. It cannot move the requirement to
`accepted`. Acceptance requires an authorised lawyer to review and bind the
requirement to the exact `document_id` and `document_version_id`.

Replacing a document emits `document.version-superseded`. Consumers must mark
verified particulars, accepted requirements, completed dependent steps, and
readiness evaluations stale as applicable. This service publishes the fact of
supersession; it does not mutate those other services' records.

## 8. Evidence viewer and validation contract

### Preserve the original; do not recreate it

The verification surface displays the original PDF or image as uploaded. It
must not rebuild a deed, plan, or receipt as editable HTML or Word in an attempt
to reproduce its layout.

```text
Original document
= immutable legal evidence displayed from the pinned DocumentVersion

Candidate particulars
= machine-extracted structured values awaiting lawyer review

Generated draft
= a separate document created later from verified facts
```

Recreating the source would be unreliable for fonts, stamps, signatures,
handwriting, Sinhala shaping, spacing, and page breaks. More importantly, the
recreation would not be the evidence that was uploaded. Draftly instead draws a
non-destructive highlight overlay over the original display:

```text
Original PDF or page image
        +
EvidenceSpan overlay
        +
Candidate fact and lawyer decision controls
```

The overlay is a UI projection. It never modifies the stored original or burns
an annotation into the evidence file.

### Required interaction

The review screen is evidence beside decision:

```text
┌─────────────────────────────────┬──────────────────────────────┐
│ ORIGINAL DOCUMENT               │ EXTRACTED PARTICULARS        │
│                                 │                              │
│ Page 3                          │ Deed number                  │
│       ┌──────────────┐          │ 4471                         │
│       │ Deed No.4471 │          │ Confidence: 92%              │
│       └──────────────┘          │ [Accept] [Correct]           │
│                                 │                              │
│ Zoom · Rotate · Pages           │ Previous · Next              │
└─────────────────────────────────┴──────────────────────────────┘
```

Selecting a candidate fact must:

1. Open the `DocumentVersion` pinned by its `EvidenceSpan`.
2. Navigate to the recorded page.
3. Zoom or scroll the evidence region into view.
4. Draw the region highlight over the unchanged source.
5. Show alternative readings and provenance when a conflict exists.

For example:

```text
Document AI: 4471
Gemini:      4474
Status:      Conflict — lawyer decision required
```

The stored region uses normalised, viewport-independent coordinates:

```json
{
  "page": 2,
  "x": 0.42,
  "y": 0.18,
  "width": 0.21,
  "height": 0.06
}
```

`document-processing.md` owns conversion from provider coordinates into this
canonical space. The viewer multiplies the normalised values by the active page
viewport. Tests must cover zoom, rotation, resize, mixed page dimensions, and
the 0-based/1-based page-number boundary.

### Review legally material facts, not every OCR token

The OCR text layer may remain searchable, but token-by-token approval is out of
scope. Draftly asks the lawyer to decide only workflow-relevant particulars,
including names and identity references, deed/plan/lot numbers, dates, extents,
boundaries, consideration, ownership shares, rights of way, reservations, and
encumbrances.

Review priority is:

1. Conflicting or cross-document-mismatched values.
2. Low-confidence or Gemini-recovered values.
3. Missing or unreadable values.
4. Values sourced from a superseded document version.
5. Clear high-confidence values eligible for an explicitly recorded grouped
   confirmation.

Support three projections over the same candidate and verification records:

| Review mode | Purpose |
| --- | --- |
| Document review | Review the material facts extracted from one document version |
| Exception review | Show conflicts, low confidence, missing values, unreadable evidence, and superseded sources first |
| Cross-document review | Compare the same real-world fact across deeds, plans, assessments, and other evidence |

These are query and UI modes, not separate truth stores. Every accept,
correction, rejection, or unreadable decision is owned and audited by
`verification_service`.

## 9. Open-source reuse evaluation

### OpenContracts: reference architecture, not a Draftly replacement

[OpenContracts][opencontracts] is a self-hostable, MIT-licensed document
intelligence platform. Its useful overlap includes PDF/DOCX viewing, precise
text-to-coordinate mapping, human and machine-proposed annotations, structured
extraction in a grid, approve/reject review, permissions, and history. Its
[PAWLS-compatible PDF data layer][opencontracts-pdf] stores page dimensions,
tokens, bounding boxes, and character-to-position mappings. That is closely
aligned with Draftly's `EvidenceSpan` interaction.

The domain boundary is different:

| OpenContracts centres on | Draftly centres on |
| --- | --- |
| Corpuses, annotations, search, extraction grids, and citation graphs | Matters, immutable evidence versions, verified facts, cross-document checks, drafting, approval, and export |

OpenContracts is also a substantial application with its own Django backend,
Celery workers, GraphQL/REST APIs, data model, permissions, and React frontend.
Embedding the complete platform beside Draftly's FastAPI services would create
two identity, persistence, queue, and policy systems. Do **not** adopt the full
runtime for V0 without an architecture spike that proves data ownership,
matter isolation, deployment cost, and upgrade strategy.

The preferred evaluation order is:

1. Study and test its PDF coordinate/data-format ideas against synthetic
   Sinhala deeds and survey plans.
2. Identify narrowly reusable frontend or parser modules with clear dependency
   boundaries.
3. Preserve Draftly's `DocumentVersion`, `EvidenceSpan`, role, audit, and
   verification contracts around any reused code.
4. Record the exact upstream commit and licence notices before copying code.

No OpenContracts dependency is approved by this document. It is a strong
reference and spike candidate.

### Viewer component candidates

| Candidate | Useful capability | Draftly concern |
| --- | --- | --- |
| PDF.js | Browser PDF rendering and text/display layers; maximum control | Draftly must build navigation, overlay, virtualisation, and accessibility behaviour |
| `react-pdf-highlighter` | PDF.js-based text/area highlights, popovers, and scroll-to-highlight | Narrower feature set; verify current PDF.js compatibility and maintenance before pinning |
| `react-pdf-highlighter-plus` | Viewport-independent highlights plus notes, shapes, search, and PDF export | Much more than evidence review needs; disable editing/export features that could imply modification of original evidence |
| `react-pdf-selection` | Normalised permanent text/rectangle selections over PDF.js | Older project with maintenance risk; use as a coordinate-model reference unless a dependency audit passes |

For V0, run a focused spike with **PDF.js plus a thin Draftly-owned evidence
overlay**, and compare it with `react-pdf-highlighter` using the same synthetic
fixtures. Area highlights are mandatory because scanned deeds may have no
usable embedded text layer. Use the simpler option that passes the viewer tests
without introducing annotation-authoring or PDF-export behaviour.

### Industry precedent, not dependencies

The evidence-beside-fields interaction is an established human-in-the-loop
document-validation pattern:

| System | Relevant precedent | Draftly position |
| --- | --- | --- |
| [ABBYY Vantage][abbyy-review] | Manual Review compares extracted fields and low-confidence characters with the document image | Pattern reference only; not a selected provider |
| [Rossum][rossum-validation] | Validation screen, bounding boxes, review/confirm states, and automation blockers | Pattern reference only; invoice-oriented rather than notarial |
| [Amazon A2I][aws-a2i] | Human review loops for low-confidence Textract key-value extraction | Historical reference only; AWS closed access to new customers on 2026-07-30 |
| [Nanonets][nanonets] | Field confidence, validation rules, and low-confidence human review | Commercial benchmark only; not a source of Draftly truth |
| [Apryse WebViewer][apryse] | Commercial viewer and programmatic annotations | Paid fallback if the open-source spike fails accessibility, fidelity, or performance gates |

These products validate the workflow shape, not the legal model. Draftly still
needs domain-specific material facts, source-version pinning, cross-document
checks, lawyer-only verification, and approval/export gates.

M2 remains unchanged: its frontend uses pre-baked synthetic page images. The
viewer decision applies when real protected uploads are connected in M3/E8.10.

## 10. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Original immutable, never overwritten | `put_immutable` fails on an existing key; corrections and OCR write derivatives only |
| Checksum on every version | SHA-256 computed at ingest, stored on DocumentVersion |
| Replacement preserves history (inv. 7) | New version supersedes; old row and blob retained; stale facts flagged via event |
| Ack independent of OCR | Enqueue and return; the worker processes later |
| Original displayed, not recreated | Viewer manifest resolves the immutable original or its checksummed page-image derivative; highlights remain a separate overlay |
| Evidence opens exact source | Viewer lookup uses `DocumentVersion` from `EvidenceSpan`, never silently substitutes the current version |
| Coordinates survive viewport changes | Canonical normalised regions are mapped using recorded page dimensions and coordinate-space version |
| Machine result never authoritative | Derivatives flagged rebuildable; only verification promotes facts |
| Processing never implies acceptance | `processed` is emitted as evidence availability; only task-service records lawyer acceptance |
| Every mutation audited (inv. 8) | `AuditPort.record` on upload, replace, retry, and state changes |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership; storage keys are organisation-prefixed (`security-model.md` §2) |
| Matter isolation | Membership re-checked; 404 hides existence |
| Paid work is metered | Upload reserves pages and bytes, the worker consumes actual, a dead-lettered run releases (§5A) |
| Held evidence is never collected | The orphan-blob sweep and any deletion skip scopes under an active `retention.hold-placed` (`retention-service.md` §6) |

## 11. Failure modes to handle explicitly

- Duplicate upload (same checksum in the matter) — dedupe policy, see open
  decisions.
- Storage put succeeds, database commit fails — the reservation/object becomes
  unclaimed and `storage_service` reconciles it after the hold-aware grace
  period; `document_service` never deletes it directly.
- Database commit succeeds, enqueue fails — the outbox sweeper re-drains.
- Worker crash mid-run — lease expiry re-queues; the idempotent claim prevents
  double-processing.
- Oversized, disallowed mime, or zero-byte — rejected before storage.
- Superseded version still bound to an in-flight draft — the draft keeps its
  pinned version; new work uses the successor.
- Processing succeeds while a requirement remains unreviewed — expose the
  document as `present`; do not unblock readiness.
- Viewer opens the latest version instead of the evidence-pinned version —
  reject the mismatch and retain the historical version rather than moving the
  highlight to different evidence.
- PDF/page rotation or dimension mismatch moves the highlight — fail the viewer
  contract test; do not allow verification against a visibly misaligned span.
- Browser cannot render the original PDF — fall back to the checksummed page
  raster derivative and retain the same canonical `EvidenceSpan`.

## 12. Test list

- **Unit:** version and run state transitions, checksum, mime and size gates,
  supersession preserves history, idempotent retry, illegal-transition
  rejection.
- **Contract:** upload and get response schemas, the `ProcessingMessage` job
  schema, `ViewerManifestRead`, provider-result normalisation, and
  processing-completed and supersession events.
- **Integration:** real PostgreSQL plus storage emulator plus queue — upload to
  job to worker to `processed`; provider failure to `manual_review`; retry
  idempotency; orphan-blob reconciliation; outbox drain; processed evidence
  becomes present but not accepted in task-service; replacement stales the
  accepted requirement binding.
- **Viewer:** exact source version opens; fact click navigates to the correct
  page and region; highlights survive zoom, resize, rotation, and mixed page
  dimensions; scanned PDF falls back to an area highlight; original bytes and
  checksum remain unchanged; superseded evidence is visibly labelled.
- **Security:** cross-matter upload and read denied; 404-not-403 existence
  hiding; signed-URL expiry; no secret and no raw client data in logs.

## 13. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Dedupe on identical checksum** — reject as duplicate, return the existing
   version, or always create a new logical document? Lean **return the existing
   version and link it** for an exact-checksum re-upload.
2. **Queue technology** (plan §12 open) — for the V0 reference, **a
   Postgres-backed outbox plus a `SKIP LOCKED` poller** avoids a second infra
   dependency; swap to a real broker later behind `JobQueuePort`. Database and
   object-store choices are recorded in `backend/docs/infrastructure.md` (Neon
   for V0, self-hosted PostgreSQL for V1).
3. **Allowed mime and max size for V0** — **track Google Document AI's supported
   classes** (PDF and common image types), reject the rest to manual entry.
4. **Signed-URL TTL** for evidence reads — **short, on the order of minutes.**
5. **Real-upload viewer** — approve PDF.js plus a thin owned overlay,
   `react-pdf-highlighter`, or a narrowly extracted OpenContracts component only
   after the spike. Lean **PDF.js plus a Draftly-owned area/text overlay** for
   the smallest policy and dependency surface.
6. **DOCX evidence** — OpenContracts demonstrates a DOCX path, but Draftly V0's
   evidence pipeline is PDF/common-image first. Lean **convert an accepted DOCX
   upload to a checksummed PDF/page derivative while preserving the DOCX as the
   immutable original**, only after legal and rendering QA approves the
   conversion contract.

## 14. References

### October 2026 interpretation and page-accounting implementation

The lawyer-led workflow stores immutable interpretation snapshots. A semantic
type or ordered source/page change increments the detected document generation;
an unchanged confirmation does not. Evidence and machine observations pin that
generation. Exact downstream facts, links, checks and form eligibility become
stale in the same matter transaction through their owning public contracts.
Approved field bindings and artifact hashes remain historical and unchanged.

`POST /detected-documents/{id}/refresh-extraction` uses the current confirmed
type and ordered fragments, validated immutable originals and cached page OCR.
It appends an interpretation run and new candidates, including exact original
IDs when multiple originals each contain page 1. Failed or unsupported refresh
never restores an old candidate. `GET /detected-documents/{id}/interpretations`
returns snapshots and associated refresh attempts; `GET /review?generation=N`
opens an exact historical extraction. Legacy rows without matching current
extraction metadata project unavailable rather than claiming current success.
Current manual page evidence can pin a supported or unsupported interpretation
without citing a machine run; accepted-source and critical-fact policy still
apply in verification.

`POST /matters/{id}/detected-documents` creates a group from unclaimed pages.
Boundary decisions can retire explicitly version-pinned groups during a merge.
Inbox page accounting reports unknown bounds, unclaimed, overlapping,
out-of-bounds, blank and unsupported pages. Unknown or unsupported pages do not
establish completed review. `POST /source-files/{id}/page-dispositions` appends
a reasoned blank, unsupported or return-to-review decision. Its optional
`retireDocuments` only retires active groups consisting entirely of the selected
original/page; a larger group needs a separate range correction first.

Upload, process, supersede, classification, boundary, refresh, group creation
and page-disposition commands require `Idempotency-Key`. Versioned commands also
require `If-Match`. Replay authorizes the owned resource first, serializes a
first insert with the existing PostgreSQL replay store, and compares the body
including preconditions. Upload identity hashes the actual bytes and upload
metadata. A deliberate identical-byte upload with a new key remains a distinct
record. Terminal process failure followed by a new intent uses the current
source version and creates a new run. A cached response is historical; clients
read the current resource before presenting completion or eligibility.

Browser retry storage contains only actor/matter/operation identity, opaque key,
request digest, creation time and an optional original version. No input values,
filenames, files or tokens are retained. Manual evidence selected in a document
view pins source, page and interpretation together. Refreshing props cannot
renew that pin without an explicit selection or renewal.

Migrations `document0003` and `document0004` are additive. Downgrade refuses to
discard recorded corrections, mixed-source extraction pins, page dispositions
or associated interpretation runs. Empty migrated schemas can downgrade to base
and upgrade again. Running older application readers after corrections is
unsupported even if the new columns remain: a schema guard cannot stop older
code from ignoring generation pins. Legacy attempts lacking an association
cannot be reconstructed as exact document history.

Provider calls currently persist typed failures only when the call returns or
raises. Bounded OCR/classification/extraction deadlines and cancellation-safe
outcomes are a required Task 8 integration dependency, not a completed recovery
guarantee. Fresh intake matters still need checklist context before governed
extraction schemas are available; Task 5 owns that workflow dependency.

- [OpenContracts repository][opencontracts]
- [OpenContracts PDF data layer][opencontracts-pdf]
- [OpenContracts structured-extractor model][opencontracts-extractors]
- [PDF.js][pdfjs]
- [`react-pdf-highlighter`][react-pdf-highlighter]
- [`react-pdf-highlighter-plus`][react-pdf-highlighter-plus]
- [`react-pdf-selection`][react-pdf-selection]
- [ABBYY Vantage Manual Review][abbyy-review]
- [Rossum validation terminology][rossum-validation]
- [Amazon A2I human review][aws-a2i]
- [Nanonets Document Intelligence][nanonets]
- [Apryse WebViewer][apryse]

[opencontracts]: https://github.com/Open-Source-Legal/OpenContracts
[opencontracts-pdf]: https://github.com/Open-Source-Legal/OpenContracts/blob/main/docs/architecture/PDF-data-layer.md
[opencontracts-extractors]: https://github.com/Open-Source-Legal/OpenContracts/blob/main/docs/walkthrough/advanced/write-your-own-extractors.md
[pdfjs]: https://mozilla.github.io/pdf.js/
[react-pdf-highlighter]: https://github.com/agentcooper/react-pdf-highlighter
[react-pdf-highlighter-plus]: https://github.com/QuocVietHa08/react-pdf-highlighter-plus
[react-pdf-selection]: https://github.com/MathiasMeuleman/react-pdf-selection
[abbyy-review]: https://docs.abbyy.com/vantage/documentation/runtime/manual-review/verification
[rossum-validation]: https://knowledge-base.rossum.ai/docs/glossary
[aws-a2i]: https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-use-augmented-ai-a2i-human-review-loops.html
[nanonets]: https://nanonets.com/products/document-intelligence
[apryse]: https://docs.apryse.com/web/guides
