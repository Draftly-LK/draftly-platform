# content-governance-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `library-service.md`,
and the task-service design. This service is the **maintainer's tier**: it
governs the controlled legal *content* that per-matter work consumes across
five families: legal document/form templates, workflow definitions and
modules, question/checklist sets, deadline-rule templates, and internal reports
or supporting documents. It owns the guarantee that approved wording changes
only through a new approved version.

Maps to plan **Phase 5** ("versioned rule definitions with authority metadata,
version, effective date"), the maintainer role, invariant **§5.3.6**, the
trust-boundary row *Legal corpus* (§5.2), and the *content governance* audit
event (§5.2). Frontend reads (`GET /api/templates`, `/api/questions`,
`/api/question-sets`) exist as mock accessors; the write path does not.

## 1. What it owns

The lifecycle of **controlled, versioned content definitions**:
`FormTemplate`, `SupportingDocumentTemplate`, `WorkflowDefinition`,
`WorkflowModule`, `DeadlineRule`, and `QuestionSet`s / `Question`s. Each
carries an `approvalState` and moves `draft → approved → retired` only under a
maintainer's hand. It owns the create/version/approve/retire write path and the
read path that hands `approved` definitions to per-matter services.

It does **not** run a workflow (task-service runs an instance of approved
definitions), calculate an obligation occurrence (obligations-service does),
bind facts into a draft (draft-service does), or author legal wording. Legal
wording and legal rule content stay lawyer-owned. This service governs the
definition lifecycle; specialist services execute approved definitions.

## 2. Where it sits

```text
GET  /api/templates       ─┐
GET  /api/questions       ─┤
GET  /api/question-sets   ─┼→ api/v1/... ─→ application/content_governance_service.py
POST (create/version/       │                          │ orchestrates
      approve/retire) ──────┘                          ▼
   maintainer-role-gated          ports: ContentRepository, AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` (actor, roles) and enforces the maintainer gate itself — it
does not trust a client-supplied role. It imports no SQLAlchemy and no FastAPI;
it orchestrates the domain state machine plus ports.

## 3. Domain models it needs

In `domain/content.py`, mirroring the frontend contract exactly:

- **FormTemplate** (from `frontend/src/types/draft.ts`) — `{ id, formNumber,
  nameKey, regime, transactionType, approvalState, fields: FormTemplateField[],
  blocks: FormTemplateBlock[] }`.
  - **FormTemplateField** — `{ id, labelKey, order, required, factBinding? }`.
  - **FormTemplateBlock** — `{ id, order, kind, placeholderText }` where `kind`
    is `locked-prescribed` or `editable`. A `locked-prescribed` block is the
    wording invariant §5.3.6 protects.
- **SupportingDocumentTemplate** — a governed Draftly-created output definition
  for reports, schedules, checklists, packs, letters, and administration
  documents: `{ id, category, titleKey, approvalState, language, ownerId,
  version, effectiveFrom?, effectiveTo?, sections, dataBindings,
  authorityReferences }`. It may contain lawyer-approved professional wording,
  but it must not be represented as a prescribed government form.
- **WorkflowDefinition** — the versioned base for a complete notarial matter:
  `{ id, titleKey, kind: "base", approvalState, language, ownerId, version,
  effectiveFrom?, effectiveTo?, steps: StepDefinition[] }`.
- **WorkflowModule** — a reusable governed group of steps:
  `{ id, titleKey, kind, registrationRegimes, transactionTypes,
  applicability?, approvalState, language, ownerId, version, effectiveFrom?,
  effectiveTo?, steps: StepDefinition[] }`, where `kind` is `core |
  transaction | registration-regime | conditional | firm-policy`.
- **StepDefinition** — `{ id, definitionId, phase, displayOrder, titleKey,
  descriptionKey, objectiveKey, assignedRole, mandatory, applicability?,
  requiredFactKeys, requiredDocumentTypes, requiredCheckResults,
  authorityReferences, completionPolicy, overridePolicy, deadlineRuleId?,
  deadlineRuleVersion?, rules }`.
- **DeadlineRule** — a versioned rule definition with scope, trigger schema,
  applicability, calculation policy, timezone/calendar references, authority
  references, effective dates, confirmation policy, approval state, owner, and
  version. `obligations_service` executes it and owns generated obligations.
- **Question** (from `frontend/src/types/question.ts`) — `{ id, prompt, scope,
  language, frequentlyWrong }` where `scope` is `matter | step | standalone`.
- **QuestionSet** — `{ id, titleKey, descriptionKey, questionIds, approvalState,
  ownerId }`.

Enums and shared values (exact):

| Field | Values |
| --- | --- |
| `FormTemplate.approvalState` / `Workflow.approvalState` / `QuestionSet.approvalState` | `draft`, `approved`, `retired` |
| `FormTemplateBlock.kind` | `locked-prescribed`, `editable` |
| `SupportingDocumentTemplate.category` | `report`, `drafting-support`, `completion-output`, `notarial-record`, `notarial-administration`, `registry-application` |
| `Question.scope` | `matter`, `step`, `standalone` |
| `WorkflowPhase` | `intake`, `classification`, `document-collection`, `title-examination`, `issue-resolution`, `drafting`, `pre-execution`, `execution`, `registration`, `closure` |
| `WorkflowModule.kind` | `core`, `transaction`, `registration-regime`, `conditional`, `firm-policy` |
| `Role` (from `user.ts`) | `reviewer`, `approver`, `maintainer`, `administrator` |

The `approvalState` state machine, enforced in the domain layer so the first
tests hit it without a database:

```text
draft ──approve──▶ approved ──retire──▶ retired
  │                                        ▲
  └──────────────── retire ────────────────┘
approved  ──(edit)──▶  NEW draft version (never mutate the approved one)
```

An illegal transition — or an edit to an `approved` definition in place — raises
a domain error, not an HTTP error.

The current frontend's four `Workflow.function` values are presentation groups
only. An API adapter may group the ten canonical phases as Examination,
Drafting, Execution, and Attestation, but governed definitions and matter runs
retain the canonical phase.

## 4. Controlled-content catalogue

This catalogue is the intended content surface, not a claim that every entry is
already drafted, legally approved, or available in V0. Delivery phase and
content readiness are separate:

| Axis | Values | Meaning |
| --- | --- | --- |
| `deliveryPhase` | `mvp`, `v1`, `later` | When the definition and its product flow are implemented |
| `contentReadiness` | `structure-only`, `legal-content-blocked`, `lawyer-reviewed` | Whether governed content is usable; `legal-content-blocked` requires an authorized lawyer to supply or approve the content |

An MVP entry may still be `legal-content-blocked`. Inventory membership never
means legal approval. Only an exact version in
`approvalState = approved`, with required authority and effective-date metadata,
may feed a matter.

### 4.1 Legal document and form templates

#### RTA statutory instruments

The Registration of Title Act instrument catalogue is versioned against Gazette
Extraordinary No. 2308/27 and its effective date. The governed identifiers are:

```text
rta-amalgamation-subdivision-form-7
rta-transfer-sale-form-8
rta-gift-form-9
rta-lease-form-10
rta-mortgage-form-11
rta-mortgage-cancellation-form-12
rta-caveat-form-13
rta-condominium-registration-form-21
rta-agreement-of-sale-form-23
rta-security-bond-transfer-form-24
rta-certificate-of-sale-registration-form-25
rta-agreement-of-sale-cancellation-form-26
rta-gift-cancellation-form-27
rta-life-interest-cancellation-form-28
rta-lease-cancellation-form-29
rta-caveat-cancellation-form-30
rta-address-registration-form-31
rta-land-exchange-form-32
rta-life-interest-death-cancellation-form-33
rta-certificate-of-sale-cancellation-form-34
rta-servitude-access-transfer-form-35
rta-life-interest-holder-lease-form-36
```

Forms 8 through 12 are `v1`; the remaining RTA forms are `later`. Form 8 may be
used by the M2 static demonstration only with the explicit
`PLACEHOLDER — legal wording pending lawyer` content required by the plan. All
22 entries remain `legal-content-blocked` until the prescribed source text,
Gazette version, effective date, and lawyer approval are recorded. Draftly
never reconstructs the statutory wording from a summary.

#### Deed-registration instruments

The ordinary deed-registration regime uses separately governed,
lawyer-authored templates:

```text
deed-transfer-sale
deed-gift
deed-lease
deed-mortgage-bond
deed-agreement-to-sell
deed-exchange
deed-agreement-to-sell-cancellation
deed-gift-revocation
deed-mortgage-release-cancellation
deed-lease-surrender-cancellation
deed-life-interest-cancellation
deed-servitude-right-of-way-release
deed-address-declaration
deed-section-47-declaration
deed-priority-notice
deed-servitude-right-of-way
deed-subdivision-amalgamation
deed-condominium-transfer
deed-certificate-of-sale
```

`deed-transfer-sale` and `deed-gift` are `mvp`; Lease, Mortgage, Agreement to
Sell, mortgage cancellation, lease cancellation, and servitude/right-of-way
families are `v1`; the rest are `later`. Every entry is
`legal-content-blocked`. An experienced conveyancing lawyer must supply and
approve its legal wording before activation.

#### Power-of-attorney package

```text
poa-general
poa-special-sale
poa-special-gift
poa-special-mortgage
poa-special-lease
poa-revocation
poa-attorney-validity-affidavit
poa-notary-verification-statement
poa-document-retention-checklist
```

The Power-of-Attorney conditional workflow module is `mvp`; the document
templates are `v1`. The document templates are `legal-content-blocked`, and
the workflow must require identity, land-description, registration,
revocation/cancellation, and validity review using approved rules.

#### Notarial attestation and record templates

Form E is represented as one governed conditional definition, not copied into
multiple diverging templates:

```text
notarial-form-e-attestation
  conditions:
  - standard
  - instrument read
  - instrument read and explained
  - attorney execution
  - illiterate executant
  - finger or toe impression
  - corporate executant
  - multiple notaries
```

Its blocks compose only lawyer-approved variants. The service must reject any
combination that has no approved clause for the selected circumstances.

Form F and related operational records are governed separately:

```text
notarial-form-f-register
notarial-form-f-monthly-return
notarial-nil-monthly-return
notarial-out-of-district-list
notarial-local-authority-certified-list
notarial-incomplete-multiparty-execution-list
notarial-protocol-original
notarial-protocol-duplicate
notarial-protocol-copy
notarial-certified-copy
notarial-protocol-cover-sheet
notarial-document-index
```

Form E, Form F, and the nil-return template are `mvp`. The remaining record
variants are `v1` or `later`. Statutory wording and prescribed layouts remain
`legal-content-blocked`.

### 4.2 Internal reports and supporting documents

These are Draftly-created professional outputs. They are versioned and
lawyer-reviewed, but they must be labelled as Draftly outputs rather than
official forms.

#### Title examination reports

```text
report-title
report-title-preliminary
report-title-final
report-chain-of-title
report-root-of-title-analysis
report-land-registry-search-summary
report-encumbrance
report-servitude-right-of-way
```

`report-title` and `report-chain-of-title` are `mvp`; the others are `v1`.

#### Verification and exception reports

```text
report-verified-particulars
report-cross-document-comparison
report-extent-boundary-comparison
report-name-identity-discrepancy
report-missing-document
report-title-defect
report-red-flag
report-unresolved-issues
report-lawyer-override
```

`report-verified-particulars` and the document-request checklist are `mvp`.
The other reports are `v1`. Reports must preserve provenance and must clearly
separate extracted facts, verified facts, deterministic findings, and lawyer
conclusions.

#### Drafting support and completion outputs

```text
support-matter-fact-sheet
support-drafting-instruction-sheet
support-party-particulars-schedule
support-property-schedule
support-consideration-payment-schedule
support-life-interest-schedule
support-servitude-schedule
support-execution-particulars-sheet
support-document-request-checklist
support-pre-execution-checklist
completion-execution-pack
completion-registration-pack
completion-client-report
completion-registered-document-delivery-letter
completion-matter-closure-report
completion-evidence-manifest
completion-export-manifest
```

The Matter Fact Sheet, Property Schedule, Execution Pack, Registration Pack,
Evidence Manifest, and Export Manifest are `mvp`; the remainder are `v1`.
Where an output contains professional advice or legal conclusions, its wording
and sign-off policy remain lawyer-owned.

#### Notary administration and registry applications

```text
admin-annual-practice-certificate-application
admin-annual-duplicate-forwarding-affidavit
admin-office-change-notice
admin-discontinuance-notice
admin-registrar-of-lands-notice
admin-high-court-judge-notice
admin-government-agent-notice
admin-registrar-general-explanation
admin-language-authorisation-application
admin-notarial-warrant-record
registry-land-search-request
registry-extract-inspection-request
registry-certified-deed-copy-request
registry-certified-extract-copy-request
registry-title-register-extract-application-ti-re-30
registry-new-title-certificate-application-ti-re-31
registry-title-instrument-copy-request
registry-representative-authorisation-letter
registry-registration-submission-cover
registry-registration-acknowledgement
registry-registration-defect-response
```

These are `later` unless a specific MVP workflow requires a submission cover or
acknowledgement record. Prescribed applications, affidavits, notices, and
government forms are `legal-content-blocked`.

### 4.3 Workflow definitions and modules

The `base-conveyancing` workflow uses the ten canonical phases:

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

The governed workflow-module catalogue is:

| Kind | Modules |
| --- | --- |
| Transaction | Transfer/Sale, Gift, Lease, Mortgage, Agreement to Sell, Exchange, Servitude/Right of Way, Subdivision/Amalgamation, Condominium, Cancellation/Discharge, Power of Attorney |
| Registration regime | Deed registration, RTA/title registration, condominium registration, special-area registration |
| Conditional | Power of attorney used, minor party, corporate party, foreign/overseas execution, reserved life interest, mortgage/encumbrance, servitude/right of way, undivided share, multiple parcels, multiple registration districts, outside practising jurisdiction, missing original deed, unregistered prior instrument, identity mismatch, extent/boundary discrepancy |
| Firm policy | Second-lawyer review, high-value review, enhanced client verification, partner approval, original-document custody, client-funds handling |

For MVP, approve only the base workflow, Deed Transfer, Deed Gift,
deed-registration regime, Power of Attorney, Reserved Life Interest,
Registration, and Closure modules. The task service compiles the applicable
approved versions. Reclassification supersedes a run and recompiles modules; it
never silently rewrites an active run.

### 4.4 Question and checklist sets

```text
questions-client-intake
questions-conflict-check
questions-matter-classification
questions-cdd-beneficial-owner
questions-client-risk-profile
questions-transfer
questions-gift
questions-lease
questions-mortgage
questions-power-of-attorney
questions-corporate-party
questions-minor-party
questions-title-examination
questions-survey-plan
questions-encumbrance
questions-servitude
questions-draft-review
questions-pre-execution
questions-execution-attestation
questions-registration
questions-matter-closure
```

Client Intake/CDD, Transfer, Gift, Document Request, Pre-Execution,
Registration, and Closure sets are `mvp`. CDD, beneficial-owner, risk-profile,
and applicable enhanced-due-diligence questions are mandatory gates for
captured transactions; they are not optional generic intake prompts. Question
sets store structured prompts, applicability, evidence requirements, answer
types, and completion policy. They do not contain AI-authored legal answers.

### 4.5 Deadline-rule templates

```text
deadline-annual-notarial-certificate
deadline-monthly-form-f-return
deadline-monthly-nil-return
deadline-local-deed-registration-30-days
deadline-out-of-jurisdiction-registration-60-days
deadline-office-change-discontinuance-notice
deadline-power-of-attorney-validity-review
deadline-mandatory-lawyer-review
deadline-client-document-follow-up
```

The annual certificate, monthly return, nil return, and 30/60-day registration
rules are `mvp`. Each legal rule is `legal-content-blocked` until authority,
trigger semantics, calendar/timezone behavior, effective date, and lawyer
confirmation requirements are approved. Firm-configured review and follow-up
rules must be labelled internal targets rather than statutory deadlines.

### 4.6 Ownership exclusions

This service does not become a generic template bucket:

| Content | Owner |
| --- | --- |
| Email, SMS, WhatsApp, and in-app notification templates | `notification_service` |
| Authentication codes, magic links, account verification, recovery, and MFA messages | Configured identity provider |
| Matter-specific generated drafts and versions | `draft_service` |
| Generated obligation occurrences and reminder state | `obligations_service` |
| Matter-specific workflow and step runs | `task_service` |
| Corpus source text and research indexing policy | `corpus_governance` and `research_service` |

React Email components remain entirely inside `notification_service`, even
when a notification refers to a governed deadline rule. Authentication tokens
and authentication email templates never pass through ordinary application
notification or content-governance flows.

### 4.7 Repository layout

The controlled-content source tree should preserve the five families:

```text
controlled-content/
├── form-templates/
│   ├── statutory-rta/
│   ├── deed-registration/
│   ├── power-of-attorney/
│   └── notarial-records/
├── supporting-documents/
│   ├── reports/
│   ├── drafting-support/
│   ├── completion-outputs/
│   ├── notarial-administration/
│   └── registry-applications/
├── workflows/
│   ├── base/
│   ├── transactions/
│   ├── regimes/
│   ├── conditional/
│   └── firm-policies/
├── question-sets/
└── deadline-rules/
```

This is a logical backend layout, not permission to copy source material into
the repository. Every prescribed source must retain its provenance, checksum,
authority reference, retrieval date, effective date, and rights classification.

## 5. Ports it depends on

In `ports/`:

- `ContentRepository` — persist and load `FormTemplate`,
  `SupportingDocumentTemplate`, `WorkflowDefinition`, `WorkflowModule`,
  `DeadlineRule`, and `QuestionSet`/`Question` definitions with their versions; list by
  `approvalState`; fetch the applicable `approved` version for a per-matter
  consumer.
- `AuditPort` — `record(event)`; every governance transition writes a *content
  governance* audit event (§5.2).

No object storage, no retrieval, no processing. Governance is metadata and
versioning; it touches neither matter storage nor the legal corpus index.

## 6. The methods

### Read (maintainer console and per-matter consumers)

- **list_templates(ctx, filter) -> FormTemplateRead[]** — `GET /api/templates`.
- **list_supporting_document_templates(ctx, filter) ->
  SupportingDocumentTemplateRead[]**.
- **list_questions(ctx, filter) -> QuestionRead[]** — `GET /api/questions`.
- **list_question_sets(ctx, filter) -> QuestionSetRead[]** — `GET
  /api/question-sets`.
- **list_workflow_definitions(ctx, filter) -> WorkflowDefinitionRead[]**.
- **list_workflow_modules(ctx, filter) -> WorkflowModuleRead[]**.
- **list_deadline_rules(ctx, filter) -> DeadlineRuleRead[]**.

Per-matter services request `approved` definitions only; a `draft` or `retired`
definition is never handed to matter work (§7). These three reads are wired in
the frontend today as mock accessors (`getTemplates`, `getQuestions`,
`getQuestionSets`).

### Write (maintainer-role-gated) — the missing path

- **create_content(ctx, kind, definition) -> ContentRead** — creates a new
  definition in `approvalState = draft`. Maintainer only.
- **version_content(ctx, kind, id, changes) -> ContentRead** — creates a **new
  draft version** from an existing definition. Editing an `approved` definition
  routes here; the approved version is never mutated (§5.3.6).
- **approve_content(ctx, kind, id) -> ContentRead** — moves `draft → approved`.
  Maintainer only. Records version, effective date, and authority metadata
  (Phase 5). For a `FormTemplate`, approval locks the `locked-prescribed`
  blocks: from here they change only through a further new approved version.
  For workflow content, approval validates stable fact, document, and check
  keys; typed applicability; authority references; canonical phases; role and
  override policies; and referenced deadline-rule versions. For a deadline
  rule, approval validates its trigger schema, calculation policy, timezone or
  calendar dependency, authority, effective dates, and confirmation policy.
- **retire_content(ctx, kind, id) -> ContentRead** — moves `draft` or `approved`
  → `retired`. A retired definition stops feeding new matter work but stays in
  history; matters already bound to it keep their pinned version.

Every write re-checks the maintainer role from the repository context, applies
the domain transition, and audits a *content governance* event with actor,
target, before/after version references, and correlation id (inv. 8).

## 7. The template-vs-run split

This service resolves the split the frontend `Workflow` type only hints at.
The **definition** — a `WorkflowDefinition`, `WorkflowModule`,
`DeadlineRule`, `FormTemplate`, `SupportingDocumentTemplate`, or `QuestionSet`
with its `approvalState`, `version`, and `ownerId` — lives **here**.
Task-service compiles approved workflow definitions into a matter run.
Obligations-service evaluates approved deadline rules into dated occurrences.
Governance owns "what reviewed content and rules are available"; the consuming
service owns "what happened in this matter".

```text
content-governance-service          consuming service
──────────────────────────          ─────────────────
Workflow definition/module       ──▶ task-service WorkflowRun and StepRuns
DeadlineRule                     ──▶ obligations-service calculation
FormTemplate (approved, locked)  ──▶ draft bound to that template version
SupportingDocumentTemplate      ──▶ report/export renderer
```

A per-matter run may consume an `approved` definition only. It cannot pull a
`draft`, and a mid-matter `retire` does not yank the version a running matter
already pinned.

## 8. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Approved wording changes only via a new approved version (§5.3.6) | `approved` definitions are immutable; edits create a new `draft` version; approval never mutates in place |
| Locked wording cannot be altered (§9.2 release blocker) | `locked-prescribed` blocks are fixed at approval; changing them requires a new approved template version |
| Only a maintainer moves content through states | Role re-checked from context on every write; `draft→approved→retired` is maintainer-gated |
| Per-matter services consume `approved` only | Reads for matter work filter to `approvalState = approved`; draft/retired never feed a matter |
| Retire preserves history, does not yank pinned versions | Retired rows retained; a running matter keeps its bound version (mirrors inv. 7) |
| Versioned rule definitions carry authority metadata (Phase 5) | Approval records version, effective date, and authority metadata |
| Workflow phases stay canonical | Approved steps use one of the ten backend phases; four frontend work areas are presentation metadata only |
| Rules are declarative | Applicability and calculations use typed, allowlisted schemas; executable code and provider prompts are rejected |
| Referenced rules are pinned | An approved step references an exact approved deadline-rule version |
| Every governance mutation audited (inv. 8, §5.2) | `AuditPort.record` a content-governance event on create/version/approve/retire |
| Controlled content separate from matter data (§5.2) | Definitions live in their own tier; the service touches no matter storage |
| Catalogue entry is not approval | Inventory and rollout state never bypass `approvalState`; legal-content-blocked entries cannot be approved with placeholder wording |
| Official and Draftly-created outputs are distinguishable | Every output records its category and source; Draftly reports are never labelled as statutory forms |
| Notification and authentication templates stay outside | Content governance rejects notification-channel and authentication-template content kinds |

## 9. Failure modes to handle explicitly

- Edit attempted against an `approved` definition — rejected; the caller must
  `version_content` to a new draft (§5.3.6).
- Non-maintainer attempts a state transition — denied at the role re-check; a
  reviewer or approver cannot govern content.
- Approve a `FormTemplate` whose `locked-prescribed` block wording is still a
  placeholder — see open decisions; Form 8 prescribed wording is lawyer-owned
  and currently pending, so approval must not be faked with invented text.
- Retire a definition a running matter depends on — allowed; the running matter
  keeps its pinned version, only new work is blocked from the retired one.
- Concurrent version bumps on the same definition — optimistic version column
  rejects the stale write.
- Workflow approval references an unknown fact, document, or check key —
  rejected with the unresolved keys listed.
- Workflow approval references a draft, retired, or missing deadline rule —
  rejected.
- Deadline rule lacks authority, an effective range, or required calendar
  metadata — rejected.
- A definition attempts to contain executable code or an AI prompt — rejected.
- A prescribed form or lawyer-owned instrument is approved while it contains a
  placeholder or lacks its exact authority/effective-date metadata — rejected.
- A Draftly-created report is labelled as an official form — rejected.
- A notification or authentication template is submitted as governed legal
  content — rejected and routed to the owning service.

## 10. Test list

- **Unit:** `draft→approved→retired` transitions; editing an `approved`
  definition creates a new draft rather than mutating; `locked-prescribed`
  blocks fixed after approval; illegal-transition rejection; maintainer gate.
- **Contract:** `FormTemplate`, `WorkflowDefinition`, `WorkflowModule`,
  `SupportingDocumentTemplate`, `DeadlineRule`, `Question`, and `QuestionSet`
  schemas; the
  create/version/approve/retire request and response shapes; and the temporary
  frontend presentation-group adapter.
- **Integration:** approve then consume — a per-matter read returns only the
  `approved` version; retire does not affect a matter pinned to a prior version;
  task-service compiles pinned workflow modules; obligations-service evaluates
  a pinned deadline rule; audit event written on every transition.
- **Security:** non-maintainer cannot create, approve, or retire; no altered
  locked wording escapes; cross-role escalation denied; no secret or raw client
  data in logs.
- **Catalogue:** all 22 RTA identifiers are unique and mapped to the stated form
  number; MVP/V1/later classifications are valid; a catalogue item cannot be
  consumed without an approved version; ownership exclusions are enforced.
- **Legal gate:** placeholder prescribed text, missing authority metadata, or
  unapproved lawyer-authored wording blocks approval.

## 11. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Form 8 prescribed wording.** The `locked-prescribed` block text is
   **lawyer-owned and currently a placeholder pending** (plan §12, Phase 7). Do
   not invent legal wording. Decide whether an approval can proceed with an
   explicitly-marked placeholder block, or must block until the lawyer supplies
   final text. Lean **block approval of a `FormTemplate` whose locked blocks are
   still placeholders** — an approved template must carry real prescribed wording.
2. **One service or three.** Templates, workflows, and question sets share one
   `approvalState` lifecycle and one maintainer gate. Lean **one service with a
   `kind` discriminator** over three near-identical services; revisit if their
   validation rules diverge.
3. **Effective-date semantics.** Whether `approved` content activates
   immediately or on a recorded effective date (Phase 5 lists effective date as
   required metadata) — recommend **record the effective date, activate on it**.
4. **Endpoint namespace for writes.** Reads are `/api/templates`,
   `/api/questions`, `/api/question-sets`; the write verbs
   (create/version/approve/retire) need a settled path shape — recommend
   `POST /api/templates`, `POST /api/templates/{id}/versions`,
   `POST /api/templates/{id}/approve`, `POST /api/templates/{id}/retire`, and the
   same for questions/question-sets and workflows.
5. **Deadline-rule ownership.** Keep the approval and version lifecycle here,
   while obligations-service owns calculation execution, lawyer confirmation,
   recurrence, and generated occurrences.
6. **Workflow vocabulary.** Use the ten canonical phases and modular
   compilation. Preserve the current four-function frontend type only as a
   temporary grouped read model during migration.
7. **Supporting-document renderer.** Keep the definition lifecycle here, while
   a dedicated renderer/export adapter owns DOCX/PDF generation. Do not couple
   governance to a document-conversion library.
8. **MVP legal-content readiness.** The catalogue marks Transfer and Gift
   structures as MVP, but neither may become `approved` until the authorized
   conveyancing lawyer supplies and approves the actual wording. Static M2
   placeholders remain visibly marked and are never promoted.

## 12. Source register

The catalogue entries above must be reconciled against these primary sources
before their first approval:

- [Registrar General's Department — charges and registerable instrument
  categories](https://www.rgd.gov.lk/web/index.php/en/services/document-land-registration/notary/charges)
- [Prevention of Frauds
  Ordinance](https://www.srilankalaw.lk/revised-statutes/alphabetical-list-of-statutes/927-prevention-of-frauds-ordinance.html)
- [Powers of Attorneys
  Ordinance](https://www.srilankalaw.lk/revised-statutes/alphabetical-list-of-statutes/914-powers-of-attorney-ordinance.html)
- [Notaries
  Ordinance](https://www.srilankalaw.lk/n/823-notaries-ordinance.html)
- [Registrar General's Department — title
  transactions](https://www.rgd.gov.lk/web/index.php/en/services/document-land-registration/title/transactions)

The Gazette Extraordinary No. 2308/27 source file and publication metadata must
also be registered before any RTA form version is approved. A URL in this
document is a provenance lead, not proof that the local content version is
complete, current, or legally approved.
