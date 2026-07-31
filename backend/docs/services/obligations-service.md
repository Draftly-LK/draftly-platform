# obligations_service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`task-service.md`, `check-service.md`, `notification-service.md`, and
`audit-service.md`. One markdown file is kept per service under
`backend/docs/services/`.

This design replaces the earlier five-field dashboard-list model.
`obligations_service` is a deadline and commitment engine for dated legal,
compliance, client, and operational actions. It is not a generic to-do list.

Legal review status: the Sri Lankan rules below are source-backed product
requirements, not an approved production rule pack. A lawyer must confirm each
source, trigger, calculation method, exception, and effective date before the
rule can generate an authoritative deadline.

## 1. Decision

The service answers:

```text
what must happen
by what time
because of which source or commitment
who is responsible
how the due date was calculated
whether a lawyer confirmed it
```

The broader duty model has five categories:

```text
1. Hard legal deadlines
2. Recurring statutory or compliance duties
3. Matter follow-ups and client commitments
4. Non-date professional duties
5. Record-retention duties
```

Only the first three normally appear as active dashboard reminders.
Non-date professional duties belong to workflow gates and checks. Retention is
normally system-controlled and appears to a user only when review or
destruction approval is required.

## 2. Service boundaries

```text
task_service
  owns what must be done and the workflow state

check_service
  owns what is wrong, missing, conflicting, or incomplete

obligations_service
  owns what must happen by a particular time

notification_service
  owns how a due reminder is delivered

audit_service
  owns the append-only record of what happened
```

An obligation may originate from a task, check, court order, statutory rule,
client promise, firm policy, or manual lawyer decision. It references that
source; it does not absorb the source service's domain state.

Examples:

```text
check_service finds a missing survey plan
  -> lawyer requests the plan by an agreed date
  -> obligations_service tracks that dated commitment

task_service records attestation
  -> governed deadline rule calculates a registration date
  -> lawyer confirms the calculation
  -> obligations_service tracks the legal deadline

obligation reminder becomes due
  -> obligations_service emits obligation.reminder-due
  -> notification_service delivers allowed channels
```

## 3. What it owns

The service owns:

- dated obligations and commitments;
- recurrence and reminder schedules;
- source and legal-authority provenance;
- trigger events and trigger dates;
- governed due-date calculation rules;
- assignee and backup-assignee responsibility;
- lawyer confirmation of calculated legal deadlines;
- completion evidence references;
- escalation state;
- reminder occurrences already emitted; and
- status transitions caused by dates or explicit completion.

It does not own:

- undated workflow steps or professional-conduct gates;
- the underlying task, check, matter, document, or court order;
- legal content authoring;
- universal litigation deadline tables;
- email, push, SMS, provider retries, or bounce handling;
- record destruction itself; or
- an inference that a generated deadline is legally authoritative.

## 4. Obligation classification

Two dimensions are required. `ObligationClass` communicates why the date
matters. `ObligationType` gives the product a stable operational vocabulary.

```text
ObligationClass =
  legal-deadline
  compliance-deadline
  client-commitment
  internal-target
  follow-up
  administrative-reminder
  retention-review
```

```text
ObligationType =
  court-date
  filing-deadline
  service-deadline
  limitation-deadline
  notarial-monthly-return
  notarial-registration
  notarial-annual-certificate
  aml-cdd
  aml-sanctions-report
  aml-str
  aml-policy-review
  client-follow-up
  document-request
  lawyer-review
  signing-appointment
  registry-follow-up
  document-collection
  retention-review
  internal-admin
```

The display must show the class as text and an icon. Color alone must never
make an internal target look equivalent to a statutory deadline.

## 5. Domain model

### 5.1 Obligation

```text
Obligation
  id
  organisationId
  scope = user | matter | firm
  matterId?
  ownerUserId?
  type
  class
  labelKey
  sourceType
  sourceId
  sourceVersion?
  legalAuthorityRef?
  triggerType
  triggerId?
  triggerDate
  dueAt
  timezone
  calculationRuleId?
  calculationVersion?
  calculationExplanation
  hardness = hard | soft
  status
  assigneeUserId
  backupAssigneeUserId?
  recurrenceRule?
  reminderPolicyId
  escalationPolicyId?
  confidentialityLevel
  lawyerConfirmation
  completionEvidenceRef?
  completedAt?
  completedBy?
  cancelledAt?
  cancelledBy?
  cancellationReason?
  version
  createdAt
  updatedAt
```

`matterId` is nullable because annual notarial certification and firm AML
administration are not tied to a single matter.

`labelKey` is a message-catalogue key. Private facts and legal prose do not
belong in a free-form dashboard label.

### 5.2 Status

```text
ObligationStatus =
  draft
  awaiting-confirmation
  upcoming
  due
  overdue
  complete
  cancelled
  suspended
```

`draft` and `awaiting-confirmation` do not create external reminders.
A generated hard legal deadline enters `awaiting-confirmation` until a lawyer
confirms or corrects the calculation.

### 5.3 LawyerConfirmation

```text
LawyerConfirmation
  status = not-required | pending | confirmed | corrected
  confirmedBy?
  confirmedAt?
  reason?
  originalDueAt?
```

Hard legal and compliance deadlines require `confirmed` or `corrected` before
they become authoritative. The UI must still surface an unconfirmed candidate
prominently so confirmation cannot be forgotten.

### 5.4 Confidentiality

```text
ConfidentialityLevel =
  standard
  private-matter
  restricted-compliance
```

`restricted-compliance` is required for sanctions and suspicious-transaction
work. Those obligations are visible only to approved compliance roles and must
not place suspicion details in email, push, ordinary audit text, or dashboard
previews.

### 5.5 ReminderOccurrence

```text
ReminderOccurrence
  id
  obligationId
  recipientUserId
  reminderType
  scheduledFor
  emittedAt?
  eventId?
```

The uniqueness rule is:

```text
unique(obligationId, recipientUserId, reminderType)
```

This records the decision to request a reminder. Channel delivery belongs to
`notification_service`.

## 6. Governed deadline rules

Due dates are calculated by versioned definitions, not `if` statements spread
through application code:

```text
DeadlineRule
  id
  type
  jurisdiction
  registrationRegime?
  transactionType?
  triggerType
  calculationMethod
  timezone
  sourceAuthority
  sourceUrl
  sourceSection
  effectiveFrom
  effectiveTo?
  exceptions
  approvalState = draft | approved | retired
  approvedBy?
  approvedAt?
  version
```

The rule engine returns an explainable candidate:

```text
DeadlineCalculation
  triggerDate
  ruleId
  ruleVersion
  rawDueAt
  adjustedDueAt?
  adjustmentReason?
  explanation
  warnings
```

Draftly must preserve the rule version and the exact inputs used. Changing an
approved rule never silently rewrites an existing confirmed deadline.
Migration requires a lawyer-reviewed recalculation with before/after audit
history.

Business-day adjustment, public holidays, service rules, and court-specific
directions are separate governed inputs. The engine must not assume a general
weekend or holiday adjustment.

## 7. Sri Lankan notarial rule candidates

These candidates define the first rule-review backlog. They are not production
rules until a lawyer approves them.

### 7.1 Annual notarial practice certificate

The Notaries (Amendment) Act, No. 31 of 2022 changed the date in section 27(2)
from March to April. The consolidated rule requires application and grant on
or before 1 April and provides for one-year validity. Section 28 also requires
application material relating to deed duplicates from the previous year.

Candidate:

```text
type: notarial-annual-certificate
class: compliance-deadline
scope: user
trigger: annual recurrence
due: 1 April, Asia/Colombo
hardness: hard
severity: critical
lawyer confirmation: required when rule is first assigned or revised
```

Product copy should say "annual notarial practice certificate", not the less
precise "notary licence renewal".

### 7.2 Monthly deed return

The Notaries Ordinance requires the relevant duplicates and monthly list to
reach the Registrar of Lands by the 15th day of the following month. It also
provides for a nil list when no instrument was executed, subject to the stated
exception. The current prescribed form must come from approved content; this
service must not author it.

One monthly return aggregate should track the required components:

```text
type: notarial-monthly-return
class: compliance-deadline
scope: user
trigger: close of previous calendar month
due: 15th day of following month, Asia/Colombo
components:
  - prepare monthly deed list
  - submit deed duplicates
  - send other required copy where applicable
  - submit nil return when applicable
hardness: hard
```

The aggregate is generated from deeds attested in the previous month. Draftly
must retain the included deed ids and versions as completion evidence without
exposing client data in reminder text.

### 7.3 Registration after attestation

Section 31(30A), inserted by Act No. 31 of 2022, provides different periods
from the attestation date depending on whether registration is within or
outside the notary's practising jurisdiction.

Candidate rule branches:

```text
within practising jurisdiction
  trigger: attestation date
  period: 30 days

outside practising jurisdiction
  trigger: attestation date
  period: 60 days
```

The calculation must capture:

```text
attestation date
notary practising jurisdiction at attestation
registration jurisdiction
selected rule branch
calculated due date
source section and rule version
lawyer confirmation
```

Jurisdiction classification must never be guessed from an address string.
It comes from verified matter and notary-registration data.

### 7.4 Office change or discontinuance

The Notaries Ordinance provides for one month's notice of an intended office
change or discontinuance of practice, followed by further notifications when
the office changes.

Candidate:

```text
type: internal-admin
class: compliance-deadline
scope: user
trigger: lawyer-entered planned change date
due: one month before the planned change
hardness: hard
```

This is outside the first conveyancing V0 but fits the same engine.

## 8. AML/CFT treatment

FIU guidance applies to legal professionals undertaking captured activities.
Draftly must distinguish workflow gates, urgent restricted obligations, and
recurring compliance administration.

### 8.1 CDD is primarily a gate

CDD before or at establishment of the relevant client relationship, beneficial
owner verification, risk profiling, ongoing review, and enhanced CDD are
normally workflow requirements:

```text
task_service
  complete CDD
  verify beneficial owner
  review high-risk profile
  refresh expired identity evidence
  perform enhanced CDD

check_service
  block captured workflow while required CDD is incomplete
```

Create an obligation only when the gate has a due date, such as a lawyer-set
review date or expiring identity evidence.

### 8.2 Designated-person escalation

The FIU's 2023 guidance states that, when the relevant designated-person
condition is found, the Competent Authority must be informed with a copy to
the FIU within 24 hours.

Candidate:

```text
type: aml-sanctions-report
class: compliance-deadline
scope: firm
trigger: confirmed designated-person condition
due: 24 hours from discovery
hardness: hard
confidentiality: restricted-compliance
severity: emergency
assignee: compliance officer
backup: approved senior compliance role
```

This requires immediate secure in-app escalation. External notifications carry
only a neutral action prompt and never the matched name, list entry, client,
matter, or suspicion details.

### 8.3 Suspicious transaction reporting

The FIU guidance treats suspicion at formation, including an attempted or
uncompleted transaction, and identifies the compliance officer as the
submitting role and keeper of the STR register.

An STR item is not an ordinary dashboard reminder:

```text
type: aml-str
class: compliance-deadline
scope: firm
confidentiality: restricted-compliance
visibility: compliance officer and explicitly approved roles only
notification: secure neutral alert
```

The legal trigger, timing, privileges, confidentiality, and no-tipping-off
controls require a separately approved compliance workflow. Draftly must not
infer suspicion, auto-submit a report, or expose its existence to ordinary
matter members.

### 8.4 Compliance administration

Policy review, training, staff screening, firm risk assessment, compliance
officer details, high-risk file review, and independent audit may become
recurring obligations. Their frequency comes from approved law, regulator
material, or firm policy. Draftly must not invent a default frequency.

## 9. Non-date professional duties

Professional duties without a trigger date are not obligations. They are
permanent gates and checklist steps.

```text
before matter opening
  -> conflict check

before accepting instructions
  -> capacity, independence, and scope check

before attestation
  -> jurisdiction, language, identity, witness, authority, and evidence checks

after attestation
  -> preserve protocol, update register, prepare duplicate,
     create registration deadline, include in monthly return

before adding a team member
  -> confidentiality and access check

before paying client funds
  -> authority and purpose check

before matter closure
  -> client property and document return check
```

If a dated action arises from one of these gates, the owning service creates an
obligation by reference. The obligation does not replace the gate.

## 10. Retention duties

FIU guidance describes six-year record keeping for specified CDD, identity,
transaction, correspondence, and FIU-report records, with longer retention for
records subject to an ongoing investigation, litigation, court requirement, or
other authority requirement until release is communicated.

These are lifecycle controls:

```text
RetentionPolicy
  recordClass
  triggerEvent
  retentionPeriod
  authority
  version

LegalHold
  id
  recordScope
  sourceAuthority
  placedAt
  releasedAt?
  releaseEvidenceRef?
```

The retention engine prevents deletion. It creates a user-facing
`retention-review` obligation only when human review, legal-hold release, or
secure-destruction approval is required. Retention expiry must never cause
automatic destruction of a record under an active hold.

## 11. Matter and operational commitments

The service also supports dated work that is not a statutory deadline:

```text
client and matter
  - follow up for missing instructions
  - request a missing deed or plan
  - send an agreed status update
  - confirm a signing appointment
  - review a dormant matter

document
  - identity document expires
  - valuation or search needs refreshing
  - certified copy remains outstanding
  - original document must be returned

workflow
  - lawyer review pending
  - unresolved check due for review
  - draft awaiting approval
  - signing preparation incomplete
  - registration acknowledgement pending
  - registered deed ready for collection

administration
  - retainer or disbursement follow-up
  - invoice review
  - time-entry cut-off
  - client-money reconciliation
```

These must be labelled `client-commitment`, `internal-target`, `follow-up`, or
`administrative-reminder`, not `legal-deadline`.

## 12. Lifecycle and transitions

```text
manual soft commitment
  -> upcoming -> due -> overdue -> complete

calculated hard deadline
  -> awaiting-confirmation
  -> confirmed or corrected
  -> upcoming -> due -> overdue -> complete

draft rule or incomplete source
  -> draft
  -> no reminders and no authoritative display

active obligation
  -> cancelled only with actor, reason, and authority
  -> suspended only through an approved hold or policy
```

Date-driven `upcoming`, `due`, and `overdue` are query projections from
`dueAt` and current server time. They do not need hourly database updates.
Completion, cancellation, correction, and suspension are persisted decisions.

An overdue legal deadline remains overdue until explicitly completed or
resolved. Notification delivery success never changes it.

## 13. Application methods

### 13.1 create_manual_obligation

```text
create_manual_obligation(ctx, command) -> ObligationRead
```

Creates a client commitment, internal target, follow-up, or administrative
reminder. Hard legal classification requires an approved rule or an explicit
authority reference and lawyer role.

### 13.2 generate_from_trigger

```text
generate_from_trigger(ctx, trigger) -> list[ObligationRead]
```

1. Resolve approved rules effective for the trigger date.
2. Reject ambiguous rule matches.
3. Calculate candidates deterministically.
4. Persist source, trigger, input, rule version, and explanation.
5. Set hard legal candidates to `awaiting-confirmation`.
6. Audit the generated candidate without private fact values.

### 13.3 confirm_deadline

```text
confirm_deadline(ctx, obligation_id, due_at?, reason?) -> ObligationRead
```

Requires a lawyer. Confirming accepts the generated due date. Correcting
requires a reason and preserves the original due date. Both are audited.

### 13.4 complete_obligation

```text
complete_obligation(
  ctx,
  obligation_id,
  completion_evidence_ref?
) -> ObligationRead
```

Completion records actor and server time. Hard legal and compliance
obligations may require evidence configured by their rule.

### 13.5 list_obligations

```text
list_obligations(ctx, filters) -> page[ObligationRead]
```

Filters include scope, matter, assignee, class, type, status, due range, and
confidentiality permitted by the actor's role. The default dashboard query
returns active items from the first three duty categories only.

### 13.6 emit_due_reminders

```text
emit_due_reminders(as_of) -> count
```

Claims eligible obligations, creates missing ReminderOccurrences, and writes
`obligation.reminder-due` events to the transactional outbox in one
transaction. It skips draft, awaiting-confirmation, complete, cancelled, and
suspended obligations.

## 14. API surface

```text
GET   /api/v1/obligations
POST  /api/v1/obligations
GET   /api/v1/obligations/{id}
POST  /api/v1/obligations/{id}/confirm
POST  /api/v1/obligations/{id}/complete
POST  /api/v1/obligations/{id}/cancel
GET   /api/v1/obligation-rules
```

Ordinary users can read only obligations in scopes they are authorized to see.
Rule authoring and approval belong to governed content administration, not
these ordinary routes.

There is no endpoint that accepts a date and labels it a legal deadline without
source and confirmation controls.

## 15. Events

The service consumes:

```text
document.attested
document.registration-acknowledged
document.collection-ready
check.document-requested
task.review-requested
matter.signing-scheduled
matter.closed
identity-document.expiry-recorded
retention.hold-placed
retention.hold-released
```

It publishes:

```text
obligation.created
obligation.deadline-calculated
obligation.deadline-confirmed
obligation.deadline-corrected
obligation.due
obligation.overdue
obligation.completed
obligation.cancelled
obligation.reminder-due
```

Consumers use event ids and obligation ids idempotently. Events contain
identifiers and classification metadata, not private matter values.

## 16. Notification integration

`obligation.reminder-due` carries:

```text
eventId
occurredAt
obligationId
matterId?
recipientUserId
dueAt
reminderType
obligationClass
urgency
confidentialityLevel
templateKey
deliveryPolicyKey
correlationId
```

The notification service decides channels from the delivery policy and
permitted preferences. It records delivery separately.

Restricted compliance events use a neutral template and secure destination.
They never include a client name, designated-list match, suspicion narrative,
matter reference, property, deed number, or source excerpt.

## 17. Authorization and privacy

- User-scoped duties are visible to the owner and approved administrators.
- Matter-scoped duties require current matter membership.
- Firm-scoped duties require an approved firm role.
- Restricted compliance duties use a separate allowlist; ordinary matter
  membership is insufficient.
- A backup assignee receives access only if policy grants it.
- Cross-matter reads are filtered server-side.
- Non-members receive 404 where matter existence would otherwise be disclosed.
- Labels, events, audit entries, logs, and notifications contain minimal
  identifying information.
- Demo and test obligations use synthetic users, matters, deeds, and dates.

## 18. Audit

Material actions write an append-only audit event in the same transaction:

```text
obligation.created
obligation.confirmed
obligation.corrected
obligation.completed
obligation.cancelled
obligation.suspended
obligation.assignee-changed
obligation.rule-migrated
```

The event records actor, target, source/rule references, before/after state,
reason where required, and correlation id. It does not copy restricted
compliance content or raw client data.

Pure time projections and automated reminder emissions belong in operational
event history, not one user-facing audit entry per clock tick.

## 19. Failure modes

- No approved rule matches a hard deadline trigger: create no authoritative
  obligation; surface a configuration blocker.
- Multiple rules match: refuse calculation; never choose by list order.
- Trigger data is incomplete or unverified: keep the candidate blocked or
  awaiting confirmation.
- Jurisdiction cannot be resolved: do not choose the 30-day or 60-day branch.
- Rule changes after confirmation: preserve the old rule and due date; require
  explicit migration review.
- Reminder worker runs twice: ReminderOccurrence uniqueness prevents duplicate
  events.
- Notification fails: obligation state remains unchanged.
- Assignee loses access: suspend delivery and escalate reassignment without
  disclosing matter data.
- Legal hold exists at retention expiry: prevent destruction.
- Restricted compliance item is requested by an ordinary member: return no
  record and no existence signal.

## 20. Test list

### Unit

- Class and type validation.
- User-, matter-, and firm-scope invariants.
- Deterministic approved-rule selection.
- Ambiguous and missing rule rejection.
- Awaiting-confirmation gate for hard deadlines.
- Lawyer confirmation and correction with preserved original date.
- Date projection across upcoming, due, and overdue in `Asia/Colombo`.
- ReminderOccurrence idempotency.
- Retention hold preventing destruction review completion.

### Rule fixtures

- Annual certificate candidate resolves to 1 April under the approved current
  rule version.
- Monthly return candidate resolves to the 15th of the following month.
- Local attestation produces the reviewed 30-day branch.
- Outside-jurisdiction attestation produces the reviewed 60-day branch.
- Unknown jurisdiction produces no authoritative deadline.
- Designated-person escalation produces a restricted 24-hour candidate.

These fixtures verify implementation of lawyer-approved rules. They are not a
substitute for legal approval of the rules.

### Contract

- Expanded Obligation schema and enums.
- Nullable `matterId` and explicit scope.
- Source, trigger, calculation, confirmation, confidentiality, and recurrence.
- Filtered and paginated list API.
- `obligation.reminder-due` event compatibility with
  `notification_service`.

### Integration

- Attestation event creates an awaiting-confirmation registration deadline.
- Lawyer confirmation activates reminders.
- Monthly close generates one return aggregate and no duplicate on replay.
- Completion evidence and audit event commit together.
- Reminder occurrence and outbox event commit together.
- Delivery failure does not mutate the obligation.
- Rule migration preserves the prior calculation and audit history.

### Security

- Cross-matter and cross-user isolation.
- Firm-role checks.
- Restricted compliance allowlist.
- No private content in events, logs, notification payloads, or audit text.
- A non-lawyer cannot confirm or correct a hard legal deadline.
- A client-supplied arbitrary date cannot be promoted to a legal deadline.

## 21. Frontend contract migration

The M2 frontend type is intentionally small:

```text
id, matterId, labelKey, dueDate, status
```

M3 must replace it with an expanded read model. At minimum the dashboard needs:

```text
id
scope
matterId?
type
class
labelKey
dueAt
timezone
status
hardness
assignee
sourceSummary
calculationExplanation?
lawyerConfirmationStatus
confidentialityLevel
```

The dashboard should group or filter by class, show provenance and confirmation
for serious deadlines, and avoid rendering restricted compliance items in the
ordinary obligations list.

## 22. V0 scope

Implement first:

```text
1. Annual notarial practice certificate
2. Monthly deed, duplicate, applicable-copy, or nil return
3. Deed-registration deadline with 30-day or 60-day reviewed branch
4. Signing and attestation appointment
5. Missing deed, plan, or assessment follow-up
6. Mandatory lawyer-review deadline
7. Registration-status follow-up
8. Registered deed or document collection
9. Dated CDD completion gate
10. Restricted urgent sanctions escalation
```

Defer litigation docketing until litigation is an approved product workflow.
The model supports it, but Draftly must not ship a universal table of court,
filing, service, appeal, review, or limitation periods.

## 23. Decisions to confirm before coding

1. Treat obligations as a deadline and commitment engine, not a thin dashboard
   list or generic task service.
2. Keep the five-category duty taxonomy and show only the first three as normal
   active reminders.
3. Expand the frontend and backend Obligation contracts in M3.
4. Require source, trigger, calculation explanation, and lawyer confirmation
   for hard legal deadlines.
5. Store approved deadline rules as versioned governed content.
6. Make `matterId` nullable and require explicit user, matter, or firm scope.
7. Add restricted-compliance visibility and neutral notification policies.
8. Keep retention as a system lifecycle control with obligations only for
   human review.
9. Implement the ten-item conveyancing V0 scope above and defer litigation
   deadline rules.

## 24. Sources for legal review

Primary or official sources to pin in the governed rule records:

- [Notaries (Amendment) Act, No. 31 of 2022](https://www.parliament.lk/uploads/acts/gbills/english/6270.pdf)
- [Registrar General's Department: Notaries Ordinance PDF](https://rgd.gov.lk/web/images/ActsPDF/notary/Notaries-English.pdf)
- [Registrar General's Department: Notaries (Amendment) Act, No. 6 of 2024](https://rgd.gov.lk/web/images/ActsPDF/notary/06-2024_E.pdf)
- [Registrar General's Department: document registration](https://www.rgd.gov.lk/web/index.php/en/services/document-land-registration/movable-and-immovable-properties/document-registration1)
- [FIU: AML/CFT Compliance Obligations for Attorneys-at-Law and Notaries, No. 02 of 2023](https://fiusrilanka.gov.lk/docs/Guidelines/2023/Guidelines_02_2023.pdf)
- [Financial Transactions Reporting Act, No. 6 of 2006](https://fiusrilanka.gov.lk/docs/ACTs/FTRA/Financial_Transactions_Reporting_Act_2006-6_%28English%29.pdf)

Practitioner discussions may inform usability and operational safeguards, such
as dual-calendar review and inactive-file checks. They are never legal
authority and never enter a deadline calculation rule.
