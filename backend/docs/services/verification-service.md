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

`ingest_candidates(system_ctx, matter_id, candidates)` subscribes to the
extraction-completion event `document-processing` emits and creates these
`unreviewed`/`conflict`/`blocked` rows. This is the only path that writes a
machine value, and it writes it as a candidate — **no provider response ever sets
a fact to verified** (Phase 3 exit gate, restated here as the entry rule of
Phase 4).

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

On any correction or rejection, this service publishes
**`particular.corrected`** (carrying `matterId`, `fact_id`/`key`, `before`,
`after`, `actorId`) through `EventPort`. This is the seam `memory-service.md` §8
subscribes to: session memory derived from the old value is invalidated and
marked superseded, not deleted. `verification_service` does not reach into memory
itself — it emits, memory reacts. It is the downward-propagation half of the
two-tier rule (`memory-service.md` §3): corrections in the authoritative tier
flow down and invalidate stale working memory.

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
| Matter isolation | Membership re-checked; 404 hides existence |

## 9. Failure modes to handle explicitly

- **Evidence document superseded after seeding** — `document.version_superseded`
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
  real PostgreSQL; `document.version_superseded` flags dependent facts;
  `particular.corrected` reaches `memory-service`; rebuild the record from
  persisted versions and confirm identical decisions.
- **Security:** cross-matter fact read and verify denied; 404-not-403 existence
  hiding; clerk cannot verify, correct, or add; no raw client value in logs.

## 12. Open decisions

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
