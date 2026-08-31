# Security model — tenancy, capabilities, and existence hiding

Companion to `backend/backend-implementation-plan-v0.md` §5.2 and Phase 2,
`services/auth-service.md`, and every matter-scoped service.

Three rules were previously restated — and drifted — in nine service docs:
the user boundary, the role gate, and the 404-not-403 rule. They are defined
here once. A service doc states *which capability* an operation needs and
otherwise points here.

## 1. The two independent gates

```text
request
  ├─ auth_service.authorize(ctx, capability, matter_id?)   ← may they?
  └─ billing_service.require_feature(user_id, feature_key)  ← is it paid for?
```

Both must pass. A paid plan never grants a capability, and a capability never
bypasses a plan or quota (`billing-service.md` §1). A service that performs a
metered operation calls both, in that order, and neither is optional because the
button was hidden in the browser.

## 2. User is the outer boundary

Every persisted row that belongs to a customer carries `user_id` (the owning
notary account). Not "most rows" — every one, including audit events,
notification deliveries, research conversations, session-memory episodes, voice
captures, obligations, and party records.

```text
filter by ctx.actorId (= user_id)   ← always, first
  then check matter ownership       ← when matter_service enforces owner_user_id
    then check capability           ← when the operation mutates or is privileged
```

The actor id comes from the server-built `RequestContext`, derived from the
verified identity subject and the persisted `User` record. A client-supplied
user id never establishes tenancy.

Consequences that the individual service docs previously missed:

- **Non-matter-scoped reads still have a tenant boundary.** The audit global
  feed, notification preferences, obligation lists, research conversations,
  session memory, and voice captures are all filtered by `user_id` before
  anything else.
- **The legal corpus is the one exception.** `library_service` and the corpus
  side of `research_service` read a published release that is not
  user-scoped, because approved statutes are not customer data. Those services
  must therefore never join to a matter-scoped table without also enforcing
  `user_id` on the matter side (`library-service.md` §6).
- **Cross-user access is a release blocker**, on the same footing as
  cross-matter disclosure (plan §9.2).

There is no organisation workspace in V0 auth. Subscriptions attach to
`user_id` (`billing-service.md`).

### 2.1 Blocking central decision — `user_id` versus `organisation_id`

**Status: open. Owner: the platform team. Blocks L2 for every service.**

Three cross-cutting documents disagree about what the tenant key is, and the
conflict is load-bearing rather than cosmetic:

| Document | Requires |
| --- | --- |
| This file, §2 and §4 | `user_id` is the outer boundary; there is no organisation workspace in V0 |
| `events.md` §2 | `organisationId` is **required on every event** |
| `service-definition-of-done.md` §4.1.5 | Every persisted table has a **non-null `organisation_id`** column, checked by a schema test |

So a new service cannot satisfy all three. It either omits `organisation_id`
and fails the schema test, or adds a column that §2 says does not describe a V0
tenant. `auth_service` already carries an exemption for `users` and
`user_identities` for exactly this reason, which is a symptom, not a resolution.

**What the code already does.** Every shipped table — `matters`,
`source_files`, `detected_documents`, `processing_runs`, `candidate_fields` and
the rest — carries `user_id` and **no** `organisation_id`. The running system
has already answered this question in favour of §2; `events.md` §2 and DoD
§4.1.5 are the documents out of step with it.

Until the decision is taken centrally, **new services follow the code**:
`user_id` only, no `organisation_id` column, and no per-service exemption. A
service-local exemption would let each service answer the question differently
and quietly retire a release-blocking gate, and a lone service carrying an
organisation column no other table has would be worse — it would look like a
tenancy boundary while enforcing nothing. Cross-organisation disclosure remains
on the release-blocker list (`service-definition-of-done.md` §7), which is why
this needs resolving rather than absorbing.

The decision to take: either V0 gains a real organisation aggregate and §2 is
rewritten around it, or `organisation_id` is retired from `events.md` §2 and
DoD §4.1.5 in favour of `user_id` and the `auth_service` exemption is removed.
Both are one-way doors for the schema, so this is not a per-service call.

## 3. Capabilities, not role names in prose

Service docs previously gated on "an authorised lawyer". Neither "lawyer" nor
"clerk" is a role. `auth-service.md` defines exactly four roles, and
authorization is expressed through capability keys.

### 3.1 Capability catalogue

| Capability | Guards | Owning service |
| --- | --- | --- |
| `matter.create` | Creating a matter | `matter_service` |
| `matter.reclassify` | Appending a classification version | `matter_service` |
| `matter.close`, `matter.reopen`, `matter.archive` | Lifecycle commands | `matter_service` |
| `matter.membership.assign` | *(unused in V0 — no matter membership join in auth)* | — |
| `document.upload`, `document.replace` | Evidence intake | `document_service` |
| `requirement.review` | Accepting or rejecting evidence against a requirement | `task_service` |
| `particular.verify`, `particular.correct`, `particular.add` | Verified-record decisions | `verification_service` |
| `finding.resolve`, `finding.waive` | Disposing of a check finding | `check_service` |
| `check.run` | Running deterministic checks on a matter | `check_service` |
| `step.complete`, `step.override` | Workflow completion and authorised override | `task_service` |
| `checklist.administer` | The dedicated checklist-administration command as a whole | `task_service` |
| `checklist.assign` | Changing a checklist item's assignee | `task_service` |
| `checklist.update-due-date` | Changing a checklist item's due date | `task_service` |
| `checklist.request-collection` | Moving collection state to REQUESTED | `task_service` |
| `note.create` | Saving a non-authoritative matter working note | `matter_agent_service` |
| `checklist.record-receipt` | Recording that a document was physically received | `task_service` |
| `checklist.suggest-item` | Creating an ad-hoc AI_SUGGESTED checklist item | `task_service` |
| `document.propose-link` | Creating an unverified document-to-parcel or document-to-requirement link | `document_service` |
| `candidate.create`, `candidate.update` | Unverified structured-field candidates | `verification_service` |
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
| `platform.administer` | Plan administration (Draftly staff) | `billing_service` |
| `user.role.set` | Changing another user's role | `auth_service` |

A capability the map does not grant is denied. Capabilities are not additive by
seniority.

The four `checklist.*` keys work as an umbrella plus a narrow key: a checklist
write requires `checklist.administer` **and** the specific key for the field
being changed, so the field operations stay independently grantable and
independently revocable. `checklist.administer` alone grants nothing.

`checklist.record-receipt` records that a document arrived. It is deliberately
not `requirement.review`, which is the evidence-acceptance gate. *We received
something* and *a lawyer accepted it as legally sufficient* are different
decisions, and only the second is a legal act. The same line separates
`candidate.create`/`candidate.update` from `particular.verify`: a candidate is a
proposal, and no candidate may overwrite a verified value.

### 3.2 Role to capability map

Roles are the four in `frontend/src/types/user.ts`. No fifth role is invented.

| Capability group | `reviewer` | `approver` | `maintainer` | `administrator` |
| --- | --- | --- | --- | --- |
| Matter lifecycle (`matter.*` except unused membership) | create only | yes | no | yes |
| Roles (`user.role.set`) | no | yes | no | yes |
| Evidence (`document.*`, `requirement.review`) | yes | yes | no | no |
| Matter administration (`check.run`, `note.create`, `checklist.administer`, `checklist.assign`, `checklist.update-due-date`, `checklist.request-collection`, `checklist.record-receipt`, `checklist.suggest-item`) | yes | yes | no | no |
| Candidates and links (`candidate.create`, `candidate.update`, `document.propose-link`) | yes | yes | no | no |
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
| Retention (`retention.*`) | no | yes | no | yes |
| Billing (`billing.manage`) | no | yes | no | yes |
| Platform (`platform.administer`) | no | no | no | no — see §3.4 |

`reviewer` cannot approve. That is the Phase 2 exit gate.

Solo practitioners provisioned as `approver` receive billing, retention, and
`user.role.set` without a separate organisation admin role.

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
`finding.waive`, `step.override`, and `deadline.confirm`.

The word "clerk" is retired from all service docs. The refusal case is
"an actor holding a capability the map does not grant".

None of the six matter-administration keys is territorial, so none joins the
`require_practising_notary` set.

### 3.5 Agent-mediated execution

`matter_agent_service` executes tools on a user's behalf. It has **no identity
of its own** and is never a principal. Its effective permission is an
intersection, never a union:

```text
effective = authenticated user's capabilities
          ∩ agent tool allowlist
          ∩ matter ownership
```

- The agent can never exceed the user driving it, and a user can never reach an
  omitted capability by asking the agent. A `reviewer` using the agent has a
  reviewer's powers.
- The allowlist is a positive server-side registry. A capability absent from it
  is unreachable even for a user who holds it, so a prompt injection reaching
  for a prohibited action fails at the executor rather than at the model's
  discretion.
- Matter ownership is re-derived from `RequestContext` on every tool call, never
  carried over from the turn that proposed the action.
- Both executed and denied tool calls are audited, per §5.

### 3.4 Grants that are not role-derived

Two capability groups are not reachable through the four roles:

- `compliance.view` / `compliance.act` come from an explicit
  **compliance allowlist** on the user account (or future firm policy), naming
  the compliance officer and approved backups. Ordinary matter access is never
  sufficient (`obligations-service.md` §17).
- `platform.administer` is a Draftly-staff capability. A firm
  `administrator` cannot reach it (`billing-service.md` §11).

Both are assigned by an audited administrative action, and both are re-read per
request.

## 4. Matter ownership in V0 — no membership join

There is **no** `MatterMembership` table in auth for V0. Matter access is
**user-owned**: when `matter_service` ships, each matter carries
`owner_user_id` equal to the creating notary's `user_id`. Authorisation for
matter mutations is **capability-only** through `auth_service.authorize` until
ownership checks are wired in `matter_service`.

- `auth_service` does not expose `assign_membership` in the solo model.
- `matter_service` creates matters scoped to `ctx.actorId` and sets
  `owner_user_id` accordingly.
- Cross-user matter reads return **404, not 403** once ownership is enforced
  (`§5`).

Historical docs that described `MembershipCommandPort` and dual writers are
superseded for V0.

## 5. Existence hiding — 404, not 403

For any **matter-scoped** resource, a caller who does not own the matter (or
is not permitted by future sharing rules) receives `404 Not Found`, byte-
identical to the response for a matter that does not exist. A `403` would
confirm the matter is real. The same applies across users: a resource belonging
to another `user_id` is a 404.

Use `403` only when the caller **already has legitimate visibility** of the
matter and lacks the capability. That is a policy refusal:

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
| Resource owned by another user | 404 |
| Owner of the matter, capability not granted | 403 with `capability_denied` |
| Owner, capability granted, domain rule refuses | 409 or 422 with a domain error code (`api-conventions.md` §5) |

A denied attempt at a privileged action is audited even when the caller sees a
404.

## 6. What must never be trusted from the client

- role, capability, or tenancy (`user_id`);
- `actorId` on any write, including audit;
- entitlement or quota state;
- a content hash supplied for approval;
- a display policy for a legal source;
- a readiness flag, phase, blocking status, or progress counter;
- a delivery address for a notification;
- a payment or subscription state derived from a checkout redirect.

Each of these is re-derived server-side.

## 7. Tests every service inherits

Auth capability checks currently live in `tests/unit/` (CI collects
`tests/unit`, `tests/contract`, and `tests/conformance`). The shared
cross-service security suite will land under `tests/security/` and run
against every matter-scoped service, parameterised over the service list in
`services/README.md`.

1. Cross-user read and write are denied for every route.
2. Cross-matter read and write are denied for every matter-scoped route.
3. A non-owner receives a 404 whose body and timing are indistinguishable from
   a genuinely missing resource.
4. An owner without the capability receives 403 `capability_denied`, and the
   attempt is audited.
5. A forged role, capability, `user_id`, or `actorId` in a request body is
   ignored.
6. A pending or suspended account cannot construct a privileged
   `RequestContext`.
7. `reviewer` cannot approve a draft, create an export, attest an instrument, or
   confirm a hard deadline.
8. A user without a current practice certificate cannot perform any capability
   listed in §3.3.
9. Compliance-restricted records return no record and no existence signal to an
   ordinary matter owner.
10. No secret, raw token, or private matter value appears in logs, error bodies,
    or audit payloads.
