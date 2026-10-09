# matter_service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`task-service.md`, `auth-service.md`, `billing-service.md`,
`audit-service.md`, and `obligations-service.md`. One markdown file is kept per
service under `backend/docs/services/`.

This service is the root record and security boundary for a legal matter. It
identifies the transaction being handled; it does not define or run the
notarial workflow.

## 1. Decision

`matter_service` owns matter identity, classification, access, and lifecycle.
`task_service` compiles and runs the correct lawyer-approved workflow for that
classification.

```text
matter_service
  = what transaction is this, who may access it, and is it active?

task_service
  = which approved work applies, what phase is current, and what remains?
```

The old model mixed four different concepts:

```text
status = open | in-review | blocked | ready-to-draft | closed
activeFunction = examination | drafting | execution | attestation
progress = four mutable counters
```

That model is retired for the backend contract. Lifecycle, workflow phase,
blocking, and readiness are separate:

```text
lifecycleStatus = inquiry | active | closed | archived
currentPhase = task-service projection
blockingStatus = task-service projection
readiness = task-service projection
```

No client can set `blocked`, `ready-to-draft`, `currentPhase`, progress, or a
readiness flag through a matter patch.

## 2. What it owns

The service owns:

- matter id, `user_id`, privacy-safe reference, and client reference;
- the association between the matter and its team, expressed by calling
  `auth_service`; the membership table itself is owned there;
- transaction type and registration regime;
- relevant registration jurisdiction;
- instrument language;
- assigned notary;
- versioned matter classification;
- lifecycle from inquiry through closure and archive;
- acceptance metadata;
- party references, not raw identity records — the records themselves live in
  `party_service`;
- optimistic concurrency version;
- creation, activation, reclassification, closure, reopening, and archive; and
- events that notify specialist services of those changes.

It does not own:

- workflow definitions or modules;
- WorkflowRun or StepRun records;
- current operational phase as authoritative state;
- document requirements or uploaded files;
- verified legal particulars;
- deterministic findings;
- draft text or approvals;
- deadline calculations;
- notification templates or delivery;
- plans, subscriptions, payment state, or usage accounting; or
- editable progress and readiness booleans.

## 3. Where it sits

```text
GET   /matters
POST  /matters
GET   /matters/{id}
PATCH /matters/{id}
POST  /matters/{id}/activate
POST  /matters/{id}/reclassify
POST  /matters/{id}/close
POST  /matters/{id}/reopen
POST  /matters/{id}/archive
              |
              v
      api/v1/matters.py
              |
              v
 application/matter_service.py
              |
              +--> MatterRepository
              +--> MembershipCommandPort      (auth_service owns the table)
              +--> MatterProjectionPort
              +--> PartyReadPort
              +--> BillingEntitlementPort
              +--> EventPort
              +--> AuditPort
```

The router authenticates and parses only. The application service takes an
authenticated `RequestContext` containing actor, role, and
matter memberships. It imports no FastAPI, SQLAlchemy, task-service domain
objects, or identity-provider SDK.

`MatterProjectionPort` reads the task-owned operational projection used in
`MatterRead`. It does not let `matter_service` mutate workflow state.

## 4. Matter model

### 4.1 Matter

```text
Matter
  id
  user_id
  reference
  clientReference?
  transactionType
  registrationRegime
  registrationJurisdictionId?
  instrumentLanguage?
  assignedNotaryId?
  classificationVersion
  lifecycleStatus
  acceptedAt?
  acceptedBy?
  ownerId
  createdAt
  updatedAt
  version
```

The authoritative enums are:

```text
MatterLifecycleStatus =
  inquiry | active | closed | archived

MatterType =
  transfer | gift | lease | mortgage | other

RegistrationRegime =
  rta | deed | condominium | special-area

InstrumentLanguage =
  en | si | ta
```

`inquiry` is an access-controlled root record before client acceptance and the
main legal workflow. `active` means the matter has passed the configured
acceptance gate and may run approved legal work.

### 4.2 MatterClassification

The classification is versioned because it determines workflow modules,
document requirements, checks, templates, and deadline rules:

```text
MatterClassification
  matterId
  version
  transactionType
  registrationRegime
  registrationJurisdictionId?
  instrumentLanguage?
  propertyCharacteristics
  executionCircumstances
  changedBy
  changedAt
  reason?
```

`propertyCharacteristics` and `executionCircumstances` contain stable
classification keys or references to verified facts. They must not duplicate
raw client identity or unverified OCR output.

Examples that may select conditional modules include:

```text
whole land
divided share
undivided share
condominium parcel
corporate party
trust
power of attorney
minor party
reserved life interest
```

Registration regime and property characteristics remain distinct. A gift
under deed registration and a gift under title registration must compile
different regime modules.

### 4.3 Party references

```text
MatterPartyReference
  id
  matterId
  role
  partyRecordId        -> party_service.Party.id
```

The matter owns the association and transaction role, not the underlying raw
identity record. Names, identity numbers, addresses, beneficial-owner data, and
identity evidence live in **`party_service`** — the protected identity tier that
`partyRecordId` points into (`party-service.md`). That tier was previously
referenced here and documented nowhere.

### 4.4 Membership

`MatterMembership` is owned and written by `auth_service`
(`security-model.md` §4). Matter-service reads it only through
`RequestContext` and creates the owner's membership by calling
`MembershipCommandPort`.

Membership roles are application roles, distinct from transaction-party roles.
Every matter-scoped service re-checks `user_id` scope and then ownership
server-side. `ownerId` is a primary responsibility pointer; it is not the
authorization policy.

## 5. Canonical workflow phases

The operational workflow uses ten canonical phases:

```text
WorkflowPhase =
  intake
  classification
  document-collection
  title-examination
  issue-resolution
  drafting
  pre-execution
  execution
  registration
  closure
```

`task_service` owns the phase definitions, steps, completion state, and current
phase. The matter read model exposes the result for navigation and summaries.

The existing four-function UI remains a presentation grouping:

```text
Examination
  intake
  classification
  document-collection
  title-examination
  issue-resolution

Drafting
  drafting

Execution
  pre-execution
  execution

Attestation and registration
  registration
  closure
```

This mapping may evolve without changing canonical stored phases. The frontend
must not treat an aggregate UI band as the legal workflow definition.

## 6. Operational read projection

`MatterRead` combines matter-owned fields with a task-owned projection:

```text
MatterOperationalProjection
  matterId
  workflowRunId?
  workflowSetupStatus = pending | ready | failed
  currentPhase?
  blockingStatus = clear | blocked
  blockerIds
  readiness
  nextActionKey?
  evaluatedAt
  sourceVersion
```

```text
MatterReadinessSummary
  readyToDraft
  readyToExecute
  readyToRegister
  readyToClose
```

The summary is not authoritative by itself. Detailed
`ReadinessEvaluation` records, including blocker and dependency versions, are
owned by `task_service`.

The projection may be cached for list performance, but every value carries its
source version and can be rebuilt. It is never accepted from a browser patch.

## 7. Lifecycle

```text
inquiry --activate--> active --close--> closed --archive--> archived
                         ^                |
                         |----reopen------|
```

Rules:

- Creation starts an `inquiry`.
- Activation requires the approved intake and acceptance policy.
- Closing requires a task-owned `readyToClose` evaluation.
- Reopening requires an authorised lawyer, a non-empty reason, and an audit
  event.
- Archiving is an access/lifecycle decision; it does not delete records.
- An archived matter is read-only to ordinary users.

Lifecycle does not change because a check fails. An active matter with a
blocking finding remains:

```text
lifecycleStatus = active
blockingStatus = blocked
```

## 8. Application methods

### 8.1 list_matters

```text
list_matters(ctx, filters) -> page[MatterRead]
```

Returns only matters visible through `user_id` and ownership policy.
Filters include lifecycle, transaction type, regime, assigned notary, and
projected phase. Projection joins are server-side.

### 8.2 get_matter

```text
get_matter(ctx, matter_id) -> MatterRead
```

Re-checks membership. A non-member receives 404, not 403. Returns the current
classification and operational projection without compiling or mutating a
workflow.

### 8.3 create_matter

```text
create_matter(ctx, input) -> MatterRead
```

1. Validate `user_id`, privacy-safe reference, transaction type, and
   registration regime.
2. Require the actor's `matter.create` entitlement and atomically check
   any active-matter quota through `BillingEntitlementPort`.
3. Create `Matter(lifecycleStatus=inquiry, classificationVersion=1)`.
4. Create the initial MatterClassification.
5. Call `MembershipCommandPort.grant_owner_membership(matter_id, ctx.actorId)`
   in the same transaction. This service does not write the membership table
   itself; `auth_service` owns it and publishes `matter.membership-changed`
   (`security-model.md` §4).
6. Write the `matter.created` audit row and outbox event.
7. Return `workflowSetupStatus=pending`.

The creation transaction does not create StepRuns, seed facts, or clone checks.
Subscription state never grants matter access; `auth_service` capability and
role checks run before this entitlement gate.

`task_service` consumes `matter.created` idempotently and compiles the approved
intake and classification workflow. The UI must show pending, ready, or failed
setup explicitly.

### 8.4 activate_matter

```text
activate_matter(ctx, matter_id, acceptance_evidence) -> MatterRead
```

1. Require an authorised lawyer or approved intake role.
2. Ask `task_service` for the current intake activation gate.
3. Refuse activation while required acceptance, conflict, or applicable CDD
   steps remain blocked, pending, or stale.
4. Record accepted actor and server time.
5. Transition `inquiry -> active`.
6. Emit `matter.activated` and audit the decision.

The service records the activation decision but does not own or duplicate the
underlying CDD and conflict steps.

### 8.5 update_matter

```text
update_matter(ctx, matter_id, patch, expected_version) -> MatterRead
```

Permitted ordinary fields are narrowly scoped, such as privacy-safe references
and assigned responsibility. Transaction type, registration regime,
jurisdiction, and language changes use `reclassify_matter`; lifecycle changes
use explicit commands.

The route rejects workflow phase, progress, blocking, and readiness fields.

### 8.6 reclassify_matter

```text
reclassify_matter(
  ctx,
  matter_id,
  classification,
  reason,
  expected_version
) -> MatterRead
```

1. Require an authorised lawyer.
2. Require a non-empty reason after activation.
3. Append MatterClassification version N+1; never overwrite version N.
4. Update the matter classification pointer atomically.
5. Emit `matter.classification-changed` with old and new version references.
6. Audit the before/after classification references and reason.

`matter_service` does not modify the current WorkflowRun.
`task_service` decides whether the change is material:

```text
transaction type or registration regime changed
  -> supersede the current run and compile a new approved run

conditional characteristic changed
  -> re-evaluate pinned candidate conditional steps
```

The lawyer confirms any evidence remapping. No previous run, decision, or
override is deleted.

### 8.7 close_matter

```text
close_matter(ctx, matter_id, reason?) -> MatterRead
```

Requires an authorised lawyer and a current `readyToClose` evaluation. Closure
records the final workflow run and readiness-evaluation references. A policy
override, if permitted, requires a reason and separate audit action.

### 8.8 reopen_matter

```text
reopen_matter(ctx, matter_id, reason) -> MatterRead
```

Requires an authorised lawyer and a non-empty reason. It transitions
`closed -> active`, emits `matter.reopened`, and causes `task_service` to mark
the closure phase stale or instantiate the approved reopening workflow.

## 9. Events

The service publishes through the transactional outbox:

```text
matter.created
matter.activated
matter.classification-changed
matter.assigned-notary-changed
matter.closed
matter.reopened
matter.archived
```

`matter.membership-changed` is **not** published here. `auth_service` owns every
membership write and publishes that event (`security-model.md` §4).

Consumers must be idempotent. Events carry matter, user_id,
classification, actor, version, and correlation identifiers. They do not carry
raw party identity, property descriptions, or private evidence.

The service consumes task-owned projection events:

```text
workflow.instantiated
workflow.setup-failed
workflow.phase-changed
workflow.readiness-changed
workflow.blocking-changed
workflow.run-superseded
```

`task_service` previously wrote `workflow.instantiated`,
`workflow.setup-failed`, and `workflow.blocking-changed` only as audit rows, so
this projection never updated and a matter could sit at
`workflowSetupStatus = pending` indefinitely. All three are now required outbox
publications (`task-service.md` §9).

Those events update a rebuildable read projection, not the authoritative Matter
aggregate.

## 10. Invariants

| Invariant | Enforcement |
| --- | --- |
| Matter is the access root | Every matter-scoped operation re-checks `user_id` and ownership |
| Lifecycle is not workflow state | Inquiry/active/closed/archived only; blocking and readiness are projections |
| Current phase is task-owned | Matter exposes a projection and rejects client phase/progress writes |
| Classification history is immutable | Reclassification appends a version and emits an event |
| Workflow creation is outside matter | `matter.created` is consumed idempotently by `task_service` |
| Closure is derived-gate protected | Current `readyToClose` evaluation required |
| Reopening is explicit | Lawyer role, reason, audit event, and workflow invalidation |
| Existence is hidden | Non-member reads and writes return 404 |
| Every material mutation is audited | Matter and audit writes share a transaction |
| Private identity stays outside the root | Matter stores party references, not raw identity values |

## 11. Failure modes

- Workflow compilation after creation fails: keep the inquiry and projection
  `failed`; allow governed retry. Do not delete the matter.
- Matter is activated while intake prerequisites are stale: refuse activation.
- Browser submits `readyToDraft=true`: reject the field.
- Two actors reclassify concurrently: optimistic version rejects the stale
  write.
- Classification changes while work is active: preserve the old run until
  `task_service` supersedes it; show setup/reclassification pending.
- New workflow cannot compile after reclassification: keep the old run as
  historical, block new work, and surface the governance error.
- Closed matter requested for mutation: reject except authorised reopen or
  archive.
- Assignee is removed from membership: require reassignment before removal or
  apply the approved fallback policy.
- Projection is unavailable: return matter-owned state with projection
  explicitly unavailable; never invent readiness.

## 12. Test list

### Unit

- Inquiry, active, closed, archived lifecycle transitions.
- Activation gate and closure gate.
- Reopen requires lawyer role and reason.
- Reclassification appends rather than overwrites.
- Matter patch rejects phase, progress, blocking, and readiness.
- Optimistic concurrency.

### Contract

- New Matter and MatterClassification schemas.
- Nullable jurisdiction, language, and assigned notary during inquiry.
- MatterRead operational projection.
- Removal of mixed `MatterStatus`, `activeFunction`, and mutable progress from
  the M3 contract.
- Frontend migration mapping from the M2 mock type.

### Integration

- Create writes matter, classification, membership, audit, and outbox event
  atomically.
- `matter.created` produces one intake WorkflowRun on replay-safe consumption.
- Activation refuses incomplete intake and succeeds after approved completion.
- Material reclassification supersedes the old run without losing history.
- Conditional classification change re-evaluates the pinned run.
- Closure uses the exact readiness-evaluation version.
- Reopen audits and invalidates closure state.

### Security

- Cross-user and cross-matter isolation.
- Matter creation enforces the user entitlement and active-matter
  quota server-side.
- Non-member receives 404.
- Browser cannot assign itself a role or team membership.
- Non-lawyer cannot reclassify, close with override, or reopen.
- Events, audit rows, logs, and projections exclude raw private data.

## 13. Frontend migration

M2 keeps its mock contract and four-function presentation. M3 changes the API
read model:

```text
status
  -> lifecycleStatus + blockingStatus

activeFunction
  -> currentPhase + presentation grouping

progress counters
  -> task-owned phase completion projection

ready-to-draft
  -> readiness.readyToDraft with blocker details
```

The frontend must render setup pending/failed, inquiry versus active, canonical
phase, blocking reason, and readiness provenance without letting users directly
edit derived values.

## 14. Decisions to confirm before coding

### Approved matter scope records (2026-10-09)

`MatterSubjectReference` is a stable matter-local `party` or `parcel` reference
with an ordinal, not a raw identity record. Protected party identity remains
party-owned. `MatterTransactionReference` records parcel subject IDs and explicit
party-role associations. V0 validates the owner and matter for every reference;
organization support remains deferred. There is no automatic cross-matter merge
or implied transferee assignment from a source identity card.

`GET/POST /matters/{matterId}/subjects` and `/transactions` expose these records.
List reads accept bounded `limit` (maximum 100) and signed `cursor`.
`POST /transactions/{transactionId}/associations` replaces the association set
with `If-Match`, appends a transaction revision, and returns an ETag. Creating
and association commands require `Idempotency-Key`, authorize `CAP_MATTER_ROUTE`,
and append reference-only audit in the request transaction. They store no names,
NICs or addresses. `MatterScopePort.lock` serializes these writes with canonical
verification review; `validate_scope` and `get_transaction` are the public ports
for other owners. The database migration ships with these records.

Matter creation also requires `Idempotency-Key` at the HTTP boundary. The owning
service fingerprints the submitted intake metadata and serializes replay through
the existing public idempotency port. Replaying an authorized create intent
returns its existing owned matter; changing the body under that key conflicts.
Document corrections and current-evidence consumers share `MatterMutationLockPort`
so review, linking, checking and output eligibility cannot interleave with stale
interpretation authority inside the same matter transaction.

1. Use `inquiry | active | closed | archived` as the matter lifecycle.
2. Keep the ten canonical workflow phases in `task_service`.
3. Expose phase, blocking, and readiness through a rebuildable matter
   projection.
4. Require explicit activation after the approved intake gate.
5. Append MatterClassification versions on reclassification.
6. Supersede a WorkflowRun for transaction-type or regime changes; re-evaluate
   candidate steps for conditional characteristic changes.
7. Require current readiness evaluation for closure and a reason to reopen.
8. Replace embedded party identity data with protected party references.

### Association revision dependency synchronization (2026-10-09)

Updating an existing transaction association revision notifies the owning check
and form ports under the existing shared matter mutation lock. Checks in that
transaction become inconclusive; forms bound to its reviewed facts become stale
with SCOPE_ASSOCIATION_CHANGED. Fact values and association history are preserved.
The public scope read contract exposes owned transaction/subject references; callers
must retain the displayed associationVersion and deliberately renew after 412.

### Scope command retry metadata (2026-10-09)

Subject and transaction creation and association edits retain opaque pending keys,
request digests and original expected versions through the shared browser mutation
intent helper. Fact decisions use the same metadata-only mechanism. Actor identity
and mutation share one captured token, held only in memory; persisted keys are
actor/matter/operation scoped. Raw scopes, facts, reasons and tokens are not stored.
Successful responses clear the pending intent so a deliberate repeated create is a
new operation. Ambiguous responses retain the original request key; known 412
refusals clear it and require renewed review. Unavailable browser storage retains
the existing visible RAM-fallback notice. Refresh/re-entry behavior is untested
under the owner's explicit test waiver.
