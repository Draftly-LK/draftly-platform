# auth_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`document-service.md`, and `memory-service.md`. One markdown per service under
`backend/docs/services/`.

Maps to plan **Phase 2** (authentication, authorisation, and matters), the
Auth/session API row (§7), and the *Audit* trust-boundary row for account,
role, and assignment changes (§5.2).

This is the service every other service leans on. It decides who the actor is,
what role they hold, and which matters they may touch. Nothing downstream is
allowed to trust the browser for any of that.

## 1. What it owns

Server-side **identity, role, matter membership, and policy**. It turns a
validated identity-provider token into a `RequestContext` (actor id, role,
matter memberships) that document, verification, check, draft, approval, and
export services consume. It answers three questions for every request: is this
actor who they claim to be, what may their role do, and are they a member of
this matter?

It does **not** store passwords or run the login flow — an external
OIDC-compatible identity provider owns authentication (plan §7, §12). It does
**not** decide extraction, verification, or drafting correctness; it only
gates who may invoke those. It does **not** hold matter content.

### State of play in the frontend

There is **no real auth yet**. The frontend ships a single hardcoded demo
user and a `DEMO_USER_ID` actor:

- `getCurrentUser()` (`src/lib/data.ts`, marked `TODO(api): GET /api/users/me`)
  returns `users[0]` — the one seeded `User`.
- The seeded user is `DEMO_USER_ID = "user-reviewer-001"` with role
  `approver`, `notaryRegistration: "SYN-NP-0042"`,
  `jurisdiction: "Western Province (synthetic)"` (`src/lib/mocks/fixtures.ts`).
- Every mutation in `demo-store.ts` hardcodes `actor: DEMO_USER_ID`; there is
  no sign-in, no token, no role check, and no membership join.

So this service is a **build**, not a port of existing behaviour. The frontend
contract to honour is only the shape of `GET /api/users/me`.

## 2. Where it sits

```text
GET /api/v1/me ──→ api/v1/auth.py ──→ application/auth_service.py
                        │                        │
                        │ validates token        │ derives role + memberships
                        ▼                        ▼
                 ports: IdentityPort (OIDC)   ports: UserRepository,
                                              MatterMembershipRepository,
                                              AuditPort
```

The router validates the incoming token and parses the request only. The
service takes the validated identity claims and builds the `RequestContext`
that `api/deps.py` attaches to every downstream request. The service imports no
FastAPI, no SQLAlchemy, and no OIDC SDK — identity validation happens behind
`IdentityPort` (plan §4 `ports/identity.py`, §12 approval item), infrastructure
implements it in `infrastructure/identity/oidc_adapter.py`.

**The browser never supplies a trusted role or unrestricted matter access.**
Role and membership are derived server-side from the persisted `User` and
`MatterMembership` records, keyed off the verified identity subject — never off
a claim the client sent (plan Phase 2). A role or matter id in the request body
is ignored.

## 3. Domain models it needs

In `domain/entities.py` (identity) and a small membership model:

- **User** — mirrors the frontend `User`: `id`, `displayName`, `role: Role`,
  `notaryRegistration`, `jurisdiction`. `role` is one of the four `Role`
  values; the server owns this field, the client cannot set it.
- **Role** — exactly the frontend enum: `reviewer | approver | maintainer |
  administrator`. No fifth role is invented here; a new capability tier is an
  open decision, not a silent addition.
- **MatterMembership** — **to build.** The join `(user_id, matter_id, role)`
  that records which users belong to which matter and in what capacity. The
  frontend has no such model — a `Matter` carries only `ownerId`
  (`src/types/matter.ts`), which is a single owner, not a membership set. The
  plan **requires** matter membership checks (§2.1, Phase 2), so this join is
  the missing piece. Cross-reference `matter-service.md` for where memberships
  are assigned and audited.

### Role → capability map

Roles map to capabilities server-side. The browser may hide buttons, but the
gate lives here:

| Role | May do |
| --- | --- |
| `reviewer` | Verify and correct facts, run deterministic checks; **cannot approve** |
| `approver` | Everything a reviewer can, plus approve drafts (the approval gate) |
| `maintainer` | Govern controlled content — rule versions, templates, question sets (see `content-governance-service`) |
| `administrator` | Manage accounts, roles, and matter assignments |

A capability the map does not grant is denied. Capabilities are not additive by
seniority unless the map says so — `maintainer` governs content but is not
implicitly an approver.

### NIC / identity — keep two things distinct

The RTA domain requires an **NIC identity check during attestation**. That is
**matter data**, not auth. The NIC verified against a party belongs to the
verified matter record (`verification_service`), carries a source span, and is
audited as a `fact`. It is **not** the notary's login identity and must not be
conflated with `IdentityPort` or the `User.notaryRegistration` field. Calling
this out because both are "identity" in plain English and mixing them would put
matter PII on the auth path. Auth identifies the *user of the system*;
attestation NIC checks identify a *party to the matter*.

## 4. Ports it depends on

In `ports/`:

- `IdentityPort` — validate an OIDC token and return verified claims (subject,
  issuer, expiry). Provider-neutral so the OIDC provider can change (plan §12).
  Named in plan §4 as `ports/identity.py`.
- `UserRepository` — load the `User` (and thus `role`) for a verified subject.
- `MatterMembershipRepository` — load memberships for a user; answer "is actor
  a member of matter X, and in what role". Matter-scoped queries only.
- `AuditPort` — `record(event)`; every account, role, assignment, and matter
  membership mutation goes through here (the same `AuditPort` every service
  calls, see `audit-service.md`).

## 5. The methods

### get_current_user(ctx) -> UserRead

Backs `GET /api/v1/me` (frontend `GET /api/users/me`). Returns the actor's own
`User` — id, displayName, role, notaryRegistration, jurisdiction — derived from
the validated token, never from the request body. This replaces the mock
`getCurrentUser()` that returns `users[0]`.

### build_request_context(claims) -> RequestContext

The core of the service, called by `api/deps.py` on every authenticated
request. Validate the token via `IdentityPort`, load the `User` and role from
`UserRepository`, load memberships from `MatterMembershipRepository`, and
assemble the `RequestContext (actor, role, matter_memberships)` that downstream
services trust. If the token is invalid or the subject maps to no user, deny.

### authorize(ctx, capability, matter_id?) -> None | raises

The single server-side policy check. Given a required capability (for example
"approve draft") and an optional matter, it enforces two things:

1. **Role capability.** The actor's role must grant the capability per the §3
   map. A `reviewer` asking to approve is denied — this is the Phase 2 exit
   gate that a clerk/reviewer cannot approve.
2. **Matter membership.** If a matter is in scope, the actor must be a member.
   A non-member is treated as if the matter does not exist: return **404, not
   403**, so an unauthorised user cannot infer another matter's existence
   (Phase 2 exit gate). A `403` would confirm the matter is real.

### assign_membership(ctx, matter_id, user_id, role) -> MembershipRead

Administrator-only. Adds or changes a `MatterMembership`. Audited as a
`permission` change (`targetType: "permission"` — the frontend
`AuditTargetType` includes `"permission"` precisely so permission changes are
recorded). Cross-reference `matter-service.md`.

### set_user_role(ctx, user_id, role) -> UserRead

Administrator-only. Changes a user's `Role`. Audited as a `permission` change.
Role changes are account mutations under the Phase 2 exit gate.

## 6. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Role is server-derived | `role` comes from `UserRepository` keyed on the verified subject; a client-sent role is ignored |
| Membership is server-derived | Access decisions read `MatterMembershipRepository`, never a client claim |
| Reviewer cannot approve | `authorize` maps `approve` to `approver`/`administrator` only (Phase 2 exit gate) |
| Existence hidden from non-members | Non-member matter access returns 404, not 403 (Phase 2 exit gate) |
| Permission changes audited | `assign_membership` and `set_user_role` call `AuditPort.record` with `targetType: "permission"` |
| Cross-matter isolation | Every matter-scoped call re-checks membership; a cross-matter read is denied, not filtered client-side |
| Auth identity ≠ attestation NIC | User identity via `IdentityPort`; party NIC lives in the verified matter record, not here |

Cross-matter disclosure is a **release-blocker** (§9.2): the backend cannot be
accepted if it permits a cross-matter read. This service is where that gate is
implemented.

## 7. How jurisdiction ties in

`User.jurisdiction` is not decoration. The notary domain has a
**territorial-jurisdiction** rule — a notary attests within their registered
province. The field records the actor's territory so downstream checks
(`check_service`) can flag a matter whose parcel falls outside the acting
notary's jurisdiction. Auth persists and exposes the field; the deterministic
rule that acts on it lives in the check engine, not here.

## 8. Failure modes to handle explicitly

- Expired or malformed token — deny at `IdentityPort` validation, return 401,
  leak nothing about which matters exist.
- Valid token, no matching user — deny; a provisioned identity with no `User`
  record is not authorised until an administrator creates the account.
- Client sends a role or matter id it should not have — ignored; the server
  derives both from persisted records.
- Non-member requests a real matter — 404, identical to a matter that does not
  exist.
- Administrator removes their own last admin membership — guard against
  locking out account administration (see open decisions).

## 9. Test list

- **Unit:** role → capability map (reviewer denied approve, approver allowed);
  membership check derives from repository not request; role/membership from
  the request body is ignored.
- **Contract:** `GET /me` response schema matches the frontend `User`
  (id, displayName, role, notaryRegistration, jurisdiction); `RequestContext`
  shape consumed by `api/deps.py`.
- **Integration:** OIDC adapter validates a token and maps to a `User`;
  membership assignment persists and is audited; role change persists and is
  audited.
- **Security:** cross-matter access denied; 404-not-403 existence hiding;
  privilege escalation via forged role/membership claims rejected; permission
  changes always produce an audit event; no token or PII in logs.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **OIDC provider and claim → user mapping** (plan §12 open) — which provider,
   and whether the subject maps to `User.id` directly or via an external-id
   table. Lean **an external-id table** so the identity provider can change
   without rewriting matter data.
2. **Membership role vs. account role** — `MatterMembership` carries its own
   `role` (per matter), while `User.role` is account-wide. Decide precedence
   when they differ. Lean **the narrower of the two grants** the capability.
3. **Owner vs. membership** — the frontend `Matter.ownerId` is a single owner.
   Decide whether `ownerId` becomes an implicit `administrator`/`approver`
   membership or is dropped in favour of explicit memberships. Lean **derive an
   explicit membership from `ownerId` at migration**, then treat memberships as
   the source of truth.
4. **Admin lockout guard** — prevent removing the last administrator membership
   on an account or matter. Lean **block the operation** with a clear error.
5. **New capability tiers** — any role beyond the four frontend values
   (`reviewer`, `approver`, `maintainer`, `administrator`) is a product
   decision, not an implementation shortcut.
