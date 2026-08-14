# audit_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `auth-service.md`,
`document-service.md`, and `memory-service.md`. One markdown per service under
`backend/docs/services/`.

Maps to plan **invariant #8** (§5.3), the *Audit* trust-boundary row (§5.2),
and the Audit API row (§7). This service is **cross-cutting**: every other
service writes to it, and the activity and history screens read from it.

It is the append-only record of every material mutation. It is the product's
**legal defensibility** — when a notary is asked how a fact reached a draft,
the answer comes from here.

## 1. What it owns

The **append-only event log**. It owns one write path — `AuditPort.record` —
that every application service calls after a material mutation, and one
read path — a matter-scoped or global timeline — that the activity and history
screens consume. It assigns server-side ids and timestamps, records actor,
target, before/after references, reason where required, and a correlation id.

It does **not** decide whether a mutation is legal (the mutating service does),
does **not** hold matter content beyond the before/after references, and offers
**no** update or delete on the write side. There is no "edit event" and no
"delete event" for ordinary users — that is the whole point of an audit log.

## 2. Where it sits

```text
every application service, every worker, every webhook handler
        │
        └─→ AuditPort.record(event) ─→ application/audit_service.py
                (write, append-only)             │
                                                 ▼
                              ports: AuditRepository (insert-only)

GET /api/v1/matters/{id}/audit ──→ api/v1/audit.py ──→ paginated matter timeline
GET /api/v1/history            ──→ (optional matterId) ──→ user-scoped feed
```

Writers include `auth_service`, `billing_service`, `matter_service`,
`party_service`, `document_service`, `verification_service`, `check_service`,
`task_service`, `obligations_service`, `draft_service`, `approval_service`,
`export_service`, `notarial_register_service`, `content_governance_service`,
`corpus_governance_service`, `research_service`, `voice_service`,
`notification_service`, and `retention_service`. That breadth is why the
domain model in §3 cannot be the frontend's matter-only shape.

`AuditPort` is the name every other service doc references. Services never
write audit rows directly; they call `AuditPort.record(event)` and the audit
service owns id assignment, timestamping, and append-only persistence behind
`AuditRepository`. The read routers are query-only. The service imports no
FastAPI and no SQLAlchemy.

## 3. Domain model it needs

In `domain/audit.py`:

```text
AuditEvent
  id                 # server-assigned
  userId             # REQUIRED — owning notary account (tenancy key)
  matterId?          # nullable
  actor?             # null only for scheduler- and provider-originated events
  action             # closed enum, §3.2
  targetType         # closed enum, §3.1
  targetId
  before?            # typed reference + diff, never a full object copy
  after?
  reason?            # required for the actions listed in §5
  correlationId
  causationId?
  prevHash           # §3.3
  hash
  timestamp          # server clock
```

`id`, `timestamp`, and `hash` are **server-assigned** on `record`, never
supplied by the caller. `actor` comes from the authenticated `RequestContext`
(`auth-service.md`), never from the request body.

### 3.1 The target type enum is wider than the frontend's

The frontend `AuditTargetType` (`src/types/audit.ts`) is
`matter | document | fact | check | workflow-step | answer | draft |
permission`. That set **cannot express most of what the other service docs
promise to audit**: billing writes subscription changes, obligations writes
user- and firm-scoped events, content-governance writes definition transitions,
corpus-governance writes source approvals, export writes render events, party
writes identity access, and voice writes transcript confirmations. Several of
those also have no matter at all, which the frontend's required `matterId`
forbids.

The backend enum is therefore the contract, and the frontend enum is a **read
projection** of it:

```text
AuditTargetType =
  matter | document | instrument | fact | check | workflow-step |
  answer | draft | approval | export | permission | party |
  obligation | notification | content-definition | legal-source |
  subscription | transcript | user | retention
```

The history screen filters to the eight values it renders today and shows the
rest under a generic row until the frontend type is widened
(`frontend-contract-migration.md`).

`matterId` is nullable. `userId` is not: every event belongs to exactly one
user account, including account, billing, and compliance events
(`security-model.md` §2).

### 3.2 Action is a closed enum, not a free string

The demo store sets `action` ad hoc per call (`"document.uploaded"`,
`"fact.corrected"`). A free string fragments the history on the first typo and
makes the feed unfilterable. The backend defines a closed enum in
`domain/enums.py`, and every service maps its mutations to a member of it. An
unknown action is rejected by `record`, not silently written.

Audit action names deliberately mirror the event registry names
(`events.md`) where an event exists for the same mutation, but the two are
separate mechanisms: some audited actions publish no event (a privileged read),
and some events carry no audit row (a projection refresh).

### 3.3 Hash chaining

Append-only prevents ordinary edits; it does not prove the log was not altered
out of band. Each event stores `prevHash` (the `hash` of the previous event in
its user's chain) and `hash` over its own canonical serialisation plus
`prevHash`. Any retroactive change breaks the chain from that point, and a
verification sweep detects it. Chains are per `user_id` so one account's volume
does not serialise another's writes.

## 4. Frontend contract and what changes

The frontend already exercises both sides against the demo store:

**Read.** `getAuditEvents(matterId?)` (`src/lib/data.ts`, marked
`TODO(api): GET /api/history`) returns the event list, optionally filtered by
`matterId`. So the read API is a single endpoint with an optional filter:

- with `matterId` → the **per-matter timeline** (plan §7 `GET
  /matters/{id}/audit`);
- without → the **global feed** across matters the actor may see.

**Write.** `appendEvent` in `demo-store.ts` is the in-store bus that **every
mutation calls** — create matter, add/replace document, verify/correct fact,
resolve check, complete step, create/approve/export draft, record assistant
action. In production this bus becomes `AuditPort.record`.

**What becomes real.** The demo assigns **deterministic** ids and timestamps:

- ids are `audit-live-NNN` (`eventId` pads the running count:
  `audit-live-001`, `audit-live-002`, …);
- timestamps are `deterministicTimestamp(count)` —
  `2026-07-22T10:{count}:00Z`, one synthetic minute per event;
- `actor` is hardcoded to `DEMO_USER_ID`.

In production all three are server-owned: ids are unique and unforgeable,
timestamps are the real server clock, and `actor` is the authenticated
identity — **not** a hardcoded demo id. Call this out so nobody carries the
deterministic scheme into the real store.

**The global feed is not wired yet.** The history screen
(`components/activity/history-screen.tsx`) renders a **hardcoded** four-item
resume list, not `getAuditEvents`. Wiring the global feed to the real audit
read is Phase 8 frontend-integration work; the backend must expose it first.

## 5. The write path — AuditPort.record

```text
AuditPort.record(event) →
  1. actor  ← RequestContext (never the request body)
  2. id     ← server-assigned, unique
  3. timestamp ← server clock
  4. require correlation_id; require reason where the mutation demands one
  5. append to AuditRepository (insert-only; no update, no delete)
```

Invariant #8 (§5.3) requires every material mutation to write an event with
**actor, target, before/after references, reason where required, and a
correlation id**. The correlation id ties the events of one logical operation
together (an upload and its processing outcome; a correction and the facts it
touched). Reason is mandatory where the plan demands it — corrections,
overrides, approvals — and the write is rejected without it.

A missing audit event is a **release-blocker** (§9.2): the backend cannot be
accepted if any material mutation reaches the store without a matching event.
So `record` participates in the **same database transaction** as the mutation
it records — either both commit or neither does. An audit write is not
best-effort fire-and-forget.

### 5.1 What "same transaction" means for workers and webhooks

Draftly is a modular monolith on one PostgreSQL database, so a service calling
`AuditPort.record` inside its own unit of work is a genuine shared transaction,
not a distributed one. Three cases need stating because they commit outside the
originating HTTP request:

| Case | Rule |
| --- | --- |
| Worker job (render, OCR, delivery) | The audit row commits in the same transaction as the job's terminal state change. The enqueue is audited separately at request time |
| Provider webhook (PayHere, Resend) | The audit row commits with the subscription or delivery state change, in the handler's transaction. `actor` is null and `causationId` is the provider event id |
| Scheduled job | Same rule; `actor` is null and the action names the scheduler. Per-attempt retries are operational logs, not audit rows (`jobs-and-workers.md` §8) |

If audit ever moves to a separate database, `record` becomes an outbox write in
the mutation's transaction, drained by the audit consumer. The invariant
("no event, no commit") survives the move; only the mechanism changes.

## 6. The read path

### get_matter_audit(ctx, matter_id, page) -> page[AuditEvent]

Matter-scoped timeline (§7 `GET /matters/{id}/audit`). Filter by `user_id`
first, then matter ownership when enforced; a non-owner gets **404, not 403**.
Paginated per
`api-conventions.md` §2 — cursor, `limit` capped at 100, newest first.
Read-only.

### get_history(ctx, filters, page) -> page[AuditEvent]

Backs `GET /api/v1/history`. With `matterId`, delegates to the matter timeline.
Without, returns the feed for the actor's **user account** (`ctx.actorId`),
limited to:

- events on matters owned by that user (when matter ownership is enforced);
- their own account and billing events where capability allows
  (`billing.manage` for subscription events);
- content-governance events only where the actor holds `content.author`;
- compliance events only with `compliance.view`.

Filtering is server-side by `user_id` and capability — never by the client.
Restricted-compliance events are excluded unless the actor is on the compliance
allowlist, and their absence is not signalled.

The feed is **always paginated**; it previously returned an unbounded array,
which on a real firm's history is both a performance and a disclosure problem.

The frontend history screen currently renders a hardcoded four-item list and
does not call this endpoint at all. Wiring it is Phase 8 work; the backend
exposes it first.

Both are **read-only**. There is no write, update, or delete verb on these
routes; the API surface for ordinary users cannot mutate the log (§7: "Read
access only; ordinary users cannot edit/delete").

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Every material mutation is recorded (inv. #8) | `AuditPort.record` in the same transaction as the mutation; no event = no commit |
| Append-only | `AuditRepository` is insert-only; no update or delete path is exposed |
| Tamper-evident | Per-user hash chain (`prevHash`/`hash`); a verification sweep detects any out-of-band change |
| Read API is read-only | `GET` timeline and history only; ordinary users cannot edit or delete events |
| Server-assigned id, timestamp, hash | `record` assigns all three; caller-supplied values are ignored |
| Actor is authenticated identity | `actor` from `RequestContext`, never a request-body or hardcoded id; null only for scheduler and provider events |
| Every event has a user | `userId` required; `matterId` nullable for account and billing events |
| Action and target are closed enums | An unknown `action` or `targetType` is rejected, not written |
| Reason where required | Corrections, overrides, waivers, approvals, reopens, and destruction approvals reject a `record` without a reason |
| Correlation id present | Every event carries the correlation id of its logical operation |
| References, not copies | `before`/`after` are typed references plus a diff; no full document bodies or raw client values |
| User and matter isolation on read | Feed filtered by `user_id`, then ownership/capability; non-owner gets 404 |
| Retention is externally governed | Audit events are outside V0 destruction scope (`retention-service.md` §10) |

A missing audit event and a cross-matter disclosure are both release-blockers
(§9.2); this service is where both gates are enforced on the audit path.

## 8. Failure modes to handle explicitly

- Mutation commits but audit write fails — must not happen; the shared
  transaction makes it all-or-nothing. If they were ever split, that is the
  release-blocking missing-event case.
- Caller supplies an id, timestamp, or actor — ignored; the server assigns all
  three.
- Reason omitted on a mutation that requires it — the `record` call is
  rejected, which fails the mutation.
- Attempt to edit or delete an event through the API — no such route exists;
  data-layer deletes are an operational/retention concern outside ordinary use.
- Large before/after payloads — store references, not full document bodies,
  to keep the log queryable (see open decisions).

## 9. Test list

- **Unit:** `record` assigns id, timestamp, hash, and actor, and ignores
  caller-supplied values; unknown `action` or `targetType` rejected;
  reason-required actions reject without a reason; correlation id always
  present; `userId` required and `matterId` optional; hash chain links
  correctly and a mutated row breaks verification.
- **Contract:** `AuditEvent` read schema; the backend `AuditTargetType` is a
  superset of the frontend enum and the projection maps every extra value;
  paginated `GET /history` and `GET /matters/{id}/audit` envelopes.
- **Integration:** a mutation and its audit event commit or roll back together,
  including from a worker and from a provider webhook handler; **every service
  in the writer list produces exactly one event per material change** — this is
  the conformance test in `service-definition-of-done.md` §4, parameterised over
  the service registry; append-only, no update or delete path succeeds; the
  chain-verification sweep passes on a clean log and fails on a tampered one.
- **Security:** user filtering on the global feed; a matter non-owner
  sees nothing of that matter; capability filtering hides billing, content, and
  compliance events from actors without the capability; restricted-compliance
  events leave no existence signal; 404-not-403 on a foreign matter timeline; no
  raw client value or identifier in any payload; edit and delete routes absent.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Enumerated action vocabulary — closed.** A closed enum in
   `domain/enums.py` (§3.2). Every service maps its mutations to a member; an
   unknown action is rejected.
2. **Structured before/after — closed.** Typed references plus a diff keyed to
   `targetType` (§3). Never full object copies, never raw client values.
3. **Hash-chaining — closed.** `prevHash`/`hash` per user chain (§3.3),
   with a scheduled verification sweep.
4. **Global feed scope — closed.** User-scoped, capability-filtered, paginated,
   newest first (§6).
5. **Retention and legal hold — closed for V0.** Audit events are outside the
   destruction scope that `retention_service` may propose, and tombstones are
   themselves audit records. Ordinary users never delete, regardless.
6. **Access auditing.** Draftly audits *reads* in exactly one place today:
   decryption of a party identifier (`party-service.md` §8). Whether evidence
   views and export downloads also become audited reads is open — plan §5.2
   lists "access" among audited events. Lean **audit evidence-bytes access and
   export downloads, not ordinary list and detail reads**, so the log stays
   about decisions rather than navigation.
