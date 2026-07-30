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
document_service ─┐
verification_svc  ─┤
check_service     ─┼─→ AuditPort.record(event) ─→ application/audit_service.py
draft_service     ─┤        (write, append-only)          │
approval_service  ─┤                                       ▼
auth_service      ─┘                          ports: AuditRepository (append-only)

GET /api/v1/matters/{id}/audit ──→ api/v1/audit.py ──→ read timeline
GET /api/v1/history            ──→ (optional matterId) ──→ per-matter or global feed
```

`AuditPort` is the name every other service doc references. Services never
write audit rows directly; they call `AuditPort.record(event)` and the audit
service owns id assignment, timestamping, and append-only persistence behind
`AuditRepository`. The read routers are query-only. The service imports no
FastAPI and no SQLAlchemy.

## 3. Domain model it needs

In `domain/audit.py`, mirroring the frontend `AuditEvent`
(`src/types/audit.ts`) so the read contract matches:

- **AuditEvent** — `id`, `matterId`, `actor`, `action`, `targetType:
  AuditTargetType`, `targetId`, `before?`, `after?`, `timestamp`.
- **AuditTargetType** — exactly the frontend enum: `matter | document | fact |
  check | workflow-step | answer | draft | permission`. `permission` covers
  account, role, and membership changes written by `auth_service`.

`id` and `timestamp` are **server-assigned** on `record`, not supplied by the
caller. `actor` comes from the authenticated `RequestContext` (see
`auth-service.md`), not from the request body.

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

## 6. The read path

### get_matter_audit(ctx, matter_id) -> AuditEvent[]

Matter-scoped timeline (§7 `GET /matters/{id}/audit`). Membership is re-checked
via `auth_service`; a non-member gets **404, not 403**, consistent with
cross-matter isolation. Read-only.

### get_history(ctx, matter_id?) -> AuditEvent[]

Backs `GET /api/v1/history`. With `matterId`, delegates to the matter timeline.
Without, returns the global feed limited to matters the actor may see — the
feed is filtered by membership server-side, not by the client. Read-only.

Both are **read-only**. There is no write, update, or delete verb on these
routes; the API surface for ordinary users cannot mutate the log (§7: "Read
access only; ordinary users cannot edit/delete").

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Every material mutation is recorded (inv. #8) | `AuditPort.record` in the same transaction as the mutation; no event = no commit |
| Append-only | `AuditRepository` is insert-only; no update or delete path is exposed |
| Read API is read-only | `GET` timeline and history only; ordinary users cannot edit or delete events |
| Server-assigned id and timestamp | `record` assigns both; caller-supplied values are ignored |
| Actor is authenticated identity | `actor` from `RequestContext`, never a request-body or hardcoded id |
| Reason where required | Corrections, overrides, and approvals reject a `record` without a reason |
| Correlation id present | Every event carries the correlation id of its logical operation |
| Matter isolation on read | Timeline and feed filtered by membership; non-member gets 404 |

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

- **Unit:** `record` assigns id/timestamp/actor and ignores caller-supplied
  values; reason-required mutations reject without a reason; correlation id is
  always present.
- **Contract:** `AuditEvent` read schema matches the frontend type
  (`AuditTargetType` values included); `GET /history` with and without
  `matterId`.
- **Integration:** a mutation and its audit event commit or roll back together;
  every mutating service produces exactly one event per material change;
  append-only — no update/delete path succeeds.
- **Security:** cross-matter feed filtering (a non-member sees nothing of
  another matter); 404-not-403 on a foreign matter timeline; no PII leakage in
  event payloads beyond intended references; edit/delete routes absent.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Enumerated action vocabulary** — the frontend `action` is a **free-form
   string** (`"document.uploaded"`, `"fact.corrected"`, and so on, set
   ad hoc per call). Recommend a **closed enum of action codes** so the feed is
   queryable and filterable and typos cannot fragment the history. Lean
   **define the enum in `domain/enums.py`** and map each service's mutations to
   it.
2. **Structured before/after** — the frontend `before`/`after` are `unknown`.
   Recommend a **typed, structured diff** keyed to the `targetType` rather than
   opaque blobs, so "what changed" is queryable and tamper-evidence is
   meaningful. Lean **references plus a typed diff**, not full object copies.
3. **Hash-chaining for tamper-evidence** — append-only prevents ordinary
   edits, but does not by itself prove the log was not altered out of band.
   Recommend **chaining each event to the hash of its predecessor** (per matter
   or global) so any retroactive change is detectable. Lean **add a
   `prev_hash`/`hash` pair** once the action vocabulary and structured diff are
   settled.
4. **Global feed scope** — whether the wired global feed spans all of an
   actor's matters or only recent activity, and its pagination. Lean
   **membership-scoped, paginated, most-recent-first**.
5. **Retention and legal hold** — how long events are kept and how a legal hold
   interacts with any operational purge. Defer to the retention policy (plan
   §10, §12) — but ordinary users never delete, regardless.
