# matter_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`. One markdown per
service under `backend/docs/services/`.

Maps to plan **Phase 2** (authentication, authorisation, and matters), API row
**Matters** (§7), the state-invariant on audit (§5.3.8), and the Phase 2 exit
gates on membership policy, existence hiding, and cross-matter isolation.

## 1. What it owns

The **matter** — the root record every other service hangs off. A document
belongs to a matter, a particular belongs to a matter, a check runs against a
matter, a draft is a matter's output. This service owns creating a matter,
reading it, updating its lifecycle status and active function, and — the part
the frontend has no type for yet — controlling **who may see and act on it**.

It does **not** verify particulars, run checks, hold documents, or produce
drafts. It owns the matter's identity, its lifecycle, its party list, and its
access policy, and it is the gate the other services re-check membership
against.

## 2. Where it sits

```text
GET   /matters          ─┐
POST  /matters          ─┤
GET   /matters/{id}     ─┼─→ api/v1/matters.py ─→ application/matter_service.py
PATCH /matters/{id}     ─┘                                │
                                                          │ orchestrates
                                                          ▼
                              domain/matter.py + domain/invariants.py
                              ports: MatterRepository, MembershipRepository,
                                     AuditPort, IdentityPort
```

The router authenticates and parses only. The service takes an already-
authenticated `RequestContext` (actor, roles, matter memberships) and
orchestrates domain plus ports. Infrastructure implements the ports. The
service imports no SQLAlchemy, no FastAPI, no identity SDK.

Frontend paths today are mocked at `GET /api/matters`, `GET /api/matters/{id}`,
and `POST /api/matters` (`src/lib/data.ts`, `src/lib/store/demo-store.ts`).
Under `/api/v1` these become the plan's `GET/POST /matters` and
`GET/PATCH /matters/{id}` rows.

## 3. Domain models it needs

In `domain/matter.py`, mirroring the frontend `Matter` type
(`frontend/src/types/matter.ts`) so the API contract lines up field-for-field:

- **Matter** — `id`, `reference`, `clientReference?`, `regime`
  (`RegistrationRegime`), `type` (`MatterType`), `parties` (`Party[]`),
  `status` (`MatterStatus`), `activeFunction` (`NotarialFunction`), `progress`
  (`MatterProgress`), `ownerId`, `createdAt`, `updatedAt`.
- **MatterProgress** — `examination`, `drafting`, `execution`, `attestation`,
  each a number. These are progress counters, not authority; a lawyer verifies
  facts elsewhere.
- **Party** — `id`, `role` (`PartyRole`), `nameToken`,
  `identityDocumentReference?`. Parties are **embedded** in the matter, not a
  separate resource. `nameToken` is a token, never a raw name (§8).

Enums live in `domain/enums.py`, values exactly as the frontend declares them:

| Enum | Values |
| --- | --- |
| `MatterStatus` | `open`, `in-review`, `blocked`, `ready-to-draft`, `closed` |
| `MatterType` | `transfer`, `gift`, `lease`, `mortgage`, `other` |
| `RegistrationRegime` | `rta`, `deed`, `condominium`, `special-area` |
| `NotarialFunction` | `examination`, `drafting`, `execution`, `attestation` |
| `PartyRole` | `transferor`, `transferee`, `lessor`, `lessee`, `mortgagor`, `mortgagee`, `other` |

The lifecycle is a state machine enforced in the domain layer so the first
tests hit it without a database:

```text
MatterStatus:  open → in-review → ready-to-draft → closed
                 ↑         ↓
                 └──── blocked ────┘   (a check or missing evidence blocks;
                                        resolution returns to the prior state)
```

An illegal transition raises a domain error, not an HTTP error. The exact legal
transition set is an open decision (§10) — the diagram is the intended shape,
not a ratified rule.

## 4. Membership — the piece the frontend has no type for

The frontend links a matter to a person **only** through `Matter.ownerId`.
Parties are embedded and describe the deed's counterparties, not the app's
users. There is no membership or team join type anywhere in
`frontend/src/types`. But plan Phase 2 requires "matter membership, server-side
policy checks" and "a clerk cannot verify or approve" — a matter needs a
**team**, not a single owner.

So this service introduces a **MatterMembership** join, backend-only, with no
frontend counterpart yet:

```text
MatterMembership:  user_id, matter_id, role
```

`role` here is the app-access role (for example owner, lawyer, clerk),
**distinct** from `PartyRole`, which describes a deed counterparty. Every
matter-scoped read and mutation in every service resolves authorisation through
this join, not through `ownerId` alone. `ownerId` stays as the creator/primary
pointer the frontend already renders; membership is what policy checks against.

The membership model, its role vocabulary, and how it maps to the `RequestContext`
roles are the substance of Phase 2 and are listed under open decisions (§10)
until the role policy is ratified.

## 5. Ports it depends on

In `ports/`:

- `MatterRepository` — persist and load Matter (with embedded parties);
  membership-scoped list and get; optimistic version column for `PATCH`.
- `MembershipRepository` — resolve `(user_id, matter_id) -> role`; list a
  matter's team; add and remove members. May be one repository with
  `MatterRepository`; kept named here because it is the policy seam.
- `IdentityPort` — resolve an actor's identity and app roles from the OIDC
  claim (Phase 2). The service never trusts a role supplied by the browser.
- `AuditPort` — `record(event)`; every create, assignment, status change, and
  archive goes through here (§5.3.8).

## 6. The methods

### list_matters(ctx) -> list[MatterRead]

Returns only matters the actor is a member of, resolved through
`MembershipRepository`. It never returns the full table filtered client-side. A
matter the actor cannot access does not appear — the list is the actor's
matters, full stop.

### get_matter(ctx, matter_id) -> MatterRead

Membership-scoped. If the actor is not a member, return **404, not 403** (Phase
2 exit gate: an unauthorised user cannot infer another matter exists). Returns
the matter with its embedded parties and progress.

### create_matter(ctx, input) -> MatterRead

1. Validate `reference`, `regime`, and `type` against the enums; reject unknown
   values in the domain, not the router.
2. Create the matter with server-owned defaults, matching what the frontend
   already does on create: `parties=[]`, `status=open`,
   `activeFunction=examination`, `progress` all zero, `ownerId=ctx.actor`,
   server timestamps. `clientReference` is optional.
3. Create the creator's `MatterMembership` in the **same transaction** — a
   matter is never left with zero members.
4. Audit `matter.created`.

The frontend mock also clones demo facts and checks from a seed matter into
every new matter (`demo-store.ts` `createMatter`). That is **demo seeding
only**. In production, creation creates the matter and its first membership and
nothing else; facts and checks arrive through their own services. Do not port
the clone.

### update_matter(ctx, matter_id, patch) -> MatterRead

The `PATCH /matters/{id}` row. Membership- and role-scoped; 404 hides existence
for a non-member. Handles the lifecycle status transition (validated against
the state machine in §3), the `activeFunction` change, party list edits, and
`clientReference`. Uses the optimistic version column so a stale write loses.
Every accepted mutation audits with before/after references — status change,
party added or removed, archive (a transition to `closed`). Progress counters
update here too, though which service is authoritative for advancing them is an
open decision (§10).

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Membership decides access, not `ownerId` | Every read/mutation resolves `MatterMembership`; owner is just one member |
| Existence hidden from non-members | Non-member get/patch returns 404, not 403 (Phase 2 gate) |
| Cross-matter isolation | Repository queries are membership-scoped; a cross-matter read is a bug |
| Role policy server-side | App role comes from `IdentityPort`/membership, never from the browser (Phase 2 gate) |
| Every mutation audited (§5.3.8) | `AuditPort.record` on create, assignment, status change, archive, with actor/target/before-after/correlation ID |
| Matter always has a team | Creator membership written in the same transaction as the matter |
| Legal status transitions only | Lifecycle state machine in the domain rejects illegal transitions |

## 8. Privacy posture

Real names, NICs, and addresses are confidential. The frontend already avoids
them: a `Party` carries a `nameToken`, not a name, and an
`identityDocumentReference` rather than an NIC. This service keeps that posture
end to end — it stores and returns tokens and references, never raw identity
data, and never writes raw identity data into audit events or logs. This tracks
the plan's operational rule to keep real client data out of fixtures, logs,
traces, and error reports, and CLAUDE.md's data-privacy rule. Where a raw name
must exist at all, it lives behind the same gated, audited tier as verified
facts, not in the matter's party list.

## 9. Test list

- **Unit:** lifecycle transitions (legal and illegal); enum validation for
  `regime`, `type`, `status`, `activeFunction`, `PartyRole`; create defaults
  match the frontend's (empty parties, `open`, `examination`, zeroed progress);
  optimistic-version conflict rejected.
- **Contract:** `MatterRead`/create/patch response schemas match
  `frontend/src/types/matter.ts` and `party.ts` field-for-field; enum values
  match exactly.
- **Integration:** create writes matter plus creator membership atomically;
  list returns only the actor's matters; PATCH status transition audited with
  before/after.
- **Security:** non-member get/patch returns 404 not 403; cross-matter read and
  write denied; a clerk-role member cannot perform an owner/lawyer-only
  mutation; no raw name/NIC in logs or audit payloads.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **MatterMembership model and role vocabulary** — the frontend has no
   membership type, so the join, its roles (owner/lawyer/clerk or otherwise),
   and how those map to the plan's "a clerk cannot verify or approve" gate must
   be ratified in Phase 2. Lean **a single `MatterMembership(user_id,
   matter_id, role)` join with an explicit app-role enum distinct from
   `PartyRole`.**
2. **Legal status transition set** — the §3 diagram is the intended shape.
   Confirm which `MatterStatus` transitions are legal (for example, can a
   `closed` matter reopen?) before freezing the state machine.
3. **Who advances `progress`** — `MatterProgress` counters
   (examination/drafting/execution/attestation) are rendered by the frontend,
   but which service is authoritative for incrementing them (matter_service on
   PATCH, or the verification/check/draft services as work completes) is
   unspecified. Lean **derive from the owning services and update here through
   an internal call, not a client PATCH.**
4. **Party editing rules** — whether parties are freely editable through PATCH
   or gated once a matter leaves `open`, and whether `PartyRole` must be
   consistent with `MatterType` (a `lease` expecting `lessor`/`lessee`), is an
   open policy question.
