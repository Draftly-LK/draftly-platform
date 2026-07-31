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

## 8. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Original immutable, never overwritten | `put_immutable` fails on an existing key; corrections and OCR write derivatives only |
| Checksum on every version | SHA-256 computed at ingest, stored on DocumentVersion |
| Replacement preserves history (inv. 7) | New version supersedes; old row and blob retained; stale facts flagged via event |
| Ack independent of OCR | Enqueue and return; the worker processes later |
| Machine result never authoritative | Derivatives flagged rebuildable; only verification promotes facts |
| Processing never implies acceptance | `processed` is emitted as evidence availability; only task-service records lawyer acceptance |
| Every mutation audited (inv. 8) | `AuditPort.record` on upload, replace, retry, and state changes |
| Matter isolation | Membership re-checked; 404 hides existence |

## 9. Failure modes to handle explicitly

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

## 10. Test list

- **Unit:** version and run state transitions, checksum, mime and size gates,
  supersession preserves history, idempotent retry, illegal-transition
  rejection.
- **Contract:** upload and get response schemas, the `ProcessingMessage` job
  schema, provider-result normalisation, and processing-completed and
  supersession events.
- **Integration:** real PostgreSQL plus storage emulator plus queue — upload to
  job to worker to `processed`; provider failure to `manual_review`; retry
  idempotency; orphan-blob reconciliation; outbox drain; processed evidence
  becomes present but not accepted in task-service; replacement stales the
  accepted requirement binding.
- **Security:** cross-matter upload and read denied; 404-not-403 existence
  hiding; signed-URL expiry; no secret and no raw client data in logs.

## 11. Open decisions

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
