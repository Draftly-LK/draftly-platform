# document_service — implementation design

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
POST /matters/{id}/documents ─┐
POST /documents/{id}/versions ─┼─→ api/v1/documents.py ─→ application/document_service.py
GET  /documents/{id}          ─┘                                   │
GET  /documents/{id}/processing                                    │ orchestrates
POST /processing/{job}/retry                                       ▼
                                    ports: DocumentRepository, ObjectStoragePort,
                                           JobQueuePort, AuditPort
                                    (DocumentProcessingPort is used by the WORKER)
```

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
- `ObjectStoragePort` — `put_immutable(key, stream) -> stored_ref` and
  `signed_url(key, ttl)`. The put must fail if the key already exists.
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
history (invariant 7). The service emits `document.version_superseded` so
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

### get_viewer_manifest(ctx, document_version_id) -> ViewerManifestRead

Returns the exact immutable version required by an `EvidenceSpan`, not merely
the document's current version. Re-check matter membership, then issue
short-lived URLs for the original and available viewer derivatives. Include
page dimensions and the coordinate-space version so the frontend can map a
normalised evidence region to the correct PDF.js viewport or stored page
raster. Never return raw object-storage keys.

This endpoint serves evidence. Accept, correct, reject, and conflict-resolution
actions remain in `verification_service`.

### retry_processing(ctx, job_id) -> ProcessingRead

Idempotent. Retrying a `succeeded` run is a no-op that returns the current
state. Retrying a `failed` or `dead_letter` run opens a new attempt
(`attempt+1`) against the same immutable version, bounded to N attempts. Audit
`processing.retried`. This is the manual escape hatch for the exit gate's
explicit retry and manual-review state.

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
   and emit `document.processing-completed` for classification, extraction,
   and task requirement projection consumers.
5. On provider failure, preserve the original, set `failed` with backoff retry,
   then `manual_review` or `dead_letter`. No provider response ever sets a
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

Replacing a document emits `document.version_superseded`. Consumers must mark
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
| Matter isolation | Membership re-checked; 404 hides existence |

## 11. Failure modes to handle explicitly

- Duplicate upload (same checksum in the matter) — dedupe policy, see open
  decisions.
- Storage put succeeds, database commit fails — orphan blob — reconciliation or
  garbage-collection sweep.
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
