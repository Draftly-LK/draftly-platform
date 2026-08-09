# auth_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`billing-service.md`, `document-service.md`, and `memory-service.md`. One
markdown per service under `backend/docs/services/`.

Maps to plan **Phase 2** (authentication, authorisation, and matters), the
Auth/session API row (§7), and the *Audit* trust-boundary row for account and
role changes (§5.2).

This is the service every other service leans on. It decides who the actor is,
what role they hold, and which capabilities they may exercise. Nothing
downstream is allowed to trust the browser for any of that.

## 1. What it owns

Server-side **identity, account role, and policy**. It turns a validated
identity-provider token into a `RequestContext` (`actor_id`, `account_role`,
`correlation_id`) that downstream services consume. It answers three questions
for every request: is this actor who they claim to be, what may their role do,
and (for matter-scoped resources) does the resource belong to them?

It does **not** store passwords, raw authentication tokens, magic-link tokens,
or login codes. The identity provider owns the login flow, token expiry, replay
protection, sessions, and account linking. This service does **not** decide
extraction, verification, or drafting correctness; it only gates who may invoke
those. It does **not** hold matter content or matter ownership rows — when
`matter_service` lands, matters carry `owner_user_id` and that service enforces
ownership; V0 `authorize` is **capability-only** (no matter membership join in
auth). It also does not own subscriptions, payment state, plan entitlements, or
usage counters; those belong to `billing_service`.

There is **no** `Organisation`, `OrganisationMembership`, `MatterMembership`
(in auth), or `Invitation` in the solo-user model. One verified Gmail account
maps to one `User`.

### State of play in the frontend

There is **no real auth yet** on all screens. The frontend ships a single
hardcoded demo user and a `DEMO_USER_ID` actor:

- `getCurrentUser()` (`src/lib/data.ts`, marked `TODO(api): GET /api/users/me`)
  returns `users[0]` — the one seeded `User`.
- The seeded user is `DEMO_USER_ID = "user-reviewer-001"` with role
  `approver`, `notaryRegistration: "SYN-NP-0042"`,
  `jurisdiction: "Western Province (synthetic)"` (`src/lib/mocks/fixtures.ts`).
- Every mutation in `demo-store.ts` hardcodes `actor: DEMO_USER_ID`; there is
  no sign-in, no token, and no role check in the mock layer.

The backend Phase 2 implementation is live: Google sign-in through the identity
adapter, auto-provision, and `GET /api/v1/me`. The frontend contract to honour
is the shape of `GET /api/users/me`.

## 2. Where it sits

```text
GET /api/v1/me ──→ api/v1/auth.py ──→ application/auth_service.py
                        │                        │
                        │ validates token        │ derives role
                        ▼                        ▼
                 ports: IdentityPort (OIDC)   ports: UserRepository,
                                              UserIdentityRepository,
                                              AuditPort
```

The router validates the incoming token and parses the request only. The
service takes the validated identity claims and builds the `RequestContext`
that `api/deps.py` attaches to every downstream request. The service imports no
FastAPI, no SQLAlchemy, and no provider SDK — identity validation happens behind
`IdentityPort` (plan §4 `ports/identity.py`, §12 approval item). For V0,
infrastructure implements that port as a Clerk JWT/OIDC adapter in
`infrastructure/identity/clerk_adapter.py` (Google OAuth is the primary
sign-in method).

**The browser never supplies a trusted role or unrestricted matter access.**
The account role is derived server-side from the persisted `User` record, keyed
off the verified identity subject `(issuer, subject)`. A role in a request body
is ignored.

### Selected V0 identity provider

Use **Clerk** as Draftly's managed identity provider with **Google OAuth/OIDC
as the primary sign-in path** for the solo notary product. V0 targets one
verified Gmail per user; passwordless email and magic links remain available
through Clerk for future flows but are not required for the solo admission path.

```text
Google route (primary)

Continue with Google
        ↓
Clerk starts Google OAuth/OIDC
        ↓
Google and Clerk validate the identity (verified email required)
        ↓
Frontend receives a Clerk session
        ↓
FastAPI validates the Clerk token through IdentityPort
        ↓
auth_service provisions or loads the Draftly User and role
```

```text
Next.js frontend
       ↓
Clerk sign-in and session (Google)
       ↓
Clerk JWT
       ↓
FastAPI IdentityPort validates issuer, signature, authorised party, and expiry
       ↓
auth_service resolves the Draftly User through UserIdentity
       ↓
Role loads from Neon PostgreSQL
```

Clerk provides identity only. A Clerk or Google claim never grants a Draftly
role by itself — the server assigns role on provision or through
`set_user_role`.

### Admission and account state

**Closed for V0 (solo user):** the first successful Google login with a
**verified email** auto-provisions an **ACTIVE** user with role **APPROVER**.
No invitation, no pending gate, and no organisation bootstrap. Subsequent logins
resolve the existing `User` via `(issuer, subject)` or link a second provider
to the same user when Clerk has verified the same email.

```text
Identity authenticated (verified email)
        ↓
UserIdentity resolved by (issuer, subject)?
        ├── yes → load User; deny if pending/suspended/no role
        └── no  → same verified email already linked?
                    ├── yes → link new identity to existing User
                    └── no  → create User (ACTIVE, APPROVER) + UserIdentity
```

`PENDING` and `SUSPENDED` remain valid `accountStatus` values for operational
or compliance actions; they are not the default first-login path.

```text
Authenticated ≠ authorised
```

A pending or suspended account, or a user with no role, cannot construct a
privileged `RequestContext`. The browser cannot set its own role.

### Authentication email versus application email

Authentication and application notifications have separate owners:

| Owner | Responsibility |
| --- | --- |
| Clerk / auth infrastructure | Login codes, magic links, **email verification**, account recovery, password and sign-in security notices, MFA |
| `notification_service` through Resend | Deadline reminders, document processing, review notices, approval and export messages |

Draftly does not route authentication emails through `notification_service`.
There is no invitation email in the solo model.

### Alternatives considered

| Option | Decision |
| --- | --- |
| Clerk + Google | **Selected for V0:** Google OAuth, sessions, JWT validation, managed linking |
| Auth0 | Viable enterprise OIDC alternative, heavier than required for the prototype |
| Auth.js + Google + Resend | Viable in Next.js, more custom session work with FastAPI |

The application boundary remains provider-neutral through `IdentityPort`.

## 3. Domain models it needs

In `domain/models.py` (identity):

- **User** — `id`, `displayName`, `accountStatus`, `role`,
  `notaryRegistration`, `jurisdiction`, and profile fields as exposed on
  `GET /me`. `accountStatus` is `pending | active | suspended`. `role` is
  nullable while pending and otherwise one of the four `Role` values. The server
  owns both fields; the client cannot set them.
- **UserIdentity** — the external identity link: `userId`, `provider`,
  `issuer`, `subject`, `verifiedEmail`, and `linkedAt`. The unique identity key
  is `(issuer, subject)`, not email. Verified email is unique when present and
  supports controlled linking of a second provider to the same `User`.
- **Role** — exactly the frontend enum: `reviewer | approver | maintainer |
  administrator`. No fifth role is invented here.

Do not create a Draftly-owned `email_login_tokens` table. Token generation,
expiry, replay protection, sessions, and login-account linking belong to the
identity provider.

### Role → capability map

Roles map to **capability keys**, not to prose. The full catalogue and the
role-to-capability table live in `security-model.md` §3 and are the single
source of truth; this service implements them. Summarised:

| Role | Broadly |
| --- | --- |
| `reviewer` | Evidence, verified record, drafting, resolve findings, complete steps; **cannot approve, export, attest, waive, override, or confirm a deadline** |
| `approver` | Everything a reviewer can, plus approval/export/attestation/deadline capabilities, plus **solo admin surface:** `billing.manage`, `retention.*`, `user.role.set` |
| `maintainer` | `content.*` and `corpus.*` — governed content and corpus, nothing matter-operational |
| `administrator` | Full account, matter lifecycle, retention, billing, and `user.role.set` for multi-role deployments |

Two capability groups are **not** reachable through these four roles and are
granted by an audited administrative action instead: `compliance.*` and
`platform.administer` (`security-model.md` §3.4).

A capability the map does not grant is denied. Capabilities are not additive by
seniority — `maintainer` governs content but is not an approver.

### "Authorised lawyer" is a capability plus a practising-status check

Nine service docs gate on "an authorised lawyer". The resolution is in
`security-model.md` §3.3 and is implemented here as a second predicate:

```text
authorize(ctx, capability, matter_id?)          # role → capability
require_practising_notary(ctx, matter_id?)      # practising status
```

`require_practising_notary` asserts that `User.notaryRegistration` is present,
that the annual practice certificate is current, and — for territorial
operations — that `User.jurisdiction` covers the matter's registration
jurisdiction.

An expired certificate blocks those capabilities. It does not warn and proceed.

The refusal case for missing capability is 403 `capability_denied`.

### NIC / identity — keep two things distinct

The RTA domain requires an **NIC identity check during attestation**. That is
**matter data**, not auth. The NIC verified against a party belongs to the
verified matter record (`verification_service`), carries a source span, and is
audited as a `fact`. It is **not** the notary's login identity and must not be
conflated with `IdentityPort` or `User.notaryRegistration`. Auth identifies the
*user of the system*; attestation NIC checks identify a *party to the matter*.

## 4. Ports it depends on

In `ports/`:

- `IdentityPort` — validate an OIDC token and return verified claims.
- `UserIdentityRepository` — resolve `(issuer, subject)` and verified email to
  a Draftly `User`; persist identity links on provision.
- `UserRepository` — load the `User`, `accountStatus`, and server-owned role.
- `AuditPort` — `record(event)`; every account and role mutation goes through
  here (`audit-service.md`).

There is no organisation or matter-membership repository in auth for V0.

## 5. The methods

### get_current_user(ctx) -> UserRead

Backs `GET /api/v1/me`. Returns the actor's own `User` derived from the
validated token, never from the request body.

### build_request_context(token, correlation_id?) -> RequestContext

Called by `api/deps.py` on every authenticated request. Validate the token via
`IdentityPort`, resolve `(issuer, subject)` through `UserIdentityRepository`,
load the `User`, and deny pending/suspended users or users without a role.
Assemble:

```text
RequestContext
  actorId
  accountRole
  correlationId
```

Downstream services trust this server-built context. Subscription state is
deliberately absent; `billing_service` reads it server-side per operation.

If the token is invalid, deny with 401. If the identity is valid but the
account cannot act, deny before constructing a privileged context.

### provision_identity(token, correlation_id?) -> User

Called after `IdentityPort` has validated the token. Requires **verified email**.
Creates or links `UserIdentity` and, on first sight of a new verified email,
creates an **ACTIVE** `User` with role **APPROVER**. Provisioning is audited.
This method never accepts a role from the browser.

### authorize(ctx, capability, matter_id?) -> None | raises

The single server-side **capability** check for V0. Given a required capability
and an optional matter id (reserved for when `matter_service` enforces
`owner_user_id`), it enforces:

1. **Role capability.** The actor's `accountRole` must grant the capability.
2. **User boundary.** Downstream services filter every customer row by
   `user_id` equal to `ctx.actorId` (or `owner_user_id` for matters). Auth does
   not re-check matter ownership in V0; `matter_service` will.

Cross-user matter existence hiding (404, not 403) is enforced when matter
ownership checks land in `matter_service` (`security-model.md` §5).

### set_user_role(ctx, user_id, role) -> User

Requires `user.role.set`. Changes another user's `Role` (solo deployments may
only use this for support scenarios). Audited as a `permission` change.

### require_step_up(ctx, action, token?) -> None | raises

Reserved for legally significant actions. V0 may enforce a recent
re-authentication via a fresh token and `auth_time` within
`step_up_max_age_seconds`.

## 6. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Authentication is not authorisation | A valid identity without an active role receives no privileged context |
| External identity is stable | Users resolve by verified `(issuer, subject)`, not email alone for login |
| Role is server-derived | `UserRepository` supplies the role; client-sent role is ignored |
| Tenancy is user-scoped | Customer data rows carry `user_id`; context carries `actorId` only |
| Billing is not token-derived | Subscription state remains outside `RequestContext` |
| Login secrets stay outside Draftly | Provider owns codes, tokens, sessions |
| Auth email is isolated | Authentication messages never pass through `notification_service` |
| Reviewer cannot approve | `authorize` maps approve-tier capabilities to `approver`/`administrator` |
| Permission changes audited | `set_user_role` calls `AuditPort.record` |
| Auth identity ≠ attestation NIC | Party NIC lives in the verified matter record, not here |
| First Google login provisions APPROVER | Verified email required; auto-active, no invitation |

## 7. How jurisdiction ties in

`User.jurisdiction` records the actor's territory for downstream checks
(`check_service`) on territorial rules. Auth persists and exposes the field; the
deterministic rule engine acts on it elsewhere.

## 8. Failure modes to handle explicitly

- Expired or malformed token — 401 at `IdentityPort`.
- Valid token, no verified email on provision — reject provision.
- Pending or suspended user — deny before privileged context.
- Token without linked identity on protected routes — treat as not admitted.
- Client sends a role — ignored.
- Non-owner matter access — 404 when matter service enforces ownership (Phase 2
  matter work).

## 9. Test list

- **Unit:** role → capability map; approver receives billing/retention/
  `user.role.set`; pending cannot build context.
- **Contract:** `GET /me` schema; `RequestContext` shape for `api/deps.py`.
- **Integration:** identity adapter; provision creates ACTIVE APPROVER; role
  changes audited.
- **Security:** capability escalation rejected; cross-user isolation delegated
  to row-level `user_id` filters and future matter ownership; step-up when
  configured.

## 10. Open decisions

1. **Step-up policy** — session age and which actions require fresh auth.
2. **Email-only sign-in** — secondary to Google for solo V0; product may defer.
3. **Matter ownership** — `owner_user_id` and 404 rules in `matter_service`.
4. **New capability tiers** — product decision, not a silent code addition.

## 11. Decision record and references

Closed for V0 (solo user):

- Identity provider: **Clerk** with **Google OAuth primary**.
- Application database: **Neon PostgreSQL** for `users` and `user_identities`
  only (no organisation or invitation tables in auth).
- Tenant boundary: **`user_id` on every customer row**; one verified Gmail →
  one `User`.
- Admission: **auto-provision ACTIVE APPROVER** on first Google login with
  verified email.
- `RequestContext`: **`actor_id`, `account_role`, `correlation_id` only**.
- Application email: **Resend through `notification_service`** for product
  notifications only.

Provider documentation:

- [Clerk sign-up and sign-in options][clerk-sign-in]
- [Clerk OAuth account linking][clerk-account-linking]
- [Clerk session-token validation][clerk-session-tokens]

[clerk-sign-in]: https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options
[clerk-account-linking]: https://clerk.com/docs/guides/configure/auth-strategies/social-connections/account-linking
[clerk-session-tokens]: https://clerk.com/docs/guides/sessions/session-tokens
