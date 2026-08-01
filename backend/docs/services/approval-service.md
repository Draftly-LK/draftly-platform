# approval_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`document-service.md`, and `memory-service.md`. One markdown per service under
`backend/docs/services/`.

Maps to plan **Phase 7** (drafting, approval, and export), the API row
**Approval** (§7), and the trust-boundary row *Approval/export* (§5.2).

## 1. What it owns

The gate between a working draft and an approved instrument. It takes one draft
version, proves that every release-blocking condition is clear, pins the exact
content, records who approved what, and emits the audit event that lets export
run. Nothing downstream may treat a draft as approved unless this service said
so against a specific content hash.

It does **not** decide whether a fact is verified (`verification_service`
does), does **not** run the deterministic checks (`check_service` does), does
**not** edit draft content (`draft_service` does), and does **not** render
files (`export_service` does). It reads those verdicts, enforces the gate, and
hands off.

## 2. Where it sits

```text
POST /api/v1/matters/{id}/drafts/{draftId}/approve ─┐
GET  /api/v1/matters/{id}/drafts/{draftId}/approval ┼─→ api/v1/drafts.py
                                                    │        │
  (public contract; the server resolves the draft   │        ▼
   to its `in-review` version — api-conventions §1) │  application/approval_service.py
                                                    │        │
                                                    └────────┤ orchestrates
                                                             ▼
                    ports: ApprovalRepository, DraftReadPort,
                           VerifiedFactReadPort, CheckReadPort,
                           EventPort, AuditPort, ClockPort
```

The router authenticates and parses only. The service takes an
already-authenticated `RequestContext` (actor, roles, matter memberships) and
orchestrates domain plus ports. It imports no SQLAlchemy, no FastAPI, and no
rendering SDK.

The endpoint mismatch between the frontend and plan §7 is settled centrally in
`api-conventions.md` §1: the matter-scoped route is the public contract and the
server resolves it to the version that is actually pinned. The backend approves
a **version**, never a draft. Today the frontend only flips
`Draft.approvalState` to `"approved"` and stamps `approvedBy` / `approvedAt` in
the demo store — no gate runs at all.

The draft reaches this service in `in-review` because
`draft_service.submit_for_review` put it there (`draft-service.md` §5). That
step did not previously exist, which made this gate unreachable.

## 3. Domain models it needs

In `domain/approvals.py`:

- **Approval** — the first-class record the frontend lacks. `id`,
  `draft_version_id`, `content_hash` (the pinned `DraftVersion.hash`),
  `approver_id`, `approver_role`, `approved_at`, `matter_id`, and a
  `blockers_checked` snapshot capturing what was clear at approval time (the
  fact states, findings, and placeholder scan that let the gate pass). Immutable
  once written.
- **ApprovalState** — mirrors `DraftApprovalState` from the frontend
  (`draft.ts`): `working` → `in-review` → `approved` → `exported`. The service
  owns the `in-review` → `approved` transition and rejects any other source
  state. `exported` is set by `export_service`, never here.

Why a first-class record. The frontend models approval as only a state plus
`approvedBy?` / `approvedAt?` on `Draft`. That cannot answer "which exact bytes
were approved, by whom, and what was verified at the time" after later edits.
Phase 7 and §9.2 require that approval never silently covers changed content, so
the backend persists the hash and the blockers snapshot as an audit anchor, not
just two nullable fields.

The single legal state transition is enforced in the domain layer so the first
tests hit it without a database:

```text
Draft:  working → in-review → approved → exported
                     │           │
                     │           └─ any edit → new working version (unapproved)
                     └─ approve() rejects unless source is in-review and gate clear
```

An illegal transition or a failed gate raises a domain error, not an HTTP error.

## 4. Ports it depends on

In `ports/`:

- `ApprovalRepository` — persist and load Approval records; organisation- and
  matter-scoped queries only; one active approval per content hash.
- `DraftReadPort` — load the `DraftVersion` (id, hash, document) and its current
  state; the service never trusts a hash supplied by the caller.
- `VerifiedFactReadPort` — fact state per bound `FactChip.fact_id`. The same
  port `draft_service` and `task_service` use.
- `CheckReadPort` — the current blocking finding set for the matter and version.
  The same port `task_service` uses.
- `EventPort` — publish `draft.approved` and `draft.approval-invalidated`
  through the outbox (`events.md` §5.10).
- `AuditPort` — `record(event)`; the approval event is a material mutation
  (invariant 8).
- `ClockPort` — the approval timestamp; injected so tests are deterministic.

Fact and blocker states are read **through ports**, not by importing sibling
application services. An earlier draft of this document allowed the direct
call; that contradicts the dependency rule in plan §5.1 that every other service
follows, and both ports already exist for exactly these reads.

## 5. The method

### approve(ctx, draft_version_id) -> ApprovalRead

1. Re-check organisation scope, then matter membership, then require the
   `draft.approve` capability **and** a current practising notary
   (`security-model.md` §3.1 and §3.3). A `reviewer` is refused with 403
   `capability_denied` (Phase 2 exit gate). A non-member gets 404.
2. Load the `DraftVersion`. Reject unless the draft is `in-review` and the
   version is the one recorded by `submittedVersionId`. Approving a `working`,
   `approved`, or `exported` version is an illegal transition; approving a
   version other than the submitted one means a save raced the review, and the
   draft has already returned to `working`.
3. Pin the content hash: read `DraftVersion.hash` from the loaded version. The
   caller does not supply it. This hash is the approval target (§5.2: approval
   targets one content hash).
4. **Fact gate.** Read, through `VerifiedFactReadPort`, the state of every
   `FactChip` bound in this version's document. The **mandatory** set is the
   template's `FormTemplateField.required` fields that carry a `factBinding`
   (open decision 3, now closed). If any mandatory fact is not `verified` or
   `corrected`, or is flagged stale by `particular.evidence-stale`, block. No
   unverified mandatory fact may reach approval (Phase 7 exit gate; §9.2
   release-blocker).
5. **Blocker gate.** Read, through `CheckReadPort`, unresolved findings on this
   matter. A finding blocks when its status is `fail` or `needs-review` and it
   has no `resolved` or `waived` resolution (`check-service.md` §6). Any
   unresolved blocking finding blocks approval. A pending-applicability or stale
   mandatory step also blocks (`task-service.md` §8), read through the same
   readiness projection.
6. **Placeholder gate.** Scan the document for `lockedBlock` nodes whose bound
   `locked-prescribed` template block is still at its `placeholderText`. Any
   unresolved placeholder blocks approval (§9.2: hidden placeholder must be
   impossible).
7. Persist the Approval record (hash, approver, role, timestamp, the
   `blockers_checked` snapshot) and set the draft state to `approved` in one
   transaction. Set `Draft.approvedBy` / `Draft.approvedAt` from the same record
   so the frontend contract stays satisfied.
8. Audit `draft.approved` with actor, target version, content hash, and the
   snapshot references (invariant 8), **and** publish the `draft.approved`
   domain event through `EventPort`. Both are required: the audit row is the
   legal record, the event is what `export_service`, `notification_service`, and
   `task_service` consume. An audit write is not a publication
   (`events.md` §3).
9. Return the ApprovalRead. Export is a separate call and reads this record.

Any edit after approval is handled by `draft_service`, not here: it creates a
**new working version** (invariant, §9.2), so the existing Approval keeps
pointing at the old hash and never silently covers the changed content.

### invalidate(system_ctx, approval_id, reason) -> ApprovalRead

Not a user action. The service subscribes to `document.version-superseded` and
`particular.evidence-stale`; when either affects a fact bound in an approved
version, the Approval is marked invalidated with the reason and
`draft.approval-invalidated` is published. The Approval record itself is never
deleted or rewritten — it keeps pointing at the hash it approved, and the
invalidation is a successor fact about it.

`export_service` consumes the event and refuses to render, including for a job
already queued (`export-service.md` §8). An invalidated approval requires a new
submit and a new approval; gates are re-run from scratch.

## 6. The seams

| Seam | Direction | Contract |
| --- | --- | --- |
| `draft_service` | reads | `DraftReadPort` supplies the `in-review` version, its `hash`, and `submittedVersionId`; a post-approval edit forks a new unapproved version |
| `verification_service` | reads | `VerifiedFactReadPort` gives fact state per `FactChip.fact_id`; all mandatory facts `verified`/`corrected` or the gate blocks |
| `check_service` | reads | `CheckReadPort` gives unresolved blocking findings; any one blocks |
| `export_service` | publishes | `draft.approved` lets export run; `draft.approval-invalidated` stops it |
| `notification_service` | publishes | `draft.approved` drives the "approval recorded" notification |
| `AuditPort` | emits | The `draft.approved` audit row anchors the approval for history — separately from the event |

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Approval targets one content hash (§5.2) | `DraftVersion.hash` pinned from the loaded version, stored on Approval, never caller-supplied |
| No mandatory unverified fact reaches approval (Phase 7, §9.2) | Fact gate blocks unless every bound `FactChip` is `verified`/`corrected` |
| Unresolved blockers stop approval (Phase 5/7) | Blocker gate consults `check_service`; any unresolved blocking finding blocks |
| No hidden placeholder (§9.2) | Placeholder gate rejects any `locked-prescribed` block still at `placeholderText` |
| Only an authorised approver (inv. 3) | `draft.approve` capability plus a current practising notary; `reviewer` denied with 403 |
| Approval never covers changed content (§9.2) | Post-approval edit forks a new working version; the Approval stays pinned to the old hash; a save during review invalidates the submission pin |
| Altered locked wording cannot slip through (§9.2) | Locked-wording validation runs at save and restore in `draft_service` and is re-asserted on the pinned document before the gate passes |
| Stale evidence revokes approval | `document.version-superseded` and `particular.evidence-stale` invalidate the Approval and stop export |
| Gates are read through ports | `VerifiedFactReadPort` and `CheckReadPort`; no sibling application service is imported (plan §5.1) |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership |
| Every approval audited **and** published (inv. 8) | `AuditPort.record("draft.approved")` plus the `draft.approved` outbox event, in one transaction |

## 8. Failure modes to handle explicitly

- Concurrent approve on the same version — optimistic version column; the second
  writer sees the state already `approved` and returns the existing Approval,
  not a duplicate.
- Draft edited between gate read and commit — the loaded hash no longer matches
  the active version at commit; reject and require re-review.
- Fact verified, then its source document replaced before approval — the fact is
  flagged stale via `document.version-superseded`; the fact gate sees it as no
  longer verified and blocks.
- Approver lacks role — denied at step 1; audit the denied attempt.
- Approving an already-`exported` version — illegal transition, rejected.
- Gate read through a port times out — fail closed with 503; never approve on a
  missing verdict.
- Draft saved while it sat in `in-review` — the draft is already back in
  `working` and `submittedVersionId` is cleared, so approve rejects with an
  illegal-transition error naming the new version.
- Approved version's evidence superseded before export — the Approval is
  invalidated, the queued render is refused, and the draft must be resubmitted.

## 9. Test list

- **Unit:** the single legal transition; approve rejects `working`, `approved`,
  and `exported` sources; approve rejects a version other than
  `submittedVersionId`; each of the three gates blocks independently; the
  mandatory fact set is derived from the template's required `factBinding`
  fields; `blockers_checked` snapshot captures what was clear; the Approval is
  immutable once written.
- **Contract:** `ApprovalRead` schema; the `draft.approved` and
  `draft.approval-invalidated` event payloads against `events.md`; the 403
  `capability_denied` and 422 gate-failure shapes.
- **Integration:** submit → approve → export end to end over real PostgreSQL;
  an unverified mandatory fact blocks; an unresolved `fail` finding blocks; a
  placeholder blocks; concurrent approve returns the existing Approval rather
  than a duplicate; superseding the evidence document invalidates the Approval
  and stops a queued export; audit row and outbox event commit together.
- **Security:** a `reviewer` cannot approve; a notary without a current practice
  certificate cannot approve; cross-matter and cross-organisation approval
  denied with 404; a caller-supplied content hash is ignored; a denied attempt
  is audited.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **First-class Approval record** — the frontend has no `Approval` entity;
   approval is only `Draft.approvalState` plus `approvedBy?` / `approvedAt?`.
   Lean **add a backend Approval record** (approver, `draft_version_id`,
   `content_hash`, timestamp, blockers-checked snapshot) as the audit anchor,
   and keep the two `Draft` fields as a projection for the frontend contract.
2. **Endpoint reconciliation — closed.** The matter-scoped route is the public
   contract, resolved server-side to the `in-review` version
   (`api-conventions.md` §1).
3. **Which facts count as mandatory — closed.** The template's
   `FormTemplateField.required` fields carrying a `factBinding`. The same source
   drives `create_draft` eligibility (`draft-service.md` open decision 1).
4. **Approver role — closed on the capability, open on self-approval.** The
   capability is `draft.approve`, held by `approver` and requiring a current
   practising notary (`security-model.md` §3.2, §3.3). Whether the drafting
   lawyer may approve their own draft is a firm-policy decision: lean
   **allow it in a solo organisation, and make four-eyes configurable per
   organisation**, since a sole practitioner has no second approver.
5. **Re-approval after edit — closed.** Every gate re-runs from scratch. A new
   hash is a new instrument, and no prior gate result is inherited.
