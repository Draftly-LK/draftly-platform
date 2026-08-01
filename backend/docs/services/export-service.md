# export_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`approval-service.md`, and `document-service.md`. One markdown per service under
`backend/docs/services/`.

Maps to plan **Phase 7** (drafting, approval, and export), the API row
**Exports** (§7), the trust-boundary row *Approval/export* (§5.2), and the
`exports/` storage prefix in `backend/docs/infrastructure.md`.

## 1. What it owns

Rendering an **approved** draft version to DOCX or PDF, storing the file in the
object store under the `exports/` prefix, and recording an integrity manifest
plus a checksum so a reader can prove which draft, template, and fact versions
produced the file. It owns the write path for approved outputs and the read path
for their metadata and short-lived download links.

It does **not** run the approval gate (`approval_service` does), does **not**
decide fact or blocker states, and does **not** hold the render inline in the
request. Rendering is an asynchronous worker behind a port; the request returns
a job id.

The frontend `exportDraft` today only flips `Draft.approvalState` to
`"exported"` and logs a `draft.exported-{format}` audit event in the demo
store — **no file is produced**. The real render is unbuilt, and this service
specifies it.

## 2. Where it sits

```text
POST /api/matters/{id}/drafts/{draftId}/exports ─┐  (frontend contract)
  { format: "docx" | "pdf" }                     │
POST /approvals/{id}/exports ────────────────────┼─→ api/v1/exports.py
  (plan §7 API surface)                          │        │
GET  /exports/{id} ──────────────────────────────┘        │ → application/export_service.py
                                                           │
                                    approval_service ──────┤ (must be approved)
                                                           │ enqueues
                                                           ▼
                                    ports: ExportRepository, RenderingPort,
                                           ObjectStoragePort, JobQueuePort, AuditPort

workers/export_jobs.py ─→ RenderingPort (office_renderer) ─→ ObjectStoragePort (exports/ prefix)
```

The router authenticates and parses only. The service takes an
already-authenticated `RequestContext`, validates that the target is approved,
and enqueues a render job. It imports no SQLAlchemy, no FastAPI, and no office
SDK — rendering lives in `infrastructure/rendering/office_renderer.py` behind
`RenderingPort` (plan §4).

Long-running work does not hold the request open (plan §7): the endpoint returns
a **job id and state**, and the client polls `GET /exports/{id}`.

## 3. Domain models it needs

The frontend has no `Export` or `Manifest` type, so both are defined here.

In `domain/exports.py`:

- **Export** — one render of one approved version. `id`, `approval_id`,
  `draft_version_id`, `format` (`"docx" | "pdf"`), `state`, `storage_key` (under
  the `exports/` prefix), `checksum` (SHA-256 of the rendered bytes), `manifest`,
  `created_at`, `expires_at`. Written once the render succeeds; the row exists
  from job creation with `state` tracking progress.
- **Manifest** — the integrity anchor, per plan §7 (`Manifest`, checksum,
  expiry) and §10. Records: application version, template version (the
  `FormTemplate` id/version bound to the draft), the fact versions used, and the
  content hash (the approved `DraftVersion.hash`). This is what makes an export
  self-describing: it identifies the exact draft/template/fact versions (Phase 7
  exit gate).
- **ExportState** — `queued → rendering → rendered` with `↘ failed` and an
  `expired` terminal once `expires_at` passes. `DraftApprovalState` moves to
  `"exported"` only after the first successful render, and only through
  `approval_service`'s state, so `approved` remains the pin.

```text
Export:  queued → rendering → rendered → (expires_at) → expired
                            ↘ failed → (retry) → dead_letter
```

An illegal transition raises a domain error, not an HTTP error.

## 4. Ports it depends on

In `ports/`:

- `RenderingPort` — `render(version_document, format) -> rendered_bytes`; the
  `office_renderer` adapter (plan §4). Server-side DOCX/PDF; the domain and
  application layers never touch the office SDK.
- `ObjectStoragePort` — `put_immutable(key, stream)` under
  `exports/{export_id}/...` and `signed_url(key, ttl)` for the short-lived
  download link. Reuses the same port as `document_service`.
- `ExportRepository` — persist and load Export rows and manifests; matter-scoped
  queries only.
- `JobQueuePort` — `enqueue(RenderMessage)` with a signed, authenticated body.
- `AuditPort` — `record(event)`; export is a material mutation (invariant 8).

## 5. The methods

### create_export(ctx, approval_id, format) -> ExportRead

1. Re-check matter membership and role from the repository; do not trust the
   router.
2. Load the Approval. **Reject unless the target draft version is `approved`**
   (seam to `approval_service`; Phase 7). An export can only run on an approved
   version — never on `working` or `in-review`.
3. Validate `format` against the `"docx" | "pdf"` allowlist, then pass the two
   gates: `authorize(ctx, "export.create", matter_id)` and
   `require_feature(org, "export.enabled")`, followed by
   `reserve_usage(org, "exports.monthly", 1, operation_id=export_id)`. The
   reservation is consumed when the render succeeds and released on
   `dead_letter` — a failed render is not billable
   (`billing-service.md` §7.2). An organisation in `restricted` mode cannot
   create a new export but can still download every export it already has
   (`billing-service.md` §10).
4. Create the Export row (`state=queued`) bound to `approval_id`,
   `draft_version_id`, and the pinned content hash, plus an outbox row for the
   render message, in one transaction. This mirrors `document_service`: never
   enqueue a job for a row the database does not have.
5. After commit, the outbox drains to `JobQueuePort`. Audit `export.requested`.
6. Return the job id and `state=queued`. No file exists yet; the response says
   requested, never rendered.

### get_export(ctx, export_id) -> ExportRead

Matter-scoped. If the actor is not a member, return **404, not 403** (existence
hiding, Phase 2 exit gate). Returns state, format, the manifest, and — once
`rendered` and not expired — a short-lived signed download URL, never a raw
storage path (infrastructure.md). An expired export returns metadata and manifest
but no URL.

## 6. The async boundary

`workers/export_jobs.py` is not this service, but it closes the loop:

1. Claim the job idempotently (claim token or `SELECT … FOR UPDATE SKIP
   LOCKED`); a crashed worker's lease expires and another re-claims. Set
   `rendering`.
2. Re-load the approved `DraftVersion` and its manifest inputs. **Re-verify the
   version is still `approved` and its hash unchanged**; if a new working version
   exists, the approval still pins the old hash, so render exactly that.
3. Call `RenderingPort.render(document, format)`. Produce DOCX or PDF
   server-side.
4. Compute SHA-256 of the rendered bytes and `put_immutable` under
   `exports/{export_id}/{format}`. Write the manifest (application, template,
   fact versions, content hash) beside it.
5. Set `rendered`, store `storage_key`, `checksum`, `manifest`, and
   `expires_at`. Set `Draft.approvalState = "exported"` through
   `approval_service`'s state. Audit `export.rendered` with the checksum and
   manifest reference.
6. On render failure, retain any prior successful export, set `failed` with
   backoff, then `dead_letter`. A failed render never leaves a partial file
   reachable by a signed URL.

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Export only on an approved version (Phase 7, §5.2) | `create_export` and the worker both reject unless the target is `approved`; the hash is re-checked before render |
| Every export identifies exact draft/template/fact versions (Phase 7) | Manifest records application, template version, fact versions, and content hash |
| No hidden placeholder in output (§9.2) | Approval already blocked unresolved placeholders; the render uses the approved, gate-cleared version verbatim |
| No altered locked wording in output (§9.2) | Render consumes the pinned approved document; no re-binding or edit path exists in this service |
| Checksum on every rendered file (§5.2) | SHA-256 computed over the rendered bytes, stored on Export and in the manifest |
| Exports isolated in their own prefix (§10, infrastructure.md) | `put_immutable` writes under `exports/{export_id}/…`, separate retention from originals and derivatives |
| Download only via expiring signed URL | `get_export` returns a short-lived `signed_url`, never a raw path; expired exports return no URL |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership |
| Paid renders are metered | `exports.monthly` reserved at request, consumed on success, released on `dead_letter` |
| An invalidated approval stops a queued render | The worker re-checks the Approval and refuses after `draft.approval-invalidated` |
| Held exports are not expired away | Objects under an active retention hold are retained past `expires_at`; only the URL expires |
| Every export audited (inv. 8) | `AuditPort.record` on `export.requested` and `export.rendered` |

## 8. Failure modes to handle explicitly

- Approval revoked or version superseded after the job is queued — the worker
  re-checks approval and hash; if the pin is gone, fail the job, do not render.
- Render succeeds, database commit fails — orphan file in `exports/`;
  reconciliation or garbage-collection sweep, as in `document_service`.
- Commit succeeds, enqueue fails — the outbox sweeper re-drains.
- Worker crash mid-render — lease expiry re-queues; the idempotent claim
  prevents a double file.
- Sinhala or English glyph/layout loss — caught by reopen validation (§9),
  release-blocking if the output does not survive reopen.
- Signed URL requested after `expires_at` — return metadata only; require a new
  export to re-render.

## 9. Test list

- **Unit:** export state transitions, manifest assembly from pinned versions,
  checksum computation, approved-only gate, illegal-transition rejection.
- **Contract:** `create_export` / `get_export` schemas, the `RenderMessage` job
  schema, the Manifest structure (application, template, fact versions, content
  hash), the `"docx" | "pdf"` format enum.
- **Integration:** real PostgreSQL plus storage emulator plus queue —
  request to job to worker to `rendered`; render failure to `dead_letter`;
  outbox drain; orphan-file reconciliation; **English and Sinhala output
  survives reopen validation** (Phase 7 exit gate); signed-URL expiry.
- **Security:** export of a non-approved version denied; cross-matter export and
  read denied; 404-not-403 existence hiding; expired-URL rejection; no raw
  storage path and no client data in logs.

## 10. Supporting-document renders

`content-governance-service.md` §4.2 marks title reports, the verified
particulars report, the matter fact sheet, the property schedule, the execution
pack, the registration pack, the evidence manifest, and the export manifest as
`mvp` outputs. Nothing rendered them: this service only ever rendered an
approved `DraftVersion` from an `approval_id`, and no second renderer existed.

Rather than build a second renderer with a second manifest and checksum path,
this service generalises. `Export` gains a target discriminator:

```text
ExportTarget =
  { kind: "draft-version", approvalId, draftVersionId }
| { kind: "supporting-document", templateId, templateVersion, matterId, params }
```

The two paths differ in exactly one place — the gate:

| Target kind | Gate |
| --- | --- |
| `draft-version` | Must be `approved`; hash re-verified before render (§5, §6) |
| `supporting-document` | Template must be `approved`; the caller needs `export.create`; **no approval gate**, because a Draftly report is not a legal instrument |

Everything else is shared: the job queue, the `exports/` prefix, the checksum,
the manifest, the signed URL, the expiry, and the audit events.

Two rules keep the distinction honest:

- **A supporting document is labelled as a Draftly output**, never as a
  statutory form (`content-governance-service.md` §8). The renderer stamps the
  category from the template and refuses a template whose category claims
  official status without the corresponding governed provenance.
- **A report's manifest records what it drew on** — the fact versions, check
  evaluation versions, and document versions it read — so a title report can be
  re-derived and audited exactly as a draft export can. A report that quotes an
  unverified particular marks it as unverified in the output rather than
  presenting it flat.

The job type is `report.render`, sharing the worker module with
`export.render` (`jobs-and-workers.md` §5).

## 11. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **First-class Export and Manifest types** — the frontend has neither. Lean
   **define Export** (`id`, `approval_id`, `draft_version_id`, `format`,
   `storage_key`, `checksum`, `manifest`, `created_at`, `expires_at`) and a
   **Manifest** (application version, template version, fact versions, content
   hash) per plan §7 and §10.
2. **Endpoint reconciliation** — the frontend posts to
   `/api/matters/{id}/drafts/{draftId}/exports`; plan §7 targets
   `/approvals/{id}/exports`. Lean **keep the matter-scoped route as the public
   contract** and resolve it to the draft's current Approval server-side.
3. **Rendering engine** — the office renderer behind `RenderingPort` (LibreOffice
   headless, a DOCX template engine, or a print-to-PDF path). This is the plan §12
   renderer-version approval item; the domain contract stays real behind the port.
4. **Export URL TTL and retention** — how long a signed download link lives and
   how long the `exports/` object is retained. Lean **short-lived URL (minutes)**
   with a longer object retention set by policy (§10), recorded separately from
   originals.
5. **Re-export policy** — whether re-exporting the same approval reuses the
   existing file or renders a fresh Export row. Lean **one Export row per render
   request**, each with its own checksum and manifest, so history is complete.
