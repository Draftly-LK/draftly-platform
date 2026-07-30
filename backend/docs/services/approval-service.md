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
POST /api/matters/{id}/drafts/{draftId}/approve ─┐
  (frontend contract)                            │
POST /draft-versions/{id}/approve ───────────────┼─→ api/v1/drafts.py
  (plan §7 API surface)                          │        │
GET  /draft-versions/{id}/approval ──────────────┘        │ → application/approval_service.py
                                                           │
                                                           │ reads
                                    verification_service ──┤ (fact states)
                                    check_service ─────────┤ (blockers)
                                    draft_service ─────────┤ (version + hash)
                                                           ▼
                                    ports: ApprovalRepository, DraftRepository,
                                           AuditPort, ClockPort
```

The router authenticates and parses only. The service takes an
already-authenticated `RequestContext` (actor, roles, matter memberships) and
orchestrates domain plus ports. It imports no SQLAlchemy, no FastAPI, and no
rendering SDK.

Note the endpoint mismatch, resolved in §9. The frontend posts to
`/api/matters/{id}/drafts/{draftId}/approve` and today only flips
`Draft.approvalState` to `"approved"` and stamps `approvedBy` / `approvedAt` in
the demo store — no gate runs. The plan §7 API targets a specific version:
`POST /draft-versions/{id}/approve`. The backend approves a **version**, and the
matter-scoped route resolves to the draft's active version.

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

- `ApprovalRepository` — persist and load Approval records; matter-scoped
  queries only; one active approval per content hash.
- `DraftRepository` — load the `DraftVersion` (id, hash, document) and its
  current state; the service never trusts a hash supplied by the caller.
- `AuditPort` — `record(event)`; the approval event is a material mutation
  (invariant 8).
- `ClockPort` — the approval timestamp; injected so tests are deterministic.

Fact and blocker states are read through the sibling application services
(`verification_service`, `check_service`), not through new ports — those
services already own the authoritative read path.

## 5. The method

### approve(ctx, draft_version_id) -> ApprovalRead

1. Re-check matter membership and approver role from the repository; do not
   trust the router. Only an authorised approver role may approve (invariant 3);
   a clerk cannot (Phase 2 exit gate). Reject with the role error otherwise.
2. Load the `DraftVersion`. Reject unless the draft is `in-review`. Approving a
   `working`, `approved`, or `exported` version is an illegal transition.
3. Pin the content hash: read `DraftVersion.hash` from the loaded version. The
   caller does not supply it. This hash is the approval target (§5.2: approval
   targets one content hash).
4. **Fact gate.** Ask `verification_service` for the state of every `FactChip`
   bound in this version's document. If any mandatory fact is not `verified` or
   `corrected`, block. No unverified mandatory fact may reach approval (Phase 7
   exit gate; §9.2 release-blocker).
5. **Blocker gate.** Ask `check_service` for unresolved findings on this
   matter/version. Any unresolved blocking finding blocks approval (Phase 5 and
   Phase 7 exit gates).
6. **Placeholder gate.** Scan the document for `lockedBlock` nodes whose bound
   `locked-prescribed` template block is still at its `placeholderText`. Any
   unresolved placeholder blocks approval (§9.2: hidden placeholder must be
   impossible).
7. Persist the Approval record (hash, approver, role, timestamp, the
   `blockers_checked` snapshot) and set the draft state to `approved` in one
   transaction. Set `Draft.approvedBy` / `Draft.approvedAt` from the same record
   so the frontend contract stays satisfied.
8. Audit `draft.approved` with actor, target version, content hash, and the
   snapshot references (invariant 8).
9. Return the ApprovalRead. Export is a separate call and reads this record.

Any edit after approval is handled by `draft_service`, not here: it creates a
**new working version** (invariant, §9.2), so the existing Approval keeps
pointing at the old hash and never silently covers the changed content.

## 6. The seams

| Seam | Direction | Contract |
| --- | --- | --- |
| `verification_service` | reads | fact state per `FactChip.fact_id`; all mandatory facts `verified`/`corrected` or the gate blocks |
| `check_service` | reads | unresolved blocking findings for the version; any one blocks |
| `draft_service` | reads / triggers | supplies the `DraftVersion` + `hash`; a post-approval edit forks a new unapproved version |
| `export_service` | hands off | reads the Approval record; renders only an `approved` version pinned to its hash |
| `AuditPort` | emits | `draft.approved` event anchors the approval for history |

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Approval targets one content hash (§5.2) | `DraftVersion.hash` pinned from the loaded version, stored on Approval, never caller-supplied |
| No mandatory unverified fact reaches approval (Phase 7, §9.2) | Fact gate blocks unless every bound `FactChip` is `verified`/`corrected` |
| Unresolved blockers stop approval (Phase 5/7) | Blocker gate consults `check_service`; any unresolved blocking finding blocks |
| No hidden placeholder (§9.2) | Placeholder gate rejects any `locked-prescribed` block still at `placeholderText` |
| Only an authorised approver (inv. 3) | Role re-checked from the repository; clerk denied |
| Approval never covers changed content (§9.2) | Post-approval edit forks a new working version; the Approval stays pinned to the old hash |
| Altered locked wording cannot slip through (§9.2) | Locked-wording check (owned with `check_service`) must be clear before the gate passes |
| Every approval audited (inv. 8) | `AuditPort.record("draft.approved")` with actor, hash, and snapshot |

## 8. Failure modes to handle explicitly

- Concurrent approve on the same version — optimistic version column; the second
  writer sees the state already `approved` and returns the existing Approval,
  not a duplicate.
- Draft edited between gate read and commit — the loaded hash no longer matches
  the active version at commit; reject and require re-review.
- Fact verified, then its source document replaced before approval — the fact is
  flagged stale via `document.version_superseded`; the fact gate sees it as no
  longer verified and blocks.
- Approver lacks role — denied at step 1; audit the denied attempt.
- Approving an already-`exported` version — illegal transition, rejected.
- Gate read from a sibling service times out — fail closed; never approve on a
  missing verdict.

## 9. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **First-class Approval record** — the frontend has no `Approval` entity;
   approval is only `Draft.approvalState` plus `approvedBy?` / `approvedAt?`.
   Lean **add a backend Approval record** (approver, `draft_version_id`,
   `content_hash`, timestamp, blockers-checked snapshot) as the audit anchor,
   and keep the two `Draft` fields as a projection for the frontend contract.
2. **Endpoint reconciliation** — the frontend posts to
   `/api/matters/{id}/drafts/{draftId}/approve`; plan §7 targets
   `/draft-versions/{id}/approve`. Lean **keep the matter-scoped route as the
   public contract** and resolve it server-side to the draft's active version,
   which is what actually gets pinned.
3. **Which facts count as mandatory** — the `FactChip` node carries only
   `fact_id` and `verification_state`; mandatoriness comes from the template
   field binding (`FormTemplateField.required` / `factBinding`). Confirm the
   source of the mandatory set before wiring the fact gate.
4. **Approver role model** — the exact role name authorised to approve (and
   whether the drafting lawyer may approve their own draft) is a Phase 2 policy
   decision, recorded here as pending.
5. **Re-approval after edit** — whether a forked version inherits any prior
   gate results or re-runs every gate from scratch. Lean **re-run all gates**;
   a new hash is a new instrument.
