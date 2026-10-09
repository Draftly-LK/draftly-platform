# verification-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `document-service.md`,
`document-processing.md`, and `memory-service.md`. This service is the
**authoritative fact tier** — the gate where a machine candidate becomes a
lawyer-verified fact. `memory-service` sits underneath it; a fact enters a draft
only from here.

Maps to plan **Phase 4** (verification and structured matter record), API rows
**Particulars** (§7), the trust-boundary row *Verified matter record* (§5.2), and
state invariants 1–4 (§5.3).

## 1. What it owns

Turning **non-authoritative candidate particulars** — the fields
`document-processing` extracted, with their source spans, confidence, and
two-engine reconciliation — into **verified or corrected facts** that carry a
lawyer's decision, a preserved extracted value, and a correction history. It owns
the verified matter record: current title, parcel, parties, instrument,
interests, and the evidence each one hangs on.

It does **not** run OCR or extraction (`document-processing` does), does **not**
store the original bytes or sign evidence URLs (`document_service` does), and does
**not** run consistency checks over the record (`check_service` does). It also
does not decide what a candidate should say — a machine value is a suggestion
until a lawyer accepts, corrects, or rejects it.

## 2. Where it sits

```text
GET  /api/matters/{id}/facts                    ─┐
POST /api/matters/{id}/facts/{factId}/verify    ─┤
POST /api/matters/{id}/facts/{factId}/correct   ─┼─→ api/v1/particulars.py ─→ application/verification_service.py
POST /api/matters/{id}/facts                    ─┘                                          │
                                                                                           │ orchestrates
document-processing candidates ──(extraction event)──────────────────────────────────────▶│
                                                                                           ▼
                                                    ports: ParticularRepository, DocumentReadPort,
                                                           EventPort, AuditPort
```

The router authenticates and parses only. The service takes an
already-authenticated `RequestContext` (actor, roles, matter memberships) and
orchestrates domain plus ports. It imports no SQLAlchemy, no FastAPI, no Google
SDK. Evidence bytes are never reached here — the service returns an
`EvidenceSpan`, and the UI resolves the page image through `document_service`'s
short-lived signed URL (the read seam in §6).

The frontend calls these `facts`; the plan API surface (§7) and the `particulars`
router name them **particulars**. Same entity, two names — reconciled in open
decisions.

## 3. Domain models it needs

In `domain/particulars.py`, mirroring the frontend `VerifiedFact` contract
(`frontend/src/types/fact.ts`) field for field so the API needs no translation
layer:

- **VerifiedFact** — `id`, `matterId`, `key`, `labelKey`, `section`,
  `value: FactValue`, `extractedValue: FactValue`, `evidence?: EvidenceSpan`,
  `confidence`, `verificationState: VerificationState`, `reviewerId?`,
  `reviewedAt?`, `changes: FactChange[]`, `conflicts?: FactConflictCandidate[]`,
  `manualReason?`. `value` is the current accepted value; `extractedValue` is what
  the machine read and is **never overwritten** (invariant 2).
- **FactChange** — `id`, `before: FactValue`, `after: FactValue`, `reason`,
  `actorId`, `timestamp`. The correction trail; append-only.
- **FactConflictCandidate** — `value: FactValue`, `evidence: EvidenceSpan`,
  `confidence`. The competing reading, carried so both sides of a disagreement
  are shown.
- **EvidenceSpan** — `documentId`, `page`, `region?{x,y,width,height}`,
  `charRange?{start,end}`, `snippet`. The `documentId` binds to an immutable
  `DocumentVersion` (invariant 1). Defined in `domain/evidence.py`, shared with
  `check_service`.

`FactValue = string | number | boolean | null`.
`VerificationState = unreviewed | verified | corrected | conflict | blocked`.

One state machine, enforced in the domain layer so the first tests hit it without
a database:

```text
                 ┌───────────────→ verified ──(correct)──┐
unreviewed ──────┤                                       ├──→ corrected
                 └─→ conflict ──(resolve to one value)───┘
   │
   └────────────→ blocked   (evidence missing or unreadable; no verify allowed)
```

`unreviewed` is the seeded candidate state. `conflict` is set at seed time when
reconciliation carried two readings (§5). `blocked` holds any candidate whose
evidence cannot be opened. An illegal transition raises a domain error, not an
HTTP error.

## 4. Ports it depends on

In `ports/`:

- `ParticularRepository` — persist and load `VerifiedFact`, append `FactChange`,
  matter-scoped queries only, with an optimistic version column (plan §7,
  Particulars: optimistic concurrency).
- `DocumentReadPort` — resolve an `EvidenceSpan`'s `documentId` to a live,
  matter-scoped `DocumentVersion` and confirm it is readable. Backed by
  `document_service`; this service does not sign URLs itself.
- `EventPort` — publish domain events (§7 seam). Drained through the same outbox
  pattern `document_service` uses, so an event is never lost and never fires for
  a fact the database does not have.
- `AuditPort` — `record(event)`; every verification decision, correction, manual
  add, and block goes through here (invariant 8).

## 5. Consuming candidates and reconciliation (the critical seam)

The candidate fields and the Document-AI-vs-Gemini reconciliation from
`document-processing.md` §7 land **here**, unchanged in meaning:

| document-processing §7 outcome | Seeded VerifiedFact |
| --- | --- |
| high confidence, one reading | `extractedValue` set, `verificationState = unreviewed` |
| both engines agree | `extractedValue` set, `confidence` raised, `unreviewed` |
| engines disagree (`4471` vs `4474`) | `extractedValue` = Document AI value; `conflicts = [{value: gemini, evidence, confidence}]`; `verificationState = conflict` |
| recovered (Document AI missing, Gemini read) | `extractedValue` = recovered value, low `confidence`, `unreviewed` (priority review) |
| unreadable / handwriting (Level 3) | no machine value; `verificationState = blocked`, page still shown |

`ingest_candidates(system_ctx, matter_id, candidates)` subscribes to
**`document.extraction-completed`** and creates these
`unreviewed`/`conflict`/`blocked` rows. That event is distinct from
`document.processing-completed`, which says derivatives exist and is what the
document-requirement projection consumes; extraction completing is what produces
candidates. This document previously named "the extraction-completion event",
which no service published (`events.md` §5.4).

This is the only path that writes a machine value, and it writes it as a
candidate — **no provider response ever sets a fact to verified** (Phase 3 exit
gate, restated here as the entry rule of Phase 4).

The `conflict` state is exactly the Document-AI-vs-Gemini disagreement made
reviewable: the lawyer sees "Document AI 4471 (low) / Gemini 4474" beside the
cropped image (`extractedValue` and `conflicts[0].value`, each with its own
`EvidenceSpan`) and picks one. Resolving a conflict is a `verify` (accept
`extractedValue`) or a `correct` (choose the conflict value or type a new one).

## 6. The methods

### list_facts(ctx, matter_id) -> FactRead[]

Matter-scoped read. Re-check membership from the repository; do not trust the
router. Returns every `VerifiedFact` with its state, `extractedValue`, `value`,
`conflicts`, `changes`, and `evidence`. If the actor is not a member, return
**404, not 403** (Phase 2 exit gate). Each returned `evidence` is a span the UI
resolves to a page image through `document_service` — this service returns no raw
storage path.

### verify_fact(ctx, matter_id, fact_id) -> FactRead

The accept decision.

1. Role gate: only an authorised lawyer may verify (invariant 3). A clerk is
   refused (Phase 2 exit gate). The refusal is a policy error, not a 404 to a
   matter member.
2. Optimistic-concurrency check against the version the client read.
3. Resolve `evidence` through `DocumentReadPort`. If the span's `documentId` is
   missing, superseded to an unreadable state, or has no readable region, the
   fact goes to `blocked` and verification is refused — **missing or unreadable
   evidence stays blocked** (Phase 4 exit gate).
4. Set `verificationState = verified`, `reviewerId = actor`, `reviewedAt = now`.
   `value` takes the accepted reading; `extractedValue` is untouched.
5. Audit `particular.verified` with actor, target, and the evidence reference.

### correct_fact(ctx, matter_id, fact_id, after, reason) -> FactRead

The change decision, and the successor-value rule (invariant 2).

1. Role gate and optimistic-concurrency check as above.
2. Append `FactChange{ before: current value, after, reason, actorId: actor,
   timestamp: now }` to `changes`. The array is append-only; a correction never
   rewrites an earlier entry.
3. Set `value = after`, `verificationState = corrected`, `reviewerId`,
   `reviewedAt`. **`extractedValue` is preserved** — the machine's original
   reading survives every correction, so the record shows what was read and what
   the lawyer changed it to.
4. Emit the invalidation event (§7). Audit `particular.corrected` with before and
   after references (invariant 8).

Rejection has no separate frontend endpoint. Rejecting a machine candidate is a
correction that moves `value` off `extractedValue` (to `null` or the right
value); it emits the same invalidation event. Whether a hard "discard this
candidate" state is also needed is an open decision.

### add_fact(ctx, matter_id, draft) -> FactRead

Manual entry — the Level 3 path where no machine value exists.

1. Role gate.
2. Create a `VerifiedFact` with `manualReason` set, `extractedValue = null`
   (there was no extraction), and the lawyer's `value`.
3. If the lawyer attaches an `EvidenceSpan` (typically a page-level span on the
   document shown for manual entry), the fact can be `corrected`/`verified`
   normally; the span still binds to a `DocumentVersion` (invariant 1). Whether a
   manual fact may exist with no evidence at all is an open decision (invariant 1
   pressure).
4. Audit `particular.added` with `manualReason`.

## 7. Events it emits (the memory seam)

The service publishes `particular.verified`, `particular.corrected`,
`particular.added`, `particular.blocked`, and `particular.evidence-stale`
(`events.md` §5.6). Payloads carry **references**, not values: a corrected
particular is private matter content and must not travel in an event body
(`events.md` §2).

`particular.corrected` is the seam `memory-service.md` §8 subscribes to: session
memory derived from the old value is invalidated and marked superseded, not
deleted. `verification_service` does not reach into memory itself — it emits,
memory reacts. It is the downward-propagation half of the two-tier rule
(`memory-service.md` §3).

`particular.evidence-stale` is published when `document.version-superseded`
flags a fact sourced from the replaced version. `approval_service` consumes it
and invalidates any Approval bound to that fact
(`approval-service.md` §5), so a superseded deed cannot silently sit behind an
approved instrument.

The verified/corrected set is also the read source for `draft_service`: a final
draft references only `verified` or `corrected` facts (invariant 4). This service
exposes which facts qualify; `draft_service` enforces the binding at approval.
Naming that seam here keeps the enforcement point unambiguous.

## 8. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Source span on every accepted fact (inv. 1) | `verify`/`correct` require a readable `EvidenceSpan` whose `documentId` resolves to an immutable `DocumentVersion`; otherwise `blocked` |
| Correction keeps the extracted value (inv. 2) | `correct_fact` appends a `FactChange` and sets `value`; `extractedValue` is never overwritten |
| Only a lawyer verifies (inv. 3) | Role gate on `verify`, `correct`, `add`; a clerk is refused |
| Draft uses only verified/corrected facts (inv. 4) | This service marks the state; `draft_service` binds against it at approval |
| Machine value never self-verifies | `ingest_candidates` only writes `unreviewed`/`conflict`/`blocked` |
| Conflicts stay reviewable | Both readings kept (`extractedValue` + `conflicts[]`), each with its own span |
| Every decision audited (inv. 8) | `AuditPort.record` on verify, correct, add, and block, with before/after references |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership; a cross-organisation resource is a 404 (`security-model.md` §2) |
| Matter isolation | Membership re-checked; 404 hides existence |

## 9. Failure modes to handle explicitly

- **Evidence document superseded after seeding** — `document.version-superseded`
  (from `document_service`) flags facts sourced from the old version; they need
  re-review against the successor before they can be verified.
- **Verify on a fact whose evidence went unreadable** — transition to `blocked`,
  refuse the decision, surface why.
- **Concurrent verify and correct on the same fact** — optimistic-concurrency
  column rejects the stale write; the client re-reads.
- **Conflict resolved to a value matching neither reading** — a legitimate
  correction; recorded as a `FactChange`, both original readings retained.
- **Candidate ingested twice** (worker retry) — idempotent on
  `(matter_id, key, source version)`; a re-ingest does not overwrite a fact a
  lawyer has already touched.

## 10. Phase 4 exit gates and how they are met

- **Every accepted fact opens the correct source version and page/region** — the
  `EvidenceSpan` on each `verified`/`corrected` fact resolves through
  `DocumentReadPort` to the exact `DocumentVersion`, page, and region.
- **Verified/corrected transitions require the correct role** — §6 role gates.
- **Missing or unreadable evidence remains blocked** — §6 step 3.
- **The record rebuilds from persisted versions without changing decisions** —
  `value`, `extractedValue`, and the full `changes[]` trail are persisted; a
  rebuild replays them, and the decisions (reviewer, timestamp, before/after)
  come back identical.

## 11. Test list

- **Unit:** state-machine transitions (unreviewed → verified/conflict/blocked →
  corrected); correction appends a `FactChange` and preserves `extractedValue`;
  role gate refuses a clerk; verify on unreadable evidence blocks; conflict
  seeding from a reconciliation disagreement; illegal-transition rejection.
- **Contract:** `facts` list/verify/correct/add response schemas match
  `VerifiedFact`; the extraction-event candidate schema; the emitted
  `particular.corrected` event schema.
- **Integration:** ingest candidates from a processing run → verify → correct over
  real PostgreSQL; `document.version-superseded` flags dependent facts;
  `particular.corrected` reaches `memory-service`; rebuild the record from
  persisted versions and confirm identical decisions.
- **Security:** cross-matter fact read and verify denied; 404-not-403 existence
  hiding; clerk cannot verify, correct, or add; no raw client value in logs.

## 12. Open decisions

### Scoped read contract (2026-10-09)

The approved lawyer-led workflow adds `transaction_id`, `scope_status`, and
`evidence_stale` to fact versions. Existing rows are explicitly
`legacy-unassigned`; migration does not invent subjects or transaction roles.
`ConfirmedFactValue` carries transaction and subject references, and
`FactTierSummary.scoped_confirmed` preserves eligible values in each scope.
The compatibility `confirmed` map omits unresolved competing values, stale
facts, and explicitly unassigned facts. It withholds the entire map when
eligible values span transaction/subject scopes, including different fact types
or a mixture of legacy and assigned scopes. Existing form consumers cannot
select a coherent scope; this temporary withholding can produce missing
bindings even for individually confirmed facts. `scoped_confirmed` stays
lossless for the later explicit resolver.
A later version alone never resolves conflicting live values. Version allocation
is scoped by user, matter, transaction, subject, and fact type. Existing
unambiguous legacy single-subject reads remain compatible.

`evidence_stale` is an additive eligibility seam for document interpretation
invalidation; interpretation refresh and downstream propagation are separate
workflow work. V0 uses the approved user/matter boundary; organization support
is deferred.

### Canonical register commands (2026-10-09)

The approved lawyer-led workflow supersedes the earlier proposed manual/reject
defaults below. The canonical owner is verification. `GET /matters/{matterId}/facts`
merges document-owned processing observations and persisted fact successors.
Lists and `GET /facts/{factId}/history` use signed cursors, default 50/100 and
maximum 100 rows. History is chronological and retains machine originals,
corrections, rejection, reasons, reviewers, timestamps and resolved alternatives.
The register exposes `origin`, `originalValue`, `sourceCandidateId`, `lineageId`,
transaction/subject references, `scopeStatus`, `evidenceStale`, `scopeToken`,
`conflictFactIds`, predecessor and successor IDs. Historical IDs stay addressable.
Any canonical candidate materialization suppresses its processing observation
from live lists, including a resolved loser with no live successor of its own.

`POST /matters/{matterId}/facts` creates a lawyer-provided `REVIEW_REQUIRED` fact
with a required reason; evidence is optional and author identity grants no
approval. `POST /facts/{factId}/{accept|correct|reject|associate}` requires
`Idempotency-Key` and `If-Match` (the integer version in quotes). Correction,
rejection and association require reasons. Association creates an unverified
successor and requires matter-owned references. Acceptance/correction requires
assigned scope, current readable evidence, current `expectedScopeToken`, and
the exact set of differing live alternatives in `resolveFactIds` with a reason.
An arriving competing fact changes the token and refuses the stale decision.
Negative conclusions retain the current-search-evidence guard; a search must
be eligible in the exact same transaction and subject. Another scope's search
or an ambiguous legacy relationship cannot satisfy it.

Only `associate` accepts `transactionId` and `subjectId`. Other actions reject
those fields with 422, including explicit nulls, matching IDs, mismatching IDs,
and foreign IDs. To assign an observation, associate using its current ETag and
a reason; then accept the returned successor ID with its ETag and `scopeToken`
as `expectedScopeToken`. Acceptance omits scope fields. Association returns the
destination scope's token, so no destination-token endpoint or client-generated
hash is needed. Reload only when a later competing change makes that token stale.

All mutations authorize the current RTA capability and practising status inside
the application service, including replay. The matter lock serializes review
and scope writes; shared `SqlIdempotencyStore` fingerprints the request. Retries
return the same fact ID without another successor/decision. The returned row
reflects later supersession if that result has since been reviewed again.
Audit events contain reference IDs, with decision text confined to verification.
Mutation, decision, audit and replay records share the request transaction.

Document review delegates edit/approval to these same policies. Its stable
candidate adapter prevents retries following a newer successor into a second
decision. An edit remains unverified; editing a confirmed fact requires canonical
correction. Document-owned machine rows and immutable source bytes are preserved.

`DocumentFactPort` validates user/matter, immutable source hash, page bounds,
candidate version/relationship, current source and document interpretation, and
readable original/page artifacts. Evidence returns actual OCR text and page
precision; text precision requires an exact supporting substring. No bounding
box is synthesized. Every existing linked source is revalidated before acceptance.
The complete source/page grouping must match the extraction. An old single-source
extraction cannot justify a regrouped document that now includes another source.
Optional unavailable OCR yields empty text and page precision when the original
and page remain readable. Missing or corrupt original/page artifacts become
unavailable candidate rows (`evidenceStale=true`, no evidence), keeping other
register entries visible. Correction commands also invalidate already persisted
fact evidence through the owning public port in the same matter transaction.

NIC fields are holder observations: `holderNic`, `holderNameEn`, `holderNameSi`,
`holderDateOfBirth`, `holderAddress`; survey plans retain `surveyorRegistration`.
They introduce no global required-form facts. They remain subject to explicit
human evidence review and practising authorization. Existing role-specific
critical identity types/capabilities and prescribed form mappings are unchanged;
a later explicit role binding must preserve their critical policy. Legacy NIC
`transfereeNic` is an observational alias only when the source owner identifies
the document as NIC. The reviewed migration preserves historical types, values
and decisions, attaches original candidate metadata, and marks that narrow
legacy NIC set unassigned. Register reads display the holder alias; the confirmed
projection withholds it until explicit association/review. Downgrade removes
additive columns/tables but keeps that conservative `scope_status` withholding.

`FactEvidenceInvalidationPort` uses `FactEvidenceInvalidation` references and
existing `evidence_stale` eligibility flags. It invalidates exact dependent
document/source/run evidence, including transitive derived facts, while
preserving reviewed values, versions and decision history. Evidence pins the
interpretation generation as well as the original source/page/hash. Reusing the
same bytes or returning to an earlier class never renews historical authority.
New manual page evidence can reference a current unsupported interpretation;
acceptance still applies the existing critical-fact source policies. See the
[document correction contract](document-service.md#october-2026-interpretation-and-page-accounting-implementation).
Richer check/readiness recomputation and role binding remain subsequent tasks.

### Earlier decisions

Recommended defaults in bold; confirm or override before coding.

1. **ParticularVersion rows** — the frontend has no separate version entity;
   versioning *is* the `changes: FactChange[]` trail. The plan (Phase 1) lists a
   `ParticularVersion`. Lean **keep `changes[]` as the source of truth and
   project explicit `ParticularVersion` rows for the draft-binding join
   (invariant 4)**, so a draft can pin an exact value version without denormal:
   `changes[]` stays the history, `ParticularVersion` is the addressable handle.
2. **`facts` versus `particulars` naming** — frontend says `facts`, plan/API says
   `particulars`. Lean **keep the frontend `facts` route surface and the domain
   name `particulars` internally**, mapped once in the router; do not rename the
   published frontend contract.
3. **Explicit reject state** — model rejection as a correction (default) or add a
   discard state distinct from `blocked`? Lean **correction to `null` for V0**;
   revisit if lawyers need "candidate was wrong" separated from "value is empty".
4. **Manual fact without evidence** — invariant 1 wants a source span on every
   accepted fact. Lean **require at least a page-level `EvidenceSpan` for a manual
   fact**, using the document shown at entry; allow a truly evidence-free fact
   only behind an explicit, audited `manualReason` override.
5. **Conflict resolution UI contract** — whether the API needs a distinct
   `resolve-conflict` call or `verify`/`correct` cover it. Lean **reuse
   `verify`/`correct`**; the `conflict` state and `conflicts[]` array already
   carry what the UI needs.

### Downstream freshness after canonical decisions (2026-10-09)

Canonical successor decisions notify the existing public check/form invalidation
ports inside the shared matter transaction. Superseded/resolved exact fact IDs and
confirmed peers withheld by new competing observations invalidate dependent outputs.
A newly competing manual fact is still review required; it does not replace a
confirmed winner silently. Unrelated bound fact IDs remain unaffected. Approved
artifacts, rendered values, bindings and decision history remain retained while
the form owner marks the output stale. FactTierSummary also exposes lossless scoped
conflict tuples so explicit scoped consumers do not borrow matter-wide conflicts.

### Confirmed conversation proposals (2026-10-09)

`ReviewFactInput` is published from `verification.contracts` and remains imported
at the existing review-service path for compatibility. `authorize_decision` exposes
the owning service's existing fact-specific capability and practising checks.
The conversation uses these only for an explicit lawyer-confirmed acceptance card;
it cannot directly mutate candidates or assert a reviewed value. Confirmation
pins the exact candidate version, scope token and selected conflict IDs and uses
an action-specific idempotency key. The canonical `decide` command remains the
owner of evidence checks, immutable successor creation, audit and invalidation.
Authorization is repeated before replaying an executed proposal result.
