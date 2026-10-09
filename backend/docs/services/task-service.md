# task-service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`content-governance-service.md`, `document-service.md`,
`verification-service.md`, and `memory-service.md`.

This service maps to Phase 5 of the backend plan, the Tasks API, and the
invariant that a mandatory blocked step requires new evidence or a recorded
authorised override.

V0 is RTA-first. Its first governed checklist is compiled from approved core,
transaction, registration-regime, conditional, and firm-policy modules.
Deed-registration and other regimes use the same mechanism only after their
content has been reviewed and approved.

The canonical workflow has ten phases:

```text
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

The frontend may group these phases into the four familiar work areas
Examination, Drafting, Execution, and Attestation. Those groups are a
presentation choice and do not replace the canonical phase recorded by the
backend.

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
- matter-specific document requirements and their lawyer-review state;
- matter-specific responses to governed question and checklist sets;
- explainable readiness evaluations for drafting, execution, registration,
  and closure;
- the operational phase and blocking projections exposed to `matter_service`;
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
GET  /matters/{id}/document-requirements
POST /matters/{id}/document-requirements/{requirementId}/review
GET  /matters/{id}/readiness
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
StepRunPort             DocumentReadPort RequirementPort
ReadinessPort           EventPort / AuditPort
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

The approved base for the complete notarial matter:

```text
WorkflowDefinition
  id
  titleKey
  kind = base
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
  kind = core | transaction | registration-regime | conditional | firm-policy
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
base notarial workflow
  + client-intake-and-CDD core module
  + document-intake core module
  + title-examination core module
  + transfer transaction module
  + RTA registration-regime module
  + power-of-attorney conditional module, when applicable
  + approved firm-policy module
```

V0 must not maintain a separate permanent template for every possible
combination of facts. A small set of reviewed modules is safer to version and
maintain.

### 3.3 StepDefinition

```text
StepDefinition
  id
  definitionId
  phase
  displayOrder
  titleKey
  descriptionKey
  objectiveKey
  assignedRole
  mandatory
  applicability?
  requiredFactKeys: string[]
  requiredDocumentTypes: string[]
  requiredCheckResults: CheckRequirement[]
  authorityReferences: AuthorityReference[]
  completionPolicy
  overridePolicy
  deadlineRuleId?
  deadlineRuleVersion?
  rules: StepRule[]
```

Definitions use stable fact keys and document types. They never contain
matter-specific database IDs.

`deadlineRuleId` references a separately approved deadline rule. A step never
embeds an ungoverned date formula. `StepRule` remains descriptive guidance:

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
  status = active | stale | superseded | closed
  supersededByRunId?
  supersededReason?
  version
```

`moduleVersions` records every core, transaction, registration-regime,
conditional, and firm-policy module used during compilation.

### 4.2 StepRun

```text
StepRun
  id
  workflowRunId
  stepDefinitionId
  definitionVersion
  sourceType?
  sourceId?
  sourceVersion?
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

### 4.3 DocumentRequirement

A document requirement is workflow state, not document-processing state:

```text
DocumentRequirement
  id
  matterId
  workflowRunId
  requirementKey
  documentType
  titleKey
  mandatory
  applicability
  applicabilityReason
  state
  acceptedDocumentId?
  acceptedDocumentVersionId?
  reviewedBy?
  reviewedAt?
  rejectionReason?
  version

DocumentRequirementState =
  missing |
  requested |
  present |
  reviewed |
  accepted |
  rejected |
  not-applicable
```

`document_service` owns upload and processing states such as `uploaded`,
`queued`, `processing`, `processed`, and `failed`. A processed document may
make a requirement `present`; it never makes it `accepted`. Acceptance is a
recorded lawyer decision against one immutable document version.

### 4.4 QuestionResponse

Question and checklist **sets** are governed content
(`content-governance-service.md` §4.4). A matter's **answers** to them are step
state, and they live here — no other service claimed them, which left the CDD
and beneficial-owner "mandatory gates" with nothing to gate on.

```text
QuestionResponse
  id
  matterId
  workflowRunId
  stepRunId
  questionSetId
  questionSetVersion
  questionId
  answerValue
  answerKind = boolean | choice | text | date | number | party-ref | document-ref
  evidenceRefs
  answeredBy
  answeredAt
  supersedesResponseId?
  state = draft | submitted | superseded
  version
```

Rules:

- Responses are append-only. A changed answer creates a successor and marks the
  predecessor `superseded`; the history is what shows a lawyer changed their
  mind and when.
- The set version is pinned, so a later governed revision of the question set
  does not silently re-interpret an existing answer.
- A step whose `completionPolicy` requires a question set cannot complete until
  every applicable mandatory question has a `submitted` response. That is the
  gate `content-governance-service.md` §4.4 describes.
- Free-text answers are matter content: they never enter an event payload, an
  audit `before`/`after`, or a notification (`events.md` §2).

### 4.5 ReadinessEvaluation

Readiness is a derived, explainable evaluation rather than an editable flag:

```text
ReadinessEvaluation
  id
  matterId
  workflowRunId
  stage = draft | execute | register | close
  ready
  blockerReferences
  evaluatedStepRunVersions
  evaluatedRequirementVersions
  evaluatedFactVersions
  evaluatedCheckVersions
  workflowRunVersion
  evaluatedAt
```

Each blocker reference identifies the exact unresolved step, requirement,
fact, check, or stale dependency. The latest evaluation supplies the summary
projection shown on a matter, but the full evaluation remains task-owned.

The default readiness policies are:

```text
ready-to-draft =
  required facts verified
  AND required documents accepted
  AND title-examination steps complete
  AND no unresolved blocking checks

ready-to-execute =
  ready-to-draft
  AND final draft approved
  AND pre-execution steps complete

ready-to-register =
  execution and attestation steps complete
  AND required execution evidence accepted

ready-to-close =
  registration outcome recorded
  AND final documents accounted for
  AND no unresolved mandatory task or active obligation
```

These policies must be versioned as approved definitions. The displayed
boolean is never accepted as a command from a browser.

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
- `DocumentRequirementRepository`: persists compiled requirements, accepted
  evidence bindings, review decisions, and optimistic versions.
- `ReadinessRepository`: stores immutable readiness evaluations and returns the
  latest projection for each stage.
- `VerifiedFactReadPort`: reads verified or corrected facts, their versions,
  and their verification states.
- `DocumentReadPort`: returns current immutable document versions and their
  processing states; it does not decide whether evidence is accepted.
- `CheckReadPort`: returns current check results and blocker provenance.
- `ObligationReadPort`: returns active obligations when evaluating closure.
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
3. Resolve exactly one approved base definition and all required approved core,
   transaction, registration-regime, and firm-policy modules effective at
   compilation time.
4. Read current verified or corrected facts and processed document versions.
5. Evaluate approved conditional modules and step conditions with three-valued
   logic.
6. Create a WorkflowRun that pins the base version, every selected module
   version, matter classification version, and compilation time.
7. Create a StepRun for every candidate step. Store its applicability result,
   reason, and the fact and document versions used.
8. Compile document requirements and preserve not-applicable requirements for
   audit.
9. Calculate the initial phase, blocking summary, and readiness evaluations.
10. Persist the run, steps, requirements, projections, the
    `workflow.instantiated` audit row, **and** the `workflow.instantiated`
    outbox event in one transaction. On failure, persist the failure state and
    publish `workflow.setup-failed` so the matter projection shows `failed`
    rather than staying `pending` forever.

Ambiguous or missing governed content is a configuration error. The compiler
must not choose a matching definition by list order.

Compilation is idempotent for the same matter classification version and
request key. It is also deterministic. The same approved definitions, matter
classification, fact versions, and document versions produce the same StepRun
set. AI suggestions are not compilation inputs.

`matter.created` triggers this operation through the outbox. An inquiry gets
the approved intake and classification modules first; activation adds the
remaining modules once acceptance and classification gates pass.

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
Re-evaluation is only valid while transaction type and registration regime are
unchanged. A material reclassification supersedes the run instead.

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

### 7.5 review_document_requirement

```text
review_document_requirement(
  ctx,
  matter_id,
  requirement_id,
  document_id,
  document_version_id,
  decision,
  reason?
) -> DocumentRequirementRead
```

1. Require matter membership and an authorised lawyer.
2. Confirm the immutable document version belongs to the same matter and is
   current enough to review.
3. Permit `accepted` only after the required evidence review completes.
4. Bind acceptance to the exact document version.
5. Require a reason for rejection.
6. Recalculate affected step prerequisites and readiness.
7. Persist the decision, projection changes, audit event, and outbox events in
   one transaction.

### 7.6 evaluate_readiness

```text
evaluate_readiness(ctx, matter_id, run_id) -> list[ReadinessEvaluationRead]
```

Evaluate every approved readiness policy against current step, requirement,
fact, check, workflow, and obligation versions. Store a new immutable
evaluation when its inputs or result differ. Return blocker references rather
than a bare boolean.

The current operational phase is derived from the earliest applicable
mandatory phase with incomplete work. Approved definitions may allow explicit
parallel work, but a client cannot assign `currentPhase` directly.

### 7.7 supersede_for_reclassification

```text
supersede_for_reclassification(
  ctx,
  matter_id,
  old_run_id,
  classification_version,
  reason
) -> WorkflowRunRead
```

Use this method when transaction type or registration regime changes:

1. Require an authorised lawyer and a recorded reclassification reason.
2. Mark the old run `superseded`; never delete it.
3. Compile a new run from approved definitions for the new classification.
4. Re-evaluate existing evidence against the new requirements.
5. Do not copy earlier completions or accepted requirements automatically.
   Present possible mappings for lawyer confirmation.
6. Link both runs and persist `workflow.run-superseded` plus audit events.

Changes to conditional characteristics, such as power-of-attorney use, keep
the same pinned run and use ordinary dependency re-evaluation.

### 7.8 create_finding_remediation

```text
create_finding_remediation(
  ctx,
  matter_id,
  check_id,
  check_evaluation_version,
  remediation_policy
) -> StepRunRead
```

Create or return the governed remediation StepRun for the idempotency tuple
`(check_id, check_evaluation_version, required_action_key)`. The StepRun owns
the responsible role, required evidence, progress, and any authorised
override. It retains the source check reference. Completion never rewrites the
finding; check-service re-evaluates it against new verified evidence.

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

Every name below is registered in `events.md`; this service must not invent one.
It consumes at least:

```text
matter.created
matter.classification-changed
matter.activated
particular.verified
particular.corrected
particular.added
particular.blocked
particular.evidence-stale
document.processing-completed
document.version-superseded
check.result-changed
finding.remediation-requested
finding.resolved
finding.waived
obligation.status-changed
instrument.attested
instrument.registration-acknowledged
content.definition-approved
content.definition-retired
```

For each event, find StepRuns whose recorded dependencies contain the changed
fact, document, or classification version.

- An untouched step is re-evaluated and its applicability history is appended.
- A completed or overridden step is marked stale.
- A requirement accepted against a superseded document version is marked
  `present` and requires a new lawyer review.
- A stale mandatory step blocks approval.
- No historical state or applicability record is deleted.

Publish:

```text
workflow.instantiated
workflow.setup-failed
workflow.step-completed
workflow.step-overridden
workflow.step-stale
workflow.applicability-changed
workflow.run-stale
workflow.run-superseded
workflow.phase-changed
workflow.requirement-changed
workflow.readiness-changed
workflow.blocking-changed
workflow.review-requested
workflow.signing-scheduled
```

Events are written through the same outbox transaction as the state change
(`jobs-and-workers.md` §2).

`workflow.instantiated`, `workflow.setup-failed`, and
`workflow.blocking-changed` were previously written only as audit rows while
`matter_service` consumed them as domain events, so its projection never
updated. Both are now required: the audit row is the record, the outbox event is
the notification. An audit write is not a publication (`events.md` §3).

`workflow.review-requested` and `workflow.signing-scheduled` are new. They are
the publishers `obligations_service` was waiting for under the unregistered
names `task.review-requested` and `matter.signing-scheduled`.

## 10. Invariants

| Invariant | Enforcement |
| --- | --- |
| Checklist is tailored deterministically | Compile approved base, transaction, registration-regime, and conditional definitions against the matter classification and verified facts |
| Unknown never means not applicable | Missing, unreviewed, conflict, blocked, stale, or unsupported inputs produce `pending-applicability` |
| Compilation is reproducible | WorkflowRun pins definition, module, classification, fact, and document versions plus evaluation reasons |
| Processing is not acceptance | Only an authorised requirement review binds accepted evidence to a document version |
| Readiness is derived and explainable | Versioned policies evaluate current dependencies and return exact blocker references |
| Mandatory block requires evidence or override | Domain transition refuses completion without current prerequisites or a non-empty authorised override reason |
| Only a lawyer decides | Instantiate, re-evaluate, complete, and override methods enforce the lawyer role |
| Definition changes preserve history | Existing runs keep their pinned versions; newer approved definitions do not mutate them |
| Material reclassification preserves history | Transaction or regime changes supersede and link the old run; conditional changes re-evaluate the pinned run |
| Dependency changes preserve decisions | Affected completed steps become stale and retain their earlier state and applicability records |
| Every material transition is audited | Instantiate, applicability change, stale marking, completion, re-evaluation, and override write separate events |
| Organisation isolation | Every query filters `ctx.organisationId` before matter membership; a cross-organisation resource is a 404 (`security-model.md` §2) |
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
- A processed document is present but not reviewed: keep its requirement
  `present` and readiness blocked.
- Transaction type or registration regime changes: refuse ordinary
  re-evaluation and require run supersession.
- A client attempts to write a readiness flag or current phase: reject it;
  both are derived projections.
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
- Processed evidence does not become accepted without lawyer review.
- Readiness reports exact blocker references and all dependency versions.
- Current phase is derived from applicable incomplete mandatory work.
- Conditional reclassification re-evaluates the pinned run.
- Transaction or regime reclassification supersedes and links the old run.

### Contract

- Instantiate, list, re-evaluate, complete, requirement review, and readiness
  request and response schemas.
- Compiled provenance fields and applicability explanations.
- Frontend mapping for all StepState values.
- Stable fact-key and document-type requirements.

### Integration

- Compile a base plus RTA, transaction, and conditional modules.
- Compile intake and classification for an inquiry, then add active-matter
  modules after activation.
- Verify every pinned definition and dependency version.
- Process a document, confirm its requirement is only `present`, then accept it
  through a lawyer review.
- Complete steps in order.
- Correct a relied-on fact and confirm affected steps become stale.
- Re-evaluate without losing earlier applicability or completion history.
- Reclassify the registration regime and confirm the old run is superseded,
  the new run is linked, and evidence is not silently accepted.
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
   approved core, transaction, registration-regime, conditional, and
   firm-policy content into a WorkflowRun.
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
8. Use the ten canonical phases in the backend. Treat Examination, Drafting,
   Execution, and Attestation as frontend presentation groups only.
9. Keep document requirements and readiness evaluations in `task_service`.
   Keep upload and processing state in `document_service`.
10. Start with approved modules for client intake and CDD, document intake,
    title examination, draft review, execution, registration, and closure;
    transfer and gift; RTA and any legally reviewed deed regime; and approved
    conditional modules such as power of attorney, corporate party, minor
    party, reserved life interest, mortgage or encumbrance, divided or
    undivided share, subdivision, and missing original evidence.

### Lawyer-led requirements and manual review (2026-10-09)

The current runtime uses governed checklist requirements, not new StepRun or
WorkflowDefinition content. Checks projects the existing human original-inspection
and requirement-decision commands. Empty accepted-class lists do not establish
administrative completion eligibility. Receipt and manual inspection never write
SATISFIED directly or bypass existing evidence, currency, consistency or waiver policy.

Requirement links now require item If-Match plus documentVersion and
interpretationGeneration. The document owner validates user/matter, exact current
pages and immutable source hash/storage version; the verification owner validates
every supplied evidence ID. Linking records receipt and resets item evidence review.
Legacy links without exact pins remain readable history and cannot establish a live
supporting link. Current reads withhold stale link-derived authority too.

Original inspections retain actor, time, method, optional note/location, and the
exact immutable original source pins. A new or replacement original requires new
inspection; a renewed interpretation of the same immutable original may retain its
physical inspection. All inspections remain in inspectionHistory. No machine or
administrative action can record the human-only inspection. Legal review actions
retain their existing capability checks and policies, including non-document
requirements with optional historical attachments.

All three POST commands (decisions, original-inspection, links) require a stable
Idempotency-Key and item If-Match. Current matter/capability/resource authorization
and the shared matter mutation lock precede replay. Same logical payload and
precondition replay the original response/ETag; changed requests conflict. Replay
is historical, so clients reload current eligibility after recovery. The browser
stores only opaque actor/matter/operation retry metadata for 24 hours; explicit
renewal discards that operation's obsolete pin after refreshing current state.

GET /api/v1/matters/{id}/readiness is an operational dependency projection, not
legal approval. It returns state, nextAction, evaluatedAt, requirement counts and
versioned blocker references. Document, verification and check owners contribute
current dependency state; missing/unavailable dependencies are unknown. Reads are
bounded (document/check pages: 10 x 100; canonical facts: 4 x 25); incomplete or
repeated pagination cannot clear work. Fresh scoped checks alone cannot prove
whole-matter coverage because no approved per-scope required-run definition exists.
Such coverage stays unknown/check-review. Counts and next actions must not be
replaced with client-side empty/null-as-zero heuristics.

Known pending document/fact work remains the next action when a checklist is absent
or unavailable; overall state stays unknown and requirement counts stay null.
Unknown-only dependencies show recovery rather than an invented completion.

Migration task0002 is additive after document0004: link document/generation/source
pins and item original-inspection source/history JSON. Existing rows are not
inventively backfilled. Legacy inspection metadata remains retained but an unbound
inspection is projected as unknown. Downgrade refuses any pinned link or recorded
inspection history. Older code is not a supported writer after these new records.
