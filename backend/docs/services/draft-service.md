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

It owns **create, version, restore, and submit-for-review**. It does **not**
approve a draft (`approval-service` does) and does **not** export it
(`export-service` does) — those are separate services and separate documents. It
does **not** author or approve Form templates; those are governed by
`content-governance-service` (maintainer, `approvalState`). It reads verified
facts but never verifies them (`verification_service` owns that).

Submission is here, not in `approval-service`, because it is the last authoring
act: it freezes which version the approver will judge. Before this document was
corrected, `approval-service` refused anything that was not `in-review` and no
service ever set `in-review`, so the approval gate was unreachable.

## 2. Where it sits

```text
GET  /matters/{id}/drafts                        ─┐
POST /matters/{id}/drafts                 (create)│
POST /matters/{id}/drafts/{draftId}/versions(save)┼─→ api/v1/drafts.py
POST /matters/{id}/drafts/{draftId}/restore       │         │
POST /matters/{id}/drafts/{draftId}/submit        │         │ orchestrates
POST /matters/{id}/drafts/{draftId}/withdraw     ─┘         ▼
                    ports: DraftRepository, FormTemplateReadPort,
                           VerifiedFactReadPort, CheckReadPort,
                           ContentHashPort, EventPort, AuditPort
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
from `draft.ts`). This service owns `working → in-review` (submit) and
`in-review → working` (withdraw, and any edit). `approval_service` owns
`in-review → approved`; `export_service` owns `approved → exported`. The state
machine, enforced in the domain layer:

```text
                submit                 approve                 render
Draft:  working ───────▶ in-review ───────────▶ approved ───────────▶ exported
           ▲   ◀───────      │                     │                     │
           │   withdraw      │                     │                     │
           └─────────────────┴─────────────────────┴─────────────────────┘
                     any save_version or restore_version returns the
                     draft to `working` as a new unapproved version
                     (Phase 7 exit gate)
```

Every transition has exactly one owner, and no state is reachable only from a
service that refuses to enter it. An illegal transition raises a domain error,
not an HTTP error.

## 4. Ports it depends on

In `ports/`:

- `DraftRepository` — persist and load Draft and DraftVersion; matter-scoped
  queries only; optimistic version column on Draft.
- `FormTemplateReadPort` — load an `approved` FormTemplate by id (and by regime
  / transactionType); read-only, written by `content-governance-service`.
- `VerifiedFactReadPort` — read verified/corrected facts for the matter to test
  the eligibility precondition and to resolve fact chips; read-only.
- `CheckReadPort` — read the current blocking finding set for the matter, used
  by `submit_for_review` to report blockers before an approver sees them.
  Read-only; the authoritative gate stays in `approval_service`.
- `EventPort` — publish `draft.*` events through the same outbox every other
  service uses (`events.md` §5.10).
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

### submit_for_review(ctx, matter_id, draft_id) -> DraftRead

The missing transition. It moves `working → in-review` and fixes which version
the approver will judge.

1. Re-check membership; 404 hides existence. Require `draft.submit-for-review`
   (`security-model.md` §3.1).
2. Require `approvalState = working`. Submitting an `in-review`, `approved`, or
   `exported` draft is an illegal transition.
3. Re-run the full save-time validation (step 2 of `save_version`) against the
   **current** verified facts and the current template version. A draft whose
   chips have gone stale since the last save cannot be submitted.
4. **Run the approval gates advisorily** — the fact gate, the blocker gate via
   `CheckReadPort`, and the placeholder scan. Failures are returned as a 422
   listing each unmet condition. This is deliberately not authoritative:
   `approval_service` re-runs all three at approval time and is the only gate
   that counts (`approval-service.md` §5). The point is that the drafting lawyer
   discovers the blockers, not the approver.
5. Pin the submitted version: set `activeVersionId` and record
   `submittedVersionId`, `submittedBy`, `submittedAt` on the Draft. A save after
   submission returns the draft to `working` (step 3 of `save_version`), so the
   pin can never silently drift under the approver.
6. Set `approvalState = in-review`, persist, publish `draft.review-requested`
   with the version id and content hash, and audit `draft.submitted`.

### withdraw_from_review(ctx, matter_id, draft_id, reason) -> DraftRead

Moves `in-review → working` without approving or rejecting. Requires
`draft.submit-for-review` and a non-empty reason. Clears the submission pin,
audits `draft.withdrawn`. An approver who wants changes uses this rather than
leaving a draft parked in `in-review`.

## 6. The seam to approval and export

draft-service stops at `in-review`. The rest of Phase 7 lives elsewhere:

```text
draft-service                  approval-service        export-service
create / save / restore  ──▶   approve            ──▶  create_export
  → working                      in-review→approved      approved→exported
submit_for_review        ──▶
  working → in-review
  │                              │                       │
  │ eligibility gate             │ fact, blocker and     │ manifest, checksum,
  │ (template-declared keys)     │ placeholder gates,    │ expiry, signed URL
  │ + advisory gate preview      │ hash pin, role gate   │
```

- **Approval** (`approval-service.md`; public route
  `POST /matters/{id}/drafts/{draftId}/approve`, resolved server-side to the
  `in-review` version per `api-conventions.md` §1) targets one content hash,
  checks that no mandatory fact is unverified, that no blocking finding is
  unresolved, that no placeholder remains, and that the actor holds
  `draft.approve` and is a practising notary, then sets `approvedBy` /
  `approvedAt` and `approvalState = approved`. draft-service does not approve.
- **Export** (`export-service.md`, plan `POST /approvals/{id}/exports`) renders
  DOCX/PDF, records a manifest and checksum, and sets `approvalState = exported`.
  draft-service does not render or export.
- **Template governance** (`content-governance-service`) owns FormTemplate
  authoring and its `approvalState`. Form 8 is the first active V0 instrument;
  its wording is a lawyer-owned placeholder pending (invariant 6). draft-service
  consumes only `approved` templates and never edits prescribed wording.

The **eligibility precondition** is a `create_draft` server precondition,
returned as a 422 with `code: "draft_eligibility_unmet"` and
`details.missingFactKeys` (`api-conventions.md` §5), never a silent `null`. The
required key set comes from the template's own `FormTemplateField.required` +
`factBinding` declarations; `transferee` and `extent` are the Form 8 values, not
a hardcoded rule (open decision 1, now closed).

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Draft references only verified/corrected facts (inv. 4) | `factChip.verification_state` accepts only `verified` or `corrected`; a chip on an unverified fact is rejected at save and restore |
| Approved wording changes only via a new approved template (inv. 6) | `lockedBlock` content must match an `approved` FormTemplate `locked-prescribed` block; altered locked wording is rejected; templates are governed elsewhere |
| Draft is a snapshot bound to exact versions (§5.2) | Each DraftVersion is immutable and carries a content `hash` over document plus bound fact/template versions |
| Any edit after approval opens a new unapproved version | `save_version` on an `approved` draft creates a new version, never mutating the approved snapshot |
| Eligibility is a server precondition | `create_draft` requires the template's declared required fact bindings verified or corrected; missing keys return 422 with the key list, not a silent null |
| Every state has exactly one owner | draft-service owns `working ⇄ in-review`; approval owns `in-review → approved`; export owns `approved → exported`. No state is reachable only from a service that refuses to enter it |
| Submission pins the reviewed version | `submit_for_review` records `submittedVersionId`; any later save returns the draft to `working`, so the approver's target cannot drift |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership (`security-model.md` §2) |
| Matter isolation | Membership re-checked; 404 hides existence; drafts are matter-scoped |
| Every mutation audited (inv. 8) | `AuditPort.record` on create, save, restore, submit, and withdraw, with actor, before/after, correlation id |

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

- **Unit:** `DraftApprovalState` transitions in both directions, including
  submit, withdraw, and the save-returns-to-working rule; save on an approved
  draft opens a new unapproved version; fact-chip rejects unverified state;
  locked-block wording and unknown-block-id rejection; restore creates a new
  version with `restoredFromVersionId`; content-hash stability and change;
  submit re-validates against current facts and refuses a stale chip.
- **Contract:** `create_draft`, `save_version`, `restore_version`,
  `submit_for_review`, and `withdraw_from_review` request and response schemas;
  `EditorDocument` node-model validation; the 422 `draft_eligibility_unmet`
  shape with `missingFactKeys`; the `draft.review-requested` event payload.
- **Integration:** real PostgreSQL — create against an approved Form template,
  save several versions, restore an earlier one, submit, approve, edit after
  approval, and confirm the approved snapshot is preserved; **a draft can travel
  create → submit → approve → export end to end** (the reachability regression
  test for the gate that was previously unreachable); a save during `in-review`
  returns the draft to `working` and invalidates the pin; missing-fact
  eligibility returns 422.
- **Security:** cross-matter draft read and write denied; 404-not-403 existence
  hiding; unverified fact cannot reach a saved version; altered locked wording
  cannot be persisted; audit written for every mutation.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Eligibility requirement source — closed.** The FormTemplate declares its
   own required fact bindings (`FormTemplateField.required` + `factBinding`);
   `transferee` + `extent` remain the Form 8 values. The frontend's hardcoded
   check is retired at M3 (`frontend-contract-migration.md`).
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

### Canonical and association invalidation (2026-10-09)

The existing FormInputInvalidationPort accepts an optional reason while continuing
to match exact bound fact IDs. Canonical corrections/conflicts use
FACT_NO_LONGER_CONFIRMED; transaction association changes use
SCOPE_ASSOCIATION_CHANGED. The form owner preserves artifact hash, rendered field
values and historical pins when marking an approved form STALE_AFTER_APPROVAL.
Readiness is an operational projection and cannot substitute for form preflight or
approval eligibility. Existing multi-scope compatibility withholding remains in force.
