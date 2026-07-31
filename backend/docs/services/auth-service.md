# auth_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`billing-service.md`, `document-service.md`, and `memory-service.md`. One
markdown per service under `backend/docs/services/`.

Maps to plan **Phase 2** (authentication, authorisation, and matters), the
Auth/session API row (§7), and the *Audit* trust-boundary row for account,
role, and assignment changes (§5.2).

This is the service every other service leans on. It decides who the actor is,
what role they hold, and which matters they may touch. Nothing downstream is
allowed to trust the browser for any of that.

## 1. What it owns

Server-side **identity, account role, organisation membership, matter
membership, and policy**. It turns a validated identity-provider token and a
requested organisation into a `RequestContext` (actor id, organisation id,
account role, organisation role, and matter memberships) that downstream
services consume. It answers four questions for every request: is this actor
who they claim to be, which organisation may they act in, what may their roles
do, and are they a member of this matter?

It does **not** store passwords, raw authentication tokens, magic-link tokens,
or login codes. Clerk owns the login flow, token expiry, replay protection,
sessions, and account linking. This service does **not** decide extraction,
verification, or drafting correctness; it only gates who may invoke those. It
does **not** hold matter content. It also does not own subscriptions, payment
state, plan entitlements, or usage counters; those belong to `billing_service`.

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
                                              OrganisationMembershipRepository,
                                              MatterMembershipRepository,
                                              AuditPort
```

The router validates the incoming token and parses the request only. The
service takes the validated identity claims and builds the `RequestContext`
that `api/deps.py` attaches to every downstream request. The service imports no
FastAPI, no SQLAlchemy, and no Clerk SDK — identity validation happens behind
`IdentityPort` (plan §4 `ports/identity.py`, §12 approval item). For V0,
infrastructure implements that port as a Clerk JWT/OIDC adapter in
`infrastructure/identity/clerk_adapter.py`.

**The browser never supplies a trusted role, organisation membership, or
unrestricted matter access.** Roles and memberships are derived server-side
from persisted `User`, `OrganisationMembership`, and `MatterMembership`
records, keyed off the verified identity subject. A role or organisation id in
a request body is ignored. A route or header may select an organisation, but
the server must verify active membership before building the context.

### Selected V0 identity provider

Use **Clerk** as Draftly's managed identity provider. The sign-in screen offers
both:

1. **Continue with Google** — Google OAuth/OIDC through Clerk.
2. **Continue with email** — a short-lived email verification code, with a
   magic link as an optional fallback.

These are separate authentication methods. Google proves control of a Google
account. Passwordless email proves control of any supported email address,
including Gmail, Outlook, or a law-firm domain. Resend does not authenticate a
Gmail account.

```text
Google route

Continue with Google
        ↓
Clerk starts Google OAuth/OIDC
        ↓
Google and Clerk validate the identity
        ↓
Frontend receives a Clerk session
        ↓
FastAPI validates the Clerk token through IdentityPort
        ↓
auth_service loads the Draftly account, role, and memberships
```

```text
Email route

Enter email
        ↓
Clerk creates a short-lived verification code or magic link
        ↓
Clerk's authentication-email infrastructure delivers it
        ↓
Clerk validates the code or link and creates the session
        ↓
FastAPI validates the Clerk token through IdentityPort
        ↓
auth_service loads the Draftly account, role, and memberships
```

The frontend integration is therefore:

```text
Next.js frontend
       ↓
Clerk sign-in and session
       ↓
Clerk JWT
       ↓
FastAPI IdentityPort validates issuer, signature, authorised party, and expiry
       ↓
auth_service resolves the Draftly User through UserIdentity
       ↓
Role and matter memberships load from Neon PostgreSQL
```

Clerk provides identity only. A Clerk, Google, or email claim never grants a
Draftly role or matter membership.

### Admission and account state

Successful authentication does not automatically admit a person to Draftly.
Legal matters contain confidential information, so configure Clerk for
**restricted sign-up** and issue invitations through an administrator-owned
flow. Draftly still enforces its own account state as defence in depth: a new
or otherwise provisioned identity must match an approved Draftly invitation or
remain pending.

```text
Identity authenticated
        ↓
UserIdentity resolved or provisioned
        ↓
Approved invitation found?
        ├── yes → activate User and apply approved role/memberships
        └── no  → keep User pending with no role or memberships
```

An authenticated but pending account is authorised to do nothing beyond the
minimal account-status screen. In particular:

```text
Authenticated ≠ authorised
```

The browser cannot approve its own account, select a role, or assign matter
memberships.

### Authentication email versus application email

Authentication and application notifications have separate owners:

| Owner | Responsibility |
| --- | --- |
| Clerk / auth infrastructure | Login codes, magic links, account verification, recovery, and MFA |
| `notification_service` through Resend | Invitations, deadline reminders, document processing, review notices, and export-ready messages |

Draftly does not need Resend for authentication emails initially. If Clerk is
later configured to use Resend as an underlying transport, authentication
tokens must still bypass `notification_service` and its ordinary notification
templates.

### Alternatives considered

| Option | Decision |
| --- | --- |
| Clerk | **Selected for V0:** Google, passwordless email, sessions, JWT validation, and managed account linking with the least custom integration |
| Auth0 | Viable enterprise OIDC alternative, but heavier than required for the university prototype |
| Auth.js + Google + Resend | Viable in Next.js, but requires more custom session and token integration with the separate FastAPI backend |

The application boundary remains provider-neutral through `IdentityPort`, so a
later provider change does not require rewriting domain services or matter
data.

## 3. Domain models it needs

In `domain/entities.py` (identity) and a small membership model:

- **User** — `id`, `displayName`, `accountStatus`, `role`,
  `notaryRegistration`, and `jurisdiction`. `accountStatus` is `pending |
  active | suspended`. `role` is nullable while pending and otherwise one of
  the four `Role` values. The server owns both fields; the client cannot set
  them. The active-user API projection continues to mirror the frontend
  `User`.
- **UserIdentity** — the external identity link: `userId`, `provider`,
  `issuer`, `subject`, `verifiedEmail`, and `linkedAt`. The unique identity key
  is `(issuer, subject)`, not email. For Clerk-issued application tokens,
  `issuer` and `subject` are the verified Clerk issuer and stable Clerk user
  identifier; upstream Google/email metadata may be retained for audit and
  support, but is not trusted as the application key.
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
- **Organisation** — the tenant/workspace boundary: `id`, `name`, `type`,
  `status`, and `createdAt`. `type` is `solo | firm | enterprise | demo`;
  `status` is `active | suspended | closed`. Every matter and subscription is
  scoped to one organisation.
- **OrganisationMembership** — `(organisation_id, user_id, role, joined_at)`.
  `role` is `owner | admin | member`. It controls workspace administration and
  is distinct from the legal-workflow `User.role` and matter-specific role.
  A user may have memberships in multiple organisations.

Do not create a Draftly-owned `email_login_tokens` table. Token generation,
expiry, replay protection, sessions, and login-account linking belong to
Clerk.

If the same person first uses passwordless email and later uses Google with the
same address, the identities should normally resolve to one Clerk account and
one Draftly `User`. Linking is allowed only when Clerk has verified both email
addresses and applies its account-linking policy. Draftly must not merge
accounts through client-side or database-only email matching.

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
  issuer, authorised party, audience where configured, expiry, and verified
  email where present). Provider-neutral so the OIDC provider can change (plan
  §12). Named in plan §4 as `ports/identity.py`; implemented by the Clerk
  adapter in V0.
- `UserIdentityRepository` — resolve `(issuer, subject)` to a Draftly `User`;
  persist an identity link only through the controlled invitation/provisioning
  path.
- `UserRepository` — load the `User`, `accountStatus`, and server-owned role.
- `OrganisationRepository` — load active organisation state.
- `OrganisationMembershipRepository` — verify that the actor belongs to the
  selected organisation and load the server-owned organisation role.
- `MatterMembershipRepository` — load memberships for a user; answer "is actor
  a member of matter X in the selected organisation, and in what role".
  Organisation- and matter-scoped queries only.
- `AuditPort` — `record(event)`; every account, role, assignment, and matter
  membership mutation goes through here (the same `AuditPort` every service
  calls, see `audit-service.md`).

## 5. The methods

### get_current_user(ctx) -> UserRead

Backs `GET /api/v1/me` (frontend `GET /api/users/me`). Returns the actor's own
`User` — id, displayName, role, notaryRegistration, jurisdiction — derived from
the validated token, never from the request body. This replaces the mock
`getCurrentUser()` that returns `users[0]`.

### build_request_context(token, requested_organisation) -> RequestContext

The core of the service, called by `api/deps.py` on every authenticated
request. Validate the token via `IdentityPort`, resolve `(issuer, subject)`
through `UserIdentityRepository`, load the `User` and account role, verify the
selected organisation and its active `OrganisationMembership`, then load only
that organisation's matter memberships. Assemble:

```text
RequestContext
  actorId
  organisationId
  accountRole
  organisationRole
  matterMemberships
```

Downstream services trust this server-built context. Subscription state and
mutable usage counters are deliberately absent; `billing_service` reads them
server-side at the time of each paid operation.

If the token is invalid, deny with 401. If the identity is valid but has no
approved invitation or active user, return the pending/no-access response
without constructing a privileged `RequestContext`. Suspended accounts and
suspended or closed organisations are denied. A user who is not a member of
the selected organisation receives no organisation context.

### provision_identity(claims, invitation?) -> AccountStatusRead

Called only after `IdentityPort` has validated the Clerk token. It resolves the
external identity and, when needed, creates a `UserIdentity` plus a pending
`User`. A valid, unexpired invitation may activate the user and assign only the
role and matter memberships recorded on that invitation. Provisioning and
activation are audited.

This method never accepts a role or membership selected by the browser.

### authorize(ctx, capability, matter_id?) -> None | raises

The single server-side policy check. Given a required capability (for example
"approve draft") and an optional matter, it enforces two things:

1. **Role capability.** The actor's account, organisation, and where relevant
   matter roles must grant the capability. Use the narrowest applicable grant;
   an organisation owner is not automatically a legal approver.
2. **Organisation boundary.** The target resource must belong to
   `ctx.organisationId`; a client-selected id never changes this boundary.
3. **Matter membership.** If a matter is in scope, the actor must be a member.
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

### require_step_up(ctx, action) -> None | raises

Reserved for legally significant or administrative actions such as approving a
final draft, exporting a legal instrument, changing a controlled template, or
changing another user's role. V0 may enforce a recent Clerk authentication;
MFA or passkeys can be added later behind the same policy check. A long-lived
browser session alone must not be treated as sufficient indefinitely.

## 6. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Authentication is not authorisation | A valid Clerk identity without an active Draftly account, role, and membership receives no matter access |
| External identity is stable | Users resolve by verified `(issuer, subject)`, never by email alone |
| Role is server-derived | `UserIdentityRepository` resolves the verified subject, then `UserRepository` supplies the role; a client-sent role is ignored |
| Organisation is server-derived | The selected organisation is accepted only after an active server-side membership lookup |
| Membership is server-derived | Access decisions read organisation and matter membership repositories, never a client claim |
| Billing is not token-derived | Subscription state and usage remain outside `RequestContext` and are checked server-side |
| Login secrets stay outside Draftly | Clerk owns login codes, magic links, raw auth tokens, expiry, replay protection, and sessions |
| Auth email is isolated | Authentication messages never pass through `notification_service`, even if Resend is later used as transport |
| Reviewer cannot approve | `authorize` maps `approve` to `approver`/`administrator` only (Phase 2 exit gate) |
| Existence hidden from non-members | Non-member matter access returns 404, not 403 (Phase 2 exit gate) |
| Permission changes audited | `assign_membership` and `set_user_role` call `AuditPort.record` with `targetType: "permission"` |
| Cross-matter isolation | Every matter-scoped call re-checks membership; a cross-matter read is denied, not filtered client-side |
| Cross-organisation isolation | Every resource organisation must equal `ctx.organisationId`; no membership permits access across tenants |
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
- Valid token, no matching invitation or user — create or retain a pending
  account with no role or memberships; expose only the account-status surface.
- Pending or suspended user requests application data — deny before loading
  matter data.
- Same verified person signs in through email and Google — rely on Clerk's
  verified account-linking policy; never merge by a client-supplied email.
- Identity subject changes unexpectedly — do not fall back to email matching;
  require an audited administrative recovery/linking path.
- Client sends a role or matter id it should not have — ignored; the server
  derives both from persisted records.
- Client selects an organisation without membership — deny before loading any
  organisation, matter, document, or billing data.
- Non-member requests a real matter — 404, identical to a matter that does not
  exist.
- Administrator removes their own last admin membership — guard against
  locking out account administration (see open decisions).

## 9. Test list

- **Unit:** role → capability map (reviewer denied approve, approver allowed);
  organisation and matter membership derive from repositories, not request
  bodies; pending and suspended accounts cannot produce a privileged context;
  organisation owner is not automatically a legal approver.
- **Contract:** `GET /me` response schema matches the frontend `User`
  (id, displayName, role, notaryRegistration, jurisdiction); `RequestContext`
  shape consumed by `api/deps.py`; pending account response has no role or
  memberships; billing state is absent from the context.
- **Integration:** Clerk adapter validates issuer, signature, authorised party,
  audience where configured, and expiry; `(issuer, subject)` maps through
  `UserIdentity`; invited users activate with only invitation-approved access;
  uninvited or manually provisioned identities remain pending; membership
  assignment and role changes persist and are audited.
- **Security:** cross-organisation and cross-matter access denied;
  404-not-403 existence hiding;
  privilege escalation via forged role/membership claims rejected; permission
  changes always produce an audit event; email-only account merging rejected;
  raw tokens, login codes, and PII are absent from logs; sensitive actions
  reject stale sessions when step-up is required.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Role composition** — `User`, `OrganisationMembership`, and
   `MatterMembership` carry separate roles. Use **the narrowest applicable
   grant**, and never let organisation ownership imply legal approval.
2. **Owner vs. membership** — the frontend `Matter.ownerId` is a single owner.
   Decide whether `ownerId` becomes an implicit `administrator`/`approver`
   membership or is dropped in favour of explicit memberships. Lean **derive an
   explicit membership from `ownerId` at migration**, then treat memberships as
   the source of truth.
3. **Admin lockout guard** — prevent removing the last organisation owner or
   required matter administrator. Lean **block the operation** with a clear
   error.
4. **Step-up policy** — choose the Clerk session age and which actions require
   recent authentication for V0. Lean **require it for final-draft approval,
   legal-instrument export, controlled-template changes, and role changes**.
5. **Email fallback** — enable magic links in addition to the primary email
   verification-code flow. Lean **code first, magic link as a fallback** to
   reduce cross-device link confusion.
6. **New capability tiers** — any role beyond the four frontend values
   (`reviewer`, `approver`, `maintainer`, `administrator`) is a product
   decision, not an implementation shortcut.

## 11. Decision record and references

The following decisions are closed for V0:

- Identity provider: **Clerk**.
- Sign-in methods: **Google OAuth/OIDC and passwordless email code**; magic link
  optional.
- Application database: **Neon PostgreSQL** for Draftly users, identities,
  roles, invitations, organisation memberships, and matter memberships.
- Tenant boundary: **organisation/workspace selected through verified
  membership**; subscriptions belong to that organisation.
- Application email: **Resend through `notification_service`**.
- Identity mapping: **separate `UserIdentity` keyed by `(issuer, subject)`**.
- Admission: **invitation/approval required; otherwise pending with no access**.

Provider documentation:

- [Clerk sign-up and sign-in options][clerk-sign-in]
- [Clerk OAuth account linking][clerk-account-linking]
- [Clerk access restrictions][clerk-restrictions]
- [Clerk session-token validation][clerk-session-tokens]
- [Auth0 authentication API][auth0-authentication] (alternative considered)
- [Auth.js Resend provider][authjs-resend] (alternative considered)

[clerk-sign-in]: https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options
[clerk-account-linking]: https://clerk.com/docs/guides/configure/auth-strategies/social-connections/account-linking
[clerk-restrictions]: https://clerk.com/docs/guides/secure/restricting-access
[clerk-session-tokens]: https://clerk.com/docs/guides/sessions/session-tokens
[auth0-authentication]: https://auth0.com/docs/api/authentication/login
[authjs-resend]: https://authjs.dev/getting-started/providers/resend
