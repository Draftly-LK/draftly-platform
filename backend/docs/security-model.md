# Security model — tenancy, capabilities, and existence hiding

Companion to `backend/backend-implementation-plan-v0.md` §5.2 and Phase 2,
`services/auth-service.md`, and every matter-scoped service.

Three rules were previously restated — and drifted — in nine service docs:
the organisation boundary, the role gate, and the 404-not-403 rule. They are
defined here once. A service doc states *which capability* an operation needs
and otherwise points here.

## 1. The two independent gates

```text
request
  ├─ auth_service.authorize(ctx, capability, matter_id?)   ← may they?
  └─ billing_service.require_feature(org_id, feature_key)  ← is it paid for?
```

Both must pass. A paid plan never grants a capability, and a capability never
bypasses a plan or quota (`billing-service.md` §1). A service that performs a
metered operation calls both, in that order, and neither is optional because the
button was hidden in the browser.

## 2. Organisation is the outer boundary

Every persisted row that belongs to a customer carries `organisation_id`. Not
"most rows" — every one, including audit events, notification deliveries,
research conversations, session-memory episodes, voice captures, obligations,
and party records.

```text
filter by ctx.organisationId      ← always, first
  then filter by matter membership ← when the resource is matter-scoped
    then check capability          ← when the operation mutates or is privileged
```

The organisation comes from the server-built `RequestContext`, which is derived
from an active `OrganisationMembership` looked up against the verified identity
subject. A client-supplied organisation id selects which membership to verify;
it never establishes one.

Consequences that the individual service docs previously missed:

- **Non-matter-scoped reads still have a tenant boundary.** The audit global
  feed, notification preferences, obligation lists at user or firm scope,
  research conversations, session memory, and voice captures are all filtered by
  organisation before anything else.
- **The legal corpus is the one exception.** `library_service` and the corpus
  side of `research_service` read a published release that is not
  organisation-scoped, because approved statutes are not customer data. Those
  services must therefore never join to a matter-scoped table
  (`library-service.md` §6).
- **Cross-organisation access is a release blocker**, on the same footing as
  cross-matter disclosure (plan §9.2).

## 3. Capabilities, not role names in prose

Service docs previously gated on "an authorised lawyer" and refused "a clerk".
Neither is a role. `auth-service.md` defines exactly four roles, and its own
capability map granted `reviewer` the power to verify facts, which contradicted
`verification-service.md`. The fix is a capability catalogue: docs and code cite
a capability key, and one table maps roles to keys.

### 3.1 Capability catalogue

| Capability | Guards | Owning service |
| --- | --- | --- |
| `matter.create` | Creating a matter | `matter_service` |
| `matter.reclassify` | Appending a classification version | `matter_service` |
| `matter.close`, `matter.reopen`, `matter.archive` | Lifecycle commands | `matter_service` |
| `matter.membership.assign` | Adding or changing matter membership | `auth_service` |
| `document.upload`, `document.replace` | Evidence intake | `document_service` |
| `requirement.review` | Accepting or rejecting evidence against a requirement | `task_service` |
| `particular.verify`, `particular.correct`, `particular.add` | Verified-record decisions | `verification_service` |
| `finding.resolve`, `finding.waive` | Disposing of a check finding | `check_service` |
| `step.complete`, `step.override` | Workflow completion and authorised override | `task_service` |
| `deadline.confirm` | Confirming or correcting a hard legal deadline | `obligations_service` |
| `draft.create`, `draft.save`, `draft.restore` | Draft authoring | `draft_service` |
| `draft.submit-for-review` | Moving a draft to `in-review` | `draft_service` |
| `draft.approve` | The approval gate | `approval_service` |
| `export.create` | Rendering an approved instrument | `export_service` |
| `instrument.attest` | Recording an attestation in the notarial register | `notarial_register_service` |
| `register.certify-return` | Certifying a monthly return | `notarial_register_service` |
| `party.read-identity`, `party.record-identity` | Party identity evidence | `party_service` |
| `compliance.view`, `compliance.act` | Restricted sanctions and STR work | `party_service`, `obligations_service` |
| `content.author`, `content.approve`, `content.retire` | Governed content lifecycle | `content_governance_service` |
| `corpus.review`, `corpus.approve`, `corpus.quarantine` | Corpus governance | `corpus_governance_service` |
| `retention.hold`, `retention.release`, `retention.approve-destruction` | Retention and legal hold | `retention_service` |
| `billing.manage` | Checkout, cancel, reactivate, portal | `billing_service` |
| `platform.administer` | Plan administration across organisations | `billing_service` |
| `user.role.set` | Changing another user's role | `auth_service` |

A capability the map does not grant is denied. Capabilities are not additive by
seniority: an organisation owner is not automatically a legal approver.

### 3.2 Role to capability map

Roles are the four in `frontend/src/types/user.ts`. No fifth role is invented.

| Capability group | `reviewer` | `approver` | `maintainer` | `administrator` |
| --- | --- | --- | --- | --- |
| Matter lifecycle (`matter.*` except membership) | create only | yes | no | yes |
| Membership and roles (`matter.membership.assign`, `user.role.set`) | no | no | no | yes |
| Evidence (`document.*`, `requirement.review`) | yes | yes | no | no |
| Verified record (`particular.*`) | yes | yes | no | no |
| Findings (`finding.resolve`, `finding.waive`) | resolve only | yes | no | no |
| Workflow (`step.complete`, `step.override`) | complete only | yes | no | no |
| Deadlines (`deadline.confirm`) | no | yes | no | no |
| Drafting (`draft.create/save/restore/submit-for-review`) | yes | yes | no | no |
| Approval (`draft.approve`) | **no** | yes | no | no |
| Export (`export.create`) | no | yes | no | no |
| Attestation (`instrument.attest`, `register.certify-return`) | no | yes | no | no |
| Party identity (`party.*`) | yes | yes | no | yes |
| Compliance (`compliance.*`) | no | no | no | no — see §3.4 |
| Content governance (`content.*`) | no | no | yes | no |
| Corpus governance (`corpus.*`) | no | no | yes | no |
| Retention (`retention.*`) | no | no | no | yes |
| Billing (`billing.manage`) | no | no | no | yes |
| Platform (`platform.administer`) | no | no | no | no — see §3.4 |

`reviewer` cannot approve. That is the Phase 2 exit gate and the row is the
implementation of it.

### 3.3 "Lawyer" is a practising-status attribute, not a role

The phrase "only an authorised lawyer" in the plan's invariant 3 means two
things at once, and both must hold:

```text
authorised = has the capability (role map, §3.2)
lawyer     = User.notaryRegistration is present
             AND the user holds a current annual practice certificate
             AND the acting territory covers the matter's registration
                 jurisdiction, where the operation is territorial
```

`auth_service.authorize` checks the capability. The practising-status predicate
is evaluated by `auth_service.require_practising_notary(ctx, matter_id?)` and is
required by `instrument.attest`, `draft.approve`, `particular.verify`,
`finding.waive`, `step.override`, and `deadline.confirm`. Certificate currency
comes from the annual-certificate obligation
(`obligations-service.md` §7.1); territory comes from `User.jurisdiction`
(`auth-service.md` §7). An expired certificate blocks the capability rather than
silently allowing it.

The word "clerk" is retired from all service docs. The refusal case is
"an actor holding a capability the map does not grant".

### 3.4 Grants that are not role-derived

Two capability groups are not reachable through the four roles:

- `compliance.view` / `compliance.act` come from an explicit
  **compliance allowlist** on the organisation, naming the compliance officer
  and approved backups. Ordinary matter membership is never sufficient
  (`obligations-service.md` §17).
- `platform.administer` is a Draftly-staff capability on an internal
  organisation. A firm `administrator` cannot reach it
  (`billing-service.md` §11).

Both are assigned by an audited administrative action, and both are excluded
from `RequestContext` caching — they are re-read per request.

## 4. Membership has one writer

`auth_service` owns the `MatterMembership` and `OrganisationMembership` tables
and every write to them. `matter_service` previously also claimed membership
ownership and created the creator membership inside `create_matter`.

The resolution:

- `auth_service` exposes `assign_membership` and `remove_membership`, guarded by
  `matter.membership.assign`, and publishes `matter.membership-changed`.
- `matter_service` calls `MembershipCommandPort.grant_owner_membership(...)`
  inside its creation transaction. It never writes the table directly and never
  reads it except through `RequestContext`.
- `Matter.ownerId` is a responsibility pointer for display and assignment. It is
  **not** the authorisation policy. At migration, each `ownerId` produces one
  explicit membership row, after which memberships are the only source of truth
  (`auth-service.md` open decision 2).

## 5. Existence hiding — 404, not 403

For any **matter-scoped** resource, a caller who is not a member of that matter
receives `404 Not Found`, byte-identical to the response for a matter that does
not exist. A `403` would confirm the matter is real. The same applies across
organisations: a resource in another organisation is a 404.

Use `403` only when the caller **is** a member of the matter (so its existence is
already known to them) and lacks the capability. That is a policy refusal and it
names the missing capability:

```json
{
  "error": {
    "code": "capability_denied",
    "capability": "draft.approve",
    "message": "This action requires the draft.approve capability."
  }
}
```

Decision table:

| Caller state | Response |
| --- | --- |
| No valid token | 401 |
| Valid identity, pending or suspended account | 403 on the account-status route only; every other route 404 |
| Not a member of the organisation | 404 |
| Member of the organisation, not a member of the matter | 404 |
| Member of the matter, capability not granted | 403 with `capability_denied` |
| Member of the matter, capability granted, domain rule refuses | 409 or 422 with a domain error code (`api-conventions.md` §5) |

A denied attempt at a privileged action is audited
(`auth-service.md` §8) even though the caller sees a 404.

## 6. What must never be trusted from the client

- role, capability, organisation membership, matter membership;
- `actorId` on any write, including audit;
- entitlement or quota state;
- a content hash supplied for approval;
- a display policy for a legal source;
- a readiness flag, phase, blocking status, or progress counter;
- a delivery address for a notification;
- a payment or subscription state derived from a checkout redirect.

Each of these is re-derived server-side. The corresponding invariant row appears
in the owning service's doc.

## 7. Tests every service inherits

These live in `tests/security/` and run against every matter-scoped service.
They are parameterised over the service list in
`services/README.md`, so a new service is covered the day it is registered.

1. Cross-organisation read and write are denied for every route.
2. Cross-matter read and write are denied for every matter-scoped route.
3. A non-member receives a 404 whose body and timing are indistinguishable from
   a genuinely missing resource.
4. A member without the capability receives 403 `capability_denied`, and the
   attempt is audited.
5. A forged role, capability, organisation id, or `actorId` in a request body is
   ignored.
6. A pending or suspended account, and a suspended or closed organisation,
   cannot construct a privileged `RequestContext`.
7. `reviewer` cannot approve a draft, create an export, attest an instrument, or
   confirm a hard deadline.
8. A user without a current practice certificate cannot perform any capability
   listed in §3.3.
9. Compliance-restricted records return no record and no existence signal to an
   ordinary matter member.
10. No secret, raw token, or private matter value appears in logs, error bodies,
    or audit payloads.
