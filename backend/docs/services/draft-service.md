# draft-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `document-service.md`,
`memory-service.md`, and `task-service.md`. One markdown per service under
`backend/docs/services/`.

Maps to plan **Phase 7** (drafting, approval, and export — the drafting half),
the API row **Drafts** (§7), the trust-boundary row *Draft* (§5.2), and the
state invariants *a final draft references only verified/corrected particular
versions* and *approved wording changes only through a new approved template
version* (§5.3, invariants 4 and 6).

## 1. What it owns

Producing a **template-constrained, fact-bound draft snapshot** and versioning
it: create a draft against an approved Form template, save a new version from an
editor document, and restore an earlier version. Each version is an immutable,
content-hashed snapshot bound to exact fact and template versions (§5.2, Draft
boundary).

It owns **create, version, and restore only**. It does **not** approve a draft
(`approval-service` does) and does **not** export it (`export-service` does) —
those are separate services and separate documents. It does **not** author or
approve Form templates; those are governed by `content-governance-service`
(maintainer, `approvalState`). It reads verified facts but never verifies them
(`verification_service` owns that).

## 2. Where it sits

```text
GET  /matters/{id}/drafts                       ─┐
POST /matters/{id}/drafts                (create)─┼─→ api/v1/drafts.py
POST /matters/{id}/drafts/{draftId}/versions(save)│         │
POST /matters/{id}/drafts/{draftId}/restore      ─┘         │ orchestrates
                                                            ▼
                    ports: DraftRepository, FormTemplateReadPort,
                           VerifiedFactReadPort, ContentHashPort, AuditPort
```

The router authenticates and parses only. The service takes an already-resolved
`RequestContext` (actor, roles, matter memberships) and orchestrates domain plus
ports. Infrastructure implements the ports. The service imports no SQLAlchemy,
no FastAPI, and no renderer or provider SDK. The seam to approval and export is
described in §6.

## 3. Domain models it needs

Types below use the exact names and values from `frontend/src/types/draft.ts`.
In `domain/drafts.py`:

- **Draft** — the logical draft in a matter: `id`, `matterId`, `title`,
  `templateId` (`TemplateId`), `approvalState` (`DraftApprovalState`),
  `versions` (`DraftVersion[]`), `activeVersionId`, `approvedBy?`, `approvedAt?`.
  The `approvedBy` / `approvedAt` fields are set by `approval-service`, not here.
- **DraftVersion** — one immutable snapshot: `id`, `draftId`, `number`, `hash`
  (content hash, §5.2), `document` (`EditorDocument`), `createdBy`, `createdAt`,
  `restoredFromVersionId?`. Never mutated after creation.
- **FormTemplate** — the governed template (read-only here): `id`
  (`TemplateId`), `formNumber`, `nameKey`, `regime`, `transactionType`,
  `approvalState` (`draft | approved | retired`), `fields`
  (`FormTemplateField[]`), `blocks` (`FormTemplateBlock[]`).
- **FormTemplateField** — `id`, `labelKey`, `order`, `required`, `factBinding?`.
  A `factBinding` names the verified-fact key a field draws from.
- **FormTemplateBlock** — `id`, `order`, `kind`
  (`locked-prescribed | editable`), `placeholderText`. `locked-prescribed`
  blocks carry the approved wording; they may not be edited in place (invariant
  6, §7).

Editor node model (from `draft.ts`), enforced when a version is saved:

- **EditorDocument** — `{ type: "doc", content: [...] }`.
- **EditorFactChipNode** — `{ type: "factChip", attrs: { fact_id,
  verification_state: verified | corrected } }`. The chip's
  `verification_state` accepts only `verified` or `corrected` — an unverified
  fact cannot be chipped into a draft (invariant 4, §7).
- **EditorLockedNode** — `{ type: "lockedBlock", attrs: { template_block_id } }`.
  Its content comes from the FormTemplate's `locked-prescribed` block, not from
  free editing (invariant 6, §7).

`DraftApprovalState = working | in-review | approved | exported` (exact values
from `draft.ts`). This service moves a draft through `working` and produces new
versions; `in-review`, `approved`, and `exported` are driven by the approval and
export services. The state machine, enforced in the domain layer:

```text
Draft:  working → in-review → approved → exported
              ↖──────────────┘  (any edit after approval opens a new
                                 unapproved version — Phase 7 exit gate)
```

An illegal transition raises a domain error, not an HTTP error.

## 4. Ports it depends on

In `ports/`:

- `DraftRepository` — persist and load Draft and DraftVersion; matter-scoped
  queries only; optimistic version column on Draft.
- `FormTemplateReadPort` — load an `approved` FormTemplate by id (and by regime
  / transactionType); read-only, written by `content-governance-service`.
- `VerifiedFactReadPort` — read verified/corrected facts for the matter to test
  the eligibility precondition and to resolve fact chips; read-only.
- `ContentHashPort` — compute the deterministic content hash of a
  `DraftVersion.document` (plus its bound fact and template versions) for the
  `hash` field.
- `AuditPort` — `record(event)`; every create, save, and restore goes through
  here (invariant 8).

## 5. The methods

### list_drafts(ctx, matter_id) -> list[DraftRead]

Matter-scoped. Re-check membership from the repository; if the actor is not a
member, return **404, not 403** (Phase 2 exit gate). Returns each draft with its
version history and `activeVersionId`.

### create_draft(ctx, matter_id, template_id, title) -> DraftRead

1. Re-check matter membership; 404 hides existence.
2. **Enforce the eligibility precondition as a server-side check.** The matter
   must have verified or corrected facts for the keys **`transferee`** and
   **`extent`**. In the frontend this lives in `createDraft`, which silently
   returns `null` when the keys are missing. The backend must not do that:
   validate on the server and, when a requirement is missing, return a proper
   4xx that names the missing keys (see §6). A successful HTTP response must
   never imply facts are verified (plan §8).
3. Resolve the FormTemplate through `FormTemplateReadPort`; reject if it is not
   `approved` (a `draft` or `retired` template cannot back a new draft).
4. Create the Draft (`approvalState = working`) and an initial DraftVersion
   (`number = 1`) seeded from the template's blocks and fact-bound fields, with
   its content hash. Persist Draft and DraftVersion in one transaction.
5. Audit `draft.created`.

### save_version(ctx, matter_id, draft_id, document) -> DraftVersionRead

1. Re-check membership; 404 hides existence.
2. Validate the incoming `EditorDocument` against the template:
   - every `factChip` references a fact whose `verification_state` is `verified`
     or `corrected`; reject any chip bound to an unverified fact (invariant 4);
   - every `lockedBlock` matches an existing `locked-prescribed`
     `template_block_id` and carries the approved wording unchanged; reject
     altered locked wording (invariant 6);
   - editable blocks and free text are allowed.
3. If the draft is already `approved`, saving does not mutate the approved
   version. It creates a **new unapproved version** and moves the draft back
   toward `working` (Phase 7 exit gate: any edit after approval creates a new
   unapproved version). The approved snapshot stays intact for audit and export.
4. Create a DraftVersion (`number = previous + 1`) with a fresh content hash over
   the document and its bound fact/template versions; set it active. Persist in
   one transaction.
5. Audit `draft.version-saved`.

### restore_version(ctx, matter_id, draft_id, source_version_id) -> DraftVersionRead

1. Re-check membership; 404 hides existence.
2. Restore is **not** an in-place rewind. Create a **new** DraftVersion whose
   `document` is copied from `source_version_id`, set
   `restoredFromVersionId = source_version_id`, and give it the next `number` and
   a fresh hash. History is append-only; the restored-from version stays in
   place.
3. Re-run the save-time validation (step 2 of `save_version`) against current
   verified facts and the current template, so a restore cannot resurrect a chip
   whose fact was since unverified or a locked block whose approved wording since
   changed.
4. Audit `draft.version-restored`.

## 6. The seam to approval and export

draft-service stops at `working`. The rest of Phase 7 lives elsewhere:

```text
draft-service          approval-service            export-service
create / save /   ──▶  POST /draft-versions/{id}/  ──▶  POST /approvals/{id}/
restore (working)      approve (→ approved)             exports (→ exported)
   │                        │                                │
   │ eligibility gate       │ latest-hash, blockers,         │ manifest, checksum,
   │ (transferee+extent)    │ placeholders, lawyer role      │ expiry
```

- **Approval** (`approval-service.md`, plan `POST /draft-versions/{id}/approve`)
  targets one content hash, checks that no mandatory fact is unverified, that no
  placeholder is unresolved, and that the actor is a lawyer, then sets
  `approvedBy` / `approvedAt` and `approvalState = approved`. draft-service does
  not approve.
- **Export** (`export-service.md`, plan `POST /approvals/{id}/exports`) renders
  DOCX/PDF, records a manifest and checksum, and sets `approvalState = exported`.
  draft-service does not render or export.
- **Template governance** (`content-governance-service`) owns FormTemplate
  authoring and its `approvalState`. Form 8 is the first active V0 instrument;
  its wording is a lawyer-owned placeholder pending (invariant 6). draft-service
  consumes only `approved` templates and never edits prescribed wording.

The **eligibility precondition** (verified/corrected `transferee` **and**
`extent`) is a `create_draft` server precondition, returned as a 4xx listing the
missing requirements rather than a silent `null`.

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Draft references only verified/corrected facts (inv. 4) | `factChip.verification_state` accepts only `verified` or `corrected`; a chip on an unverified fact is rejected at save and restore |
| Approved wording changes only via a new approved template (inv. 6) | `lockedBlock` content must match an `approved` FormTemplate `locked-prescribed` block; altered locked wording is rejected; templates are governed elsewhere |
| Draft is a snapshot bound to exact versions (§5.2) | Each DraftVersion is immutable and carries a content `hash` over document plus bound fact/template versions |
| Any edit after approval opens a new unapproved version | `save_version` on an `approved` draft creates a new version, never mutating the approved snapshot |
| Eligibility is a server precondition | `create_draft` requires verified/corrected `transferee` and `extent`; missing keys return a 4xx, not a silent null |
| Matter isolation | Membership re-checked; 404 hides existence; drafts are matter-scoped |
| Every mutation audited (inv. 8) | `AuditPort.record` on create, save, and restore, with actor, before/after, correlation id |

## 8. Failure modes to handle explicitly

- `create_draft` on a matter missing verified `transferee` or `extent` —
  rejected with a 4xx naming the missing keys, never a silent null.
- Save containing a `factChip` bound to an unverified, conflicted, or blocked
  fact — rejected; only `verified`/`corrected` chips are allowed.
- Save altering a `locked-prescribed` block's wording or referencing an unknown
  `template_block_id` — rejected.
- Save or restore against a `retired` or `draft` template version — rejected;
  only `approved` templates back a draft.
- Edit after approval — permitted, but produces a new unapproved version and
  leaves the approved snapshot untouched.
- Fact corrected after a version was saved — the saved snapshot keeps its pinned
  fact versions; a new save/restore re-validates against current verified state.
- Concurrent saves to the same draft — optimistic version column rejects the
  stale write.
- Non-member or wrong-role actor — 404 for non-membership; role policy refusal
  otherwise.

## 9. Test list

- **Unit:** `DraftApprovalState` transitions; save on an approved draft opens a
  new unapproved version; fact-chip rejects unverified state; locked-block
  wording and unknown-block-id rejection; restore creates a new version with
  `restoredFromVersionId`; content-hash stability and change.
- **Contract:** `create_draft`, `save_version`, and `restore_version` request
  and response schemas; `EditorDocument` node-model validation; the 4xx shape
  for the missing-eligibility case.
- **Integration:** real PostgreSQL — create against an approved Form template,
  save several versions, restore an earlier one, edit after a simulated
  approval, and confirm the approved snapshot is preserved; missing-fact
  eligibility returns 4xx.
- **Security:** cross-matter draft read and write denied; 404-not-403 existence
  hiding; unverified fact cannot reach a saved version; altered locked wording
  cannot be persisted; audit written for every mutation.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Eligibility requirement source.** The `transferee` + `extent` requirement
   is hardcoded in the frontend. Recommend the **FormTemplate declares its own
   required fact bindings** (`FormTemplateField.required` + `factBinding`) so the
   precondition is data-driven per form rather than hardcoded for Form 8; keep
   `transferee` + `extent` as the Form 8 defaults until the template is
   confirmed.
2. **Content-hash inputs.** `DraftVersion.hash` must cover the editor document
   plus the exact bound fact versions and template version. Recommend a
   **canonical serialization of `{document, fact_version_ids,
   template_version}`** hashed with SHA-256; confirm the canonical form so hashes
   are reproducible across reopen (Phase 7 exit gate on reopen validation).
3. **Where fact/template version pins live.** The frontend `DraftVersion` has no
   explicit fact-version or template-version fields. Recommend **adding pinned
   version references to the backend DraftVersion** (not surfaced to the editor)
   so a snapshot is provably bound to exact versions (§5.2); confirm the columns.
4. **Restore validation strictness.** Should restoring a version whose facts are
   now unverified or whose locked wording has changed be blocked, or allowed with
   a warning that forces a re-save? Recommend **block and report the specific
   conflicts**, consistent with the create/save gates.
5. **Draft title source.** `title` is free text in the frontend. Recommend
   **defaulting from the template `nameKey` and form number** while allowing an
   override; confirm.
