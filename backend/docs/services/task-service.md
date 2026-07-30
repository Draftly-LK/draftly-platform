# task-service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`content-governance-service.md`, `document-service.md`,
`verification-service.md`, and `memory-service.md`.

This service maps to Phase 5 of the backend plan, the Tasks API, and the
invariant that a mandatory blocked step requires new evidence or a recorded
authorised override.

V0 is RTA-first. Its first governed checklist is compiled from an approved base
workflow, an RTA module, a transaction module, and any approved conditional
modules that apply to the matter. Deed-registration and other regimes can use
the same mechanism after their content has been reviewed and approved.

## 1. What it owns

The service compiles and runs an ordered, role-gated notarial checklist for one
matter. Compilation combines approved definitions into a versioned,
matter-specific run.

It owns:

- deterministic module selection from the matter's registration regime and
  transaction type;
- deterministic applicability evaluation against verified or corrected facts;
- the compilation record, including definition, fact, and document versions;
- the run state of each compiled step;
- completion, blocking, and authorised override decisions; and
- invalidation when a relied-on fact or document changes.

The service does not author workflow or module definitions.
`content-governance-service` owns those definitions and their
`draft -> approved -> retired` lifecycle. `check_service` runs deterministic
legal and consistency checks. `verification_service` promotes candidate
particulars into verified or corrected facts. `task_service` reads those facts
and checks but does not modify them.

Generated prose stays outside this service. An AI component may suggest that a
condition needs review, but it cannot add, remove, waive, or complete a step.
Only approved definitions and deterministic conditions affect the compiled
checklist.

## 2. Where it sits

```text
POST /matters/{id}/workflows/instantiate
GET  /matters/{id}/workflows
POST /matters/{id}/workflows/{runId}/re-evaluate
POST /matters/{id}/workflows/{runId}/steps/{stepRunId}/complete
                              |
                              v
                      api/v1/tasks.py
                              |
                              v
             application/task_service.py
                              |
          +-------------------+-------------------+
          |                   |                   |
WorkflowDefinitionPort  WorkflowRunPort  VerifiedFactReadPort
StepRunPort             DocumentReadPort EventPort / AuditPort
```

The router authenticates and parses requests. The application service takes a
resolved `RequestContext` containing the actor, roles, and matter memberships.
It orchestrates domain objects and ports without importing FastAPI, SQLAlchemy,
or provider SDKs.

The current frontend only calls the list and completion routes. Instantiation,
re-evaluation, and the expanded step states must be added when the frontend is
connected to this backend.

## 3. Governed definitions

Governed definitions are versioned and read-only to this service.

### 3.1 WorkflowDefinition

The approved base for a notarial function:

```text
WorkflowDefinition
  id
  titleKey
  kind = base
  function = examination | drafting | execution | attestation
  approvalState = draft | approved | retired
  language = en | si | bilingual
  ownerId
  version
  effectiveFrom?
  effectiveTo?
  steps: StepDefinition[]
```

### 3.2 WorkflowModule

A reusable group of approved steps:

```text
WorkflowModule
  id
  titleKey
  kind = transaction | registration-regime | conditional
  registrationRegimes: string[]
  transactionTypes: string[]
  applicability?
  approvalState
  language
  ownerId
  version
  effectiveFrom?
  effectiveTo?
  steps: StepDefinition[]
```

Examples of module selection are:

```text
base examination workflow
  + transfer transaction module
  + RTA registration-regime module
  + power-of-attorney conditional module, when applicable
```

V0 must not maintain a separate permanent template for every possible
combination of facts. A small set of reviewed modules is safer to version and
maintain.

### 3.3 StepDefinition

```text
StepDefinition
  id
  definitionId
  order
  titleKey
  objectiveKey
  mandatory
  applicability?
  requiredFactKeys: string[]
  requiredDocumentTypes: string[]
  authority: Authority
  sourceExcerpt
  rules: StepRule[]
```

Definitions use stable fact keys and document types. They never contain
matter-specific database IDs.

`StepRule` remains descriptive guidance:

```text
StepRule
  id
  labelKey
  keywords: string[]
```

### 3.4 ApplicabilityCondition

An applicability condition is a versioned declarative expression over:

- the matter's registration regime and transaction type;
- other approved matter classifications; and
- verified or corrected fact values.

Supported operators come from an allowlist:

```text
equals
not-equals
in
exists
all
any
not
```

Definitions cannot contain executable code or provider prompts.

Registration regime and property characteristics should not be collapsed into
one field. RTA and deed registration are registration regimes. Condominium
status, special-area restrictions, and similar conditions should be separate
matter classifications or verified facts unless the domain model expressly
defines them otherwise.

## 4. Matter-specific run models

The backend separates governed definitions from matter run state.

### 4.1 WorkflowRun

```text
WorkflowRun
  id
  matterId
  baseDefinitionId
  baseDefinitionVersion
  moduleVersions
  compiledAt
  compiledBy
  matterClassificationVersion
  status = active | stale | closed
```

`moduleVersions` records every transaction, registration-regime, and
conditional module used during compilation.

### 4.2 StepRun

```text
StepRun
  id
  workflowRunId
  stepDefinitionId
  definitionVersion
  state
  applicability
  applicabilityReason
  evaluatedFactVersions
  evaluatedDocumentVersions
  note?
  overrideReason?
  completedBy?
  completedAt?
  version
```

The applicability fields explain why the step was included, excluded, or left
pending. `version` supports optimistic concurrency.

```text
ApplicabilityResult =
  applicable | not-applicable | unknown

StepState =
  pending-applicability |
  not-started |
  in-progress |
  complete |
  blocked |
  not-applicable |
  stale
```

The current frontend only understands `not-started`, `in-progress`, `complete`,
and `blocked`. Its type and rendering contract must be expanded before the
backend returns the additional states.

## 5. Applicability rules

Applicability uses three-valued logic:

```text
condition is true    -> applicable
condition is false   -> not-applicable
condition unresolved -> unknown
```

`unknown` is not equivalent to `false`. A condition is unresolved when it
depends on a fact that is:

- missing;
- unreviewed;
- in conflict;
- blocked;
- stale; or
- no longer supported by a current document version.

An unknown condition creates a `pending-applicability` StepRun. If that step
could be mandatory, it prevents downstream approval until the condition is
resolved.

The state transitions are:

```text
unknown applicability -> pending-applicability
false applicability   -> not-applicable
true applicability    -> not-started -> in-progress -> complete
                                      \-> blocked -> in-progress

relied-on fact or document changes -> stale -> lawyer-reviewed re-evaluation
```

Applicability and prerequisites answer different questions:

- Applicability determines whether the step belongs in this matter.
- Prerequisites determine whether an applicable step can be completed.

## 6. Ports

- `WorkflowDefinitionRepository`: loads approved base workflows and modules by
  registration regime, transaction type, effective date, and applicability
  metadata. `content-governance-service` owns the write side.
- `WorkflowRunRepository`: persists compilation records and pinned definition
  versions.
- `StepRunRepository`: persists matter-scoped StepRun rows with optimistic
  concurrency.
- `VerifiedFactReadPort`: reads verified or corrected facts, their versions,
  and their verification states.
- `DocumentReadPort`: resolves requirements by document type and returns the
  current processed document versions.
- `EventPort`: consumes fact-correction and document-supersession events and
  publishes workflow-staleness events through the transactional outbox.
- `AuditPort`: records every material workflow transition.

## 7. Application methods

### 7.1 instantiate_workflow

```text
instantiate_workflow(ctx, matter_id) -> WorkflowRunRead
```

1. Re-check matter membership. Return 404 for a non-member.
2. Read the matter's current registration regime, transaction type, and
   classification version.
3. Resolve exactly one approved base definition and the approved transaction
   and registration-regime modules effective at compilation time.
4. Read current verified or corrected facts and processed document versions.
5. Evaluate approved conditional modules and step conditions with three-valued
   logic.
6. Create a WorkflowRun that pins the base version, every selected module
   version, matter classification version, and compilation time.
7. Create a StepRun for every candidate step. Store its applicability result,
   reason, and the fact and document versions used.
8. Preserve non-applicable steps in the run for audit.
9. Persist the run, step runs, and `workflow.instantiated` audit event in one
   transaction.

Ambiguous or missing governed content is a configuration error. The compiler
must not choose a matching definition by list order.

Compilation is deterministic. The same approved definitions, matter
classification, fact versions, and document versions produce the same StepRun
set. AI suggestions are not compilation inputs.

### 7.2 list_workflows

```text
list_workflows(ctx, matter_id) -> list[WorkflowRunRead]
```

1. Re-check matter membership. Return 404 for a non-member.
2. Load persisted runs for the matter.
3. Join each run to its pinned definitions and StepRun rows.
4. Return definition content and run state in the shape required by the
   frontend.

A read must not compile, re-evaluate, or alter a run as a side effect.

### 7.3 re_evaluate_workflow

```text
re_evaluate_workflow(ctx, matter_id, run_id) -> WorkflowRunRead
```

1. Re-check membership and require an authorised lawyer.
2. Load the pinned run and the current matter classification, fact versions,
   and document versions.
3. Re-evaluate only steps affected by a changed dependency.
4. Append a new applicability evaluation record. Do not overwrite the previous
   reason or dependency versions.
5. Never silently reopen or delete a completed step. Mark it `stale` and
   require the lawyer to confirm the new result or perform the step again.
6. Move a previously non-applicable step that becomes applicable to
   `not-started`.
7. Move a step whose condition becomes unknown to
   `pending-applicability`.
8. Audit every changed result.

Re-evaluation uses the run's pinned workflow and module versions. Adopting a
newer approved definition requires a separate, explicit migration decision.

### 7.4 complete_step

```text
complete_step(
  ctx,
  matter_id,
  run_id,
  step_run_id,
  note?,
  override_reason?
) -> StepRunRead
```

1. Re-check matter membership. Return 404 for a non-member.
2. Require an authorised lawyer. A clerk cannot complete or override a
   role-gated step.
3. Load the StepRun and its pinned StepDefinition.
4. Refuse completion when the state is `pending-applicability`,
   `not-applicable`, or `stale`.
5. When sequence is enforced, reject completion if an earlier applicable
   mandatory step is not complete.
6. Resolve every `requiredFactKey` to a current verified or corrected fact and
   every `requiredDocumentType` to a current processed document version.
7. If a mandatory prerequisite is missing, move the step to `blocked`.
8. Permit a blocked mandatory step to complete only when its prerequisites are
   now met or an authorised lawyer supplies a non-empty `override_reason`.
9. Persist the transition and audit event in one transaction.

Use `workflow.step-completed` for ordinary completion and
`workflow.step-overridden` for an override. The audit event records the actor,
target, before and after states, reason, and correlation ID.

## 8. Blocking and overrides

An applicable mandatory step stays blocked until the missing evidence exists.
The only path past that block without the evidence is a recorded, authorised
override:

```text
mandatory applicable step, evidence missing
        |
        +-> new evidence arrives -> prerequisites met -> complete
        |
        \-> lawyer records reason -> authorised override -> complete
```

An override is a legal decision by a named lawyer. It is role-gated, requires a
reason, and is audited separately from ordinary completion.

An override does not change an applicability condition and cannot convert an
unknown condition into false. Unresolved mandatory blockers,
pending-applicability steps, and stale mandatory steps prevent downstream
approval.

## 9. Events and invalidation

The service consumes at least:

```text
particular.corrected
document.version_superseded
matter.classification_changed
```

For each event, find StepRuns whose recorded dependencies contain the changed
fact, document, or classification version.

- An untouched step is re-evaluated and its applicability history is appended.
- A completed or overridden step is marked stale.
- A stale mandatory step blocks approval.
- No historical state or applicability record is deleted.

Publish:

```text
workflow.step-stale
workflow.applicability-changed
workflow.run-stale
```

Events are written through the same outbox transaction as the state change.

## 10. Invariants

| Invariant | Enforcement |
| --- | --- |
| Checklist is tailored deterministically | Compile approved base, transaction, registration-regime, and conditional definitions against the matter classification and verified facts |
| Unknown never means not applicable | Missing, unreviewed, conflict, blocked, stale, or unsupported inputs produce `pending-applicability` |
| Compilation is reproducible | WorkflowRun pins definition, module, classification, fact, and document versions plus evaluation reasons |
| Mandatory block requires evidence or override | Domain transition refuses completion without current prerequisites or a non-empty authorised override reason |
| Only a lawyer decides | Instantiate, re-evaluate, complete, and override methods enforce the lawyer role |
| Definition changes preserve history | Existing runs keep their pinned versions; newer approved definitions do not mutate them |
| Dependency changes preserve decisions | Affected completed steps become stale and retain their earlier state and applicability records |
| Every material transition is audited | Instantiate, applicability change, stale marking, completion, re-evaluation, and override write separate events |
| Matter isolation | Membership is re-checked and cross-matter access is denied |
| Content is governed elsewhere | Only approved definitions compile; authoring remains in `content-governance-service` |

## 11. Failure modes

- An applicability input is absent or not authoritative: return `unknown`.
- More than one approved base or required module matches: refuse compilation as
  a governance configuration error.
- No approved base, transaction, or registration-regime module matches: refuse
  compilation and identify the missing governed content.
- A required fact changes after completion: mark affected steps stale and keep
  their completion history.
- A required document version is superseded: mark dependent steps stale.
- Two actors complete the same step concurrently: reject the stale write using
  optimistic concurrency.
- A step is completed out of order: reject with a domain error.
- A definition is revised while a run is active: keep the pinned version.
- An AI suggestion conflicts with the compiled checklist: keep the suggestion
  as non-authoritative review information and do not mutate the run.
- A non-member requests a run: return 404.
- A member lacks the decision role: return a policy refusal.

## 12. Test list

### Unit

- Three-valued applicability for true, false, and unknown.
- Missing or unverified facts produce unknown.
- Deterministic module selection.
- Ambiguous module selection is rejected.
- Non-applicable, pending, and stale steps cannot complete.
- A mandatory blocked step cannot complete without evidence or override.
- An override requires a non-empty reason and an authorised lawyer.
- Out-of-order completion is rejected.

### Contract

- Instantiate, list, re-evaluate, and complete request and response schemas.
- Compiled provenance fields and applicability explanations.
- Frontend mapping for all StepState values.
- Stable fact-key and document-type requirements.

### Integration

- Compile a base plus RTA, transaction, and conditional modules.
- Verify every pinned definition and dependency version.
- Complete steps in order.
- Correct a relied-on fact and confirm affected steps become stale.
- Re-evaluate without losing earlier applicability or completion history.
- Override a blocked mandatory step and confirm the separate audit event.
- Approve only when no mandatory block, pending applicability, or stale step
  remains.

### Security

- Deny cross-matter reads and writes.
- Return 404 instead of disclosing a matter to a non-member.
- Refuse clerk instantiation, re-evaluation, completion, and override.
- Audit every mutation without copying raw client values into logs.

## 13. Decisions to confirm before coding

1. Use separate WorkflowDefinition and WorkflowModule entities. Compile
   approved base, transaction, registration-regime, and conditional content
   into a WorkflowRun.
2. Store WorkflowRun and StepRun separately. WorkflowRun holds compilation
   provenance; StepRun holds applicability and completion state.
3. Keep workflow/run/step routes as the V0 API and treat "Tasks" as the
   internal resource name.
4. Defer a standalone Decision entity for V0. StepRun completion plus its audit
   event records the decision.
5. Define a lawyer-authorised migration command for moving an active run to a
   newer approved definition. Re-evaluation alone never changes pinned
   versions.
6. Add `pending-applicability`, `not-applicable`, and `stale` to the frontend
   contract. Render every state with text and an icon, not colour alone.
7. Start V0 with the lawyer-approved RTA workflow required for the evaluated
   transaction. Add transaction modules only after scope approval and legal
   review.
