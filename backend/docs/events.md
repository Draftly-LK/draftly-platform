# Event registry

Companion to `backend/backend-implementation-plan-v0.md`,
`jobs-and-workers.md`, and every service design under `docs/services/`.

This file is the **single source of truth for domain event names, payloads,
publishers, and consumers**. A service doc must not invent an event name. If an
event is not in the table below, it does not exist.

The registry exists because the service docs were written independently and
drifted: four events were consumed under a different name than the publisher
emitted, and thirteen more were consumed with no publisher at all. Both classes
of bug are silent — the consumer simply never fires — so they are caught by
schema and registry tests rather than by review.

## 1. Naming rule

```text
<aggregate>.<past-tense-kebab-case>
```

- **Aggregate** is one of the registered aggregates in §5. It is the thing that
  changed, not the service that changed it.
- **Past tense** because an event records something that already committed. A
  request for future work is a command through a port, not an event.
- **Kebab case** throughout. No underscores, no camelCase. `document.version-superseded`, never `document.version_superseded`.
- No verb suffixes such as `-event`, and no version number in the name. Payload
  versioning lives in the envelope (§2).

## 2. Envelope

Every event carries the same envelope. Payload fields sit under `data`.

```json
{
  "eventId": "evt-01K2...",
  "eventName": "particular.corrected",
  "eventVersion": 1,
  "occurredAt": "2026-08-05T11:42:07.113Z",
  "organisationId": "org-...",
  "matterId": "matter-...",
  "actorId": "user-...",
  "correlationId": "corr-01K2...",
  "causationId": "evt-01K2...",
  "idempotencyKey": "particular.corrected:fact-123:v7",
  "data": {}
}
```

Rules:

- `organisationId` is **required on every event**. It is the tenant boundary
  (`security-model.md` §2) and every consumer filters on it before doing
  anything else.
- `matterId` is nullable. User-scoped and firm-scoped events (obligations,
  billing, account changes) have no matter.
- `actorId` is null for events raised by a scheduler or a provider webhook. It
  is never a hardcoded demo id.
- `causationId` names the event that caused this one, so a chain is walkable.
- `eventVersion` starts at 1. An additive field change keeps the version; a
  removal or a semantic change increments it, and the consumer must handle both
  until the old version is retired.
- **No private matter content in an event.** Identifiers, classification
  metadata, and status values only — no party names, property descriptions,
  deed numbers, extracted values, transcript text, or suspicion narrative. Every
  event schema has a test asserting this (`service-definition-of-done.md` §4).

## 3. Delivery contract

- **Publish is transactional.** An event row is written to the outbox in the
  same transaction as the state change it describes. There is no fire-and-forget
  publish. See `jobs-and-workers.md` §2.
- **Delivery is at-least-once.** Every consumer must be idempotent on
  `idempotencyKey`, or on its own natural key when that is stronger.
- **Ordering is per aggregate instance only.** Two events for the same
  `matterId` arrive in publish order; events across matters or aggregates may
  interleave. A consumer that needs a global order is wrong and must be
  restructured.
- **A failed consumer never rolls back the publisher.** Notification delivery
  failing does not change an obligation; memory ingestion failing does not lose
  a transcript event.
- **Audit is not the event bus.** Writing an audit row is not publishing. Several
  service docs previously listed `workflow.instantiated` as an audit event while
  another service consumed it as a domain event; both are now required
  separately and named separately.

## 3.1 Three namespaces that look identical

`draft.approve` and `draft.approved` are one character apart and mean entirely
different things. Three dotted namespaces coexist, and a reader — or a grep —
will confuse them unless the distinction is stated:

| Namespace | Form | Example | Defined in |
| --- | --- | --- | --- |
| **Event** | `<aggregate>.<past-tense>` | `draft.approved` | this file |
| **Capability** | `<resource>.<imperative>` | `draft.approve` | `security-model.md` §3.1 |
| **Audit action** | `<aggregate>.<past-tense>` | `draft.submitted` | `audit-service.md` §3.2 |
| **Job type** | `<domain>.<imperative>` | `export.render` | `jobs-and-workers.md` §5 |
| **Entitlement key** | `<feature>.<noun>` | `export.enabled` | `billing-service.md` §5.1 |

Events and audit actions share a form deliberately — the same mutation usually
produces both, under the same name. They are still separate mechanisms: some
audited actions publish no event (a privileged read, a denied attempt), and some
events carry no audit row (a projection refresh). Where they differ, the audit
action is the finer-grained one: `draft.submitted` is audited, while the event
published for the same act is `draft.review-requested`, named for what
downstream consumers actually need to react to.

Capabilities, job types, and entitlement keys are imperative or nominal and are
never past tense, so a past-tense dotted name in code is always an event or an
audit action.

## 4. Registered aggregates

`user`, `organisation`, `matter`, `party`, `document`, `instrument`,
`particular`, `check`, `finding`, `workflow`, `obligation`, `draft`, `export`,
`corpus`, `content`, `assistant`, `agent`, `memory`, `voice`, `retention`,
`notification`, `billing`.

`assistant` and `agent` are distinct: `assistant` is the global research
conversation (`research_service`), `agent` is the per-matter chat session
(`matter_agent_service`).

Note that `check.*` and `finding.*` are separate aggregates published by the
same service: a `check` is a rule evaluation, a `finding` is its disposition.

## 5. The registry

Payload columns list `data` fields only; the envelope of §2 is always present.

A `—` in the Consumers column means the event has no subscriber today. That is
allowed: the event still records the mutation and still feeds the audit log,
which every publisher writes directly through `AuditPort` rather than by
subscribing. `audit_service` is deliberately absent from every Consumers cell
for that reason — it is a sink, not a subscriber.

### 5.1 Identity and tenancy — `auth_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `user.provisioned` | `userId`, `accountStatus` | — |
| `user.activated` | `userId`, `role`, `invitationId` | `notification_service` |
| `user.suspended` | `userId`, `reason` | `notification_service`, `obligations_service` |
| `user.role-changed` | `userId`, `beforeRole`, `afterRole` | — |
| `user.invited` | `userId`, `invitationId`, `expiresAt` | `notification_service` |
| `organisation.membership-changed` | `userId`, `role`, `changeKind` | `billing_service` |
| `matter.membership-changed` | `matterId`, `userId`, `role`, `changeKind` | `notification_service`, `obligations_service`, `task_service` |

`matter.membership-changed` is published by `auth_service`, not
`matter_service`. Membership has one writer (`security-model.md` §4).

### 5.2 Matter — `matter_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `matter.created` | `matterId`, `transactionType`, `registrationRegime`, `classificationVersion` | `task_service`, `billing_service` |
| `matter.activated` | `acceptedBy`, `acceptedAt` | `task_service`, `obligations_service` |
| `matter.classification-changed` | `fromVersion`, `toVersion`, `material` | `task_service`, `obligations_service` |
| `matter.assigned-notary-changed` | `fromUserId`, `toUserId` | `notification_service`, `obligations_service` |
| `matter.closed` | `readinessEvaluationId`, `workflowRunId` | `task_service`, `obligations_service`, `retention_service` |
| `matter.reopened` | `reason` | `task_service` |
| `matter.archived` | — | `retention_service` |

The old `matter.classification_changed` spelling consumed by `task_service` is
retired; the hyphenated name above is canonical.

### 5.3 Party — `party_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `party.created` | `partyId`, `partyKind` | — |
| `party.identity-evidence-recorded` | `partyId`, `evidenceKind`, `documentVersionId` | `task_service` |
| `party.identity-document-expiry-recorded` | `partyId`, `documentKind`, `expiresOn` | `obligations_service` |
| `party.screening-completed` | `partyId`, `outcome`, `confidentialityLevel` | `obligations_service`, `check_service` |
| `party.designated-person-confirmed` | `partyId`, `confidentialityLevel` | `obligations_service`, `notification_service` |

`party.identity-document-expiry-recorded` replaces the unpublished
`identity-document.expiry-recorded` that `obligations_service` expected.
`party.designated-person-confirmed` carries no name, list entry, or narrative;
it is the trigger for the restricted 24-hour escalation only.

### 5.4 Documents — `document_service` and its worker

| Event | Payload | Consumers |
| --- | --- | --- |
| `document.uploaded` | `documentId`, `documentVersionId`, `checksum`, `mime` | `task_service`, `billing_service` |
| `document.replaced` | `documentId`, `newVersionId`, `supersededVersionId` | `task_service`, `notification_service` |
| `document.version-superseded` | `documentId`, `supersededVersionId`, `successorVersionId` | `verification_service`, `task_service`, `memory_service`, `draft_service` |
| `document.processing-completed` | `documentVersionId`, `processingRunId`, `docClass`, `derivatives`, `sourceFileId`, `sourceVersion`, `documentReferences` | `task_service`, `document_processing` |
| `document.processing-failed` | `documentVersionId`, `processingRunId`, `outcome`, `terminal` | `notification_service`, `billing_service` |
| `document.extraction-completed` | `documentVersionId`, `processingRunId`, `candidateCount`, `conflictCount` | `verification_service` |

`document.version-superseded` is the corrected spelling. The old
`document.version_superseded` was the only snake_case name in the system.

`document.processing-completed` and `document.extraction-completed` are
deliberately separate. The first says derivatives exist, which is what a
document requirement projection needs. The second says candidate particulars
exist, which is what `verification_service.ingest_candidates` needs. Previously
`verification-service.md` subscribed to "the extraction-completion event", which
nothing published.

The source-processing API also includes `sourceFileId`, `sourceVersion` and
`documentReferences` containing exact document `id`, `version` and interpretation
`generation`. Reruns that reuse grouping re-read current, eligible document pins.
These identifiers support a durable operational document-review proposal. The
task consumer rechecks live actor authorization, ownership and supporting versions;
it suppresses stale or denied events. No extracted text enters this payload and
no event accepts facts, completes lawyer decisions or changes legal satisfaction.

`document.processing-failed` carries `terminal` so a consumer can distinguish a
retryable attempt from a dead-lettered run; only the terminal case notifies.

### 5.5 Notarial register — `notarial_register_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `instrument.attested` | `instrumentId`, `matterId`, `attestedAt`, `registrationRegime`, `notaryUserId`, `practisingJurisdictionId`, `registrationJurisdictionId` | `obligations_service`, `task_service` |
| `instrument.protocol-recorded` | `instrumentId`, `protocolNumber`, `registerEntryId` | `retention_service` |
| `instrument.registration-submitted` | `instrumentId`, `submittedAt`, `registryId` | `obligations_service` |
| `instrument.registration-acknowledged` | `instrumentId`, `acknowledgedAt`, `outcome` | `obligations_service`, `task_service` |
| `instrument.collection-ready` | `instrumentId`, `readyAt` | `obligations_service`, `notification_service` |
| `register.monthly-period-closed` | `notaryUserId`, `periodStart`, `periodEnd`, `instrumentIds` | `obligations_service` |

These five replace the unpublished `document.attested`,
`document.registration-acknowledged`, and `document.collection-ready` that
`obligations_service` expected. The aggregate is `instrument`, not `document`,
because an attestation is an act on a legal instrument, not a state of an
uploaded file.

`instrument.attested` carries both jurisdictions because the deed-registration
deadline branch (30 vs 60 days) is selected from them and
`obligations_service` must never guess (`obligations-service.md` §7.3).

### 5.6 Verified record — `verification_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `particular.verified` | `factId`, `key`, `evidenceRef` | `check_service`, `task_service` |
| `particular.corrected` | `factId`, `key`, `beforeRef`, `afterRef` | `check_service`, `task_service`, `memory_service` |
| `particular.added` | `factId`, `key`, `manualReason` | `check_service`, `task_service` |
| `particular.blocked` | `factId`, `key`, `reason` | `task_service` |
| `particular.evidence-stale` | `factId`, `supersededVersionId` | `task_service`, `memory_service`, `approval_service` |

`particular.corrected` carries value **references**, not values. Corrected
values are private matter content (§2).

### 5.7 Checks and findings — `check_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `check.result-changed` | `checkId`, `evaluationVersion`, `beforeStatus`, `afterStatus`, `blocking` | `task_service`, `approval_service` |
| `check.document-requested` | `checkId`, `requiredDocumentType`, `requestedByUserId`, `agreedDueAt?` | `obligations_service`, `task_service` |
| `finding.resolved` | `checkId`, `action`, `actorId` | `task_service`, `approval_service` |
| `finding.waived` | `checkId`, `reason`, `actorId` | `task_service`, `approval_service` |
| `finding.remediation-requested` | `checkId`, `checkEvaluationVersion`, `requiredActionKey` | `task_service` |

`finding.remediation-requested` is canonical. `check-service.md` previously
published `finding.remediation-created` while `task-service.md` consumed
`finding.remediation-requested`.

`check.result-changed` was consumed by `task_service` and published by nobody;
it is now a required publication from `run_checks`.

### 5.8 Workflow — `task_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `workflow.instantiated` | `workflowRunId`, `baseDefinitionVersion`, `moduleVersions` | `matter_service` |
| `workflow.setup-failed` | `reason`, `missingDefinitionKeys` | `matter_service`, `notification_service` |
| `workflow.step-completed` | `stepRunId`, `stepDefinitionId`, `phase` | `matter_service`, `obligations_service` |
| `workflow.step-overridden` | `stepRunId`, `overrideReason`, `actorId` | `matter_service` |
| `workflow.step-stale` | `stepRunId`, `causeRef` | `matter_service`, `approval_service` |
| `workflow.applicability-changed` | `stepRunId`, `beforeResult`, `afterResult` | `matter_service` |
| `workflow.run-stale` | `workflowRunId`, `causeRef` | `matter_service` |
| `workflow.run-superseded` | `oldRunId`, `newRunId`, `reason` | `matter_service`, `obligations_service` |
| `workflow.phase-changed` | `fromPhase`, `toPhase` | `matter_service` |
| `workflow.requirement-changed` | `requirementId`, `beforeState`, `afterState` | `matter_service`, `obligations_service` |
| `workflow.readiness-changed` | `stage`, `ready`, `blockerRefs` | `matter_service`, `draft_service` |
| `workflow.blocking-changed` | `blockingStatus`, `blockerIds` | `matter_service` |
| `workflow.review-requested` | `stepRunId`, `assignedRole`, `dueAt?` | `obligations_service`, `notification_service` |
| `workflow.signing-scheduled` | `scheduledFor`, `location?` | `obligations_service`, `notification_service` |

`workflow.instantiated`, `workflow.setup-failed` and `workflow.blocking-changed`
were consumed by `matter_service` but only ever written as audit rows. They are
now required outbox publications.

`workflow.review-requested` and `workflow.signing-scheduled` replace the
unpublished `task.review-requested` and `matter.signing-scheduled` that
`obligations_service` expected. Both are workflow state, so both take the
`workflow` aggregate.

### 5.9 Obligations — `obligations_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `obligation.created` | `obligationId`, `class`, `type`, `scope`, `dueAt` | — |
| `obligation.deadline-calculated` | `obligationId`, `ruleId`, `ruleVersion`, `rawDueAt` | — |
| `obligation.deadline-confirmed` | `obligationId`, `dueAt`, `confirmedBy` | `task_service`, `notification_service` |
| `obligation.deadline-corrected` | `obligationId`, `originalDueAt`, `dueAt`, `reason` | `task_service`, `notification_service` |
| `obligation.status-changed` | `obligationId`, `beforeStatus`, `afterStatus`, `class`, `confidentialityLevel` | `task_service`, `notification_service` |
| `obligation.cancelled` | `obligationId`, `reason` | `task_service` |
| `obligation.reminder-due` | `obligationId`, `recipientUserId`, `dueAt`, `reminderType`, `class`, `urgency`, `confidentialityLevel`, `templateKey`, `deliveryPolicyKey` | `notification_service` |
| `obligation.escalated` | `obligationId`, `escalationLevel`, `recipientUserId`, `confidentialityLevel` | `notification_service` |

`obligation.status-changed` is the single lifecycle event. The previously listed
`obligation.due`, `obligation.overdue` and `obligation.completed` are retired as
events: `obligations-service.md` §12 states that `upcoming`, `due` and `overdue`
are query projections from `dueAt` and server time, so publishing them per
transition contradicted the model. Persisted transitions — completion,
cancellation, correction, suspension — are what `obligation.status-changed`
reports.

### 5.10 Drafting, approval, export

| Event | Publisher | Payload | Consumers |
| --- | --- | --- | --- |
| `draft.created` | `draft_service` | `draftId`, `templateId`, `templateVersion` | — |
| `draft.version-saved` | `draft_service` | `draftVersionId`, `number`, `hash` | `approval_service` |
| `draft.version-restored` | `draft_service` | `draftVersionId`, `restoredFromVersionId` | — |
| `draft.review-requested` | `draft_service` | `draftVersionId`, `hash`, `requestedByUserId` | `notification_service`, `obligations_service` |
| `draft.approved` | `approval_service` | `approvalId`, `draftVersionId`, `contentHash`, `approverId` | `export_service`, `notification_service`, `task_service` |
| `draft.approval-invalidated` | `approval_service` | `approvalId`, `draftVersionId`, `reason` | `export_service`, `notification_service` |
| `export.requested` | `export_service` | `exportId`, `approvalId`, `format` | `billing_service` |
| `export.rendered` | `export_service` | `exportId`, `checksum`, `manifestRef`, `expiresAt` | `notification_service`, `retention_service` |
| `export.failed` | `export_service` | `exportId`, `failureCode`, `terminal` | `notification_service` |

`draft.review-requested` is new: it is emitted by `submit_for_review`, the step
that moves a draft `working → in-review`. Without it nothing could reach the
approval gate (`draft-service.md` §5.6).

`draft.approved` is a domain event, not only an audit row. `export_service` and
`notification_service` both need it.

### 5.11 Governed content and corpus

| Event | Publisher | Payload | Consumers |
| --- | --- | --- | --- |
| `content.definition-versioned` | `content_governance_service` | `kind`, `definitionId`, `newVersion` | — |
| `content.definition-approved` | `content_governance_service` | `kind`, `definitionId`, `version`, `effectiveFrom` | `task_service`, `obligations_service`, `check_service`, `draft_service` |
| `content.definition-retired` | `content_governance_service` | `kind`, `definitionId`, `version` | `task_service`, `obligations_service`, `check_service` |
| `corpus.source-approved` | `corpus_governance_service` | `sourceId`, `audience`, `policies` | `library_service`, `research_service` |
| `corpus.source-quarantined` | `corpus_governance_service` | `sourceId`, `audiences` | `library_service`, `research_service`, `memory_service` |
| `corpus.source-policy-changed` | `corpus_governance_service` | `sourceId`, `beforePolicies`, `afterPolicies` | `library_service`, `research_service`, `memory_service` |
| `corpus.release-published` | `corpus_governance_service` | `releaseId`, `audience`, `manifestChecksum` | `library_service`, `research_service` |
| `corpus.release-retired` | `corpus_governance_service` | `releaseId`, `audience` | `research_service`, `memory_service` |

### 5.12 Research, voice, notification, billing, retention

| Event | Publisher | Payload | Consumers |
| --- | --- | --- | --- |
| `assistant.question-asked` | `research_service` | `answerJobId`, `scopeType`, `corpusVersion` | `billing_service` |
| `assistant.answer-composed` | `research_service` | `answerId`, `kind`, `claimCount`, `abstained` | `memory_service` |
| `voice.transcript-partial-superseded` | `voice_service` | `sessionId`, `supersededEventId`, `successorEventId` | `memory_service` |
| `voice.transcript-finalised` | `voice_service` | `sessionId`, `candidateTranscriptId` | `memory_service` |
| `voice.transcript-revised` | `voice_service` | `sessionId`, `revisionId`, `supersedesVersionId` | `memory_service` |
| `voice.transcript-confirmed` | `voice_service` | `sessionId`, `transcriptVersionId`, `confirmedBy` | `memory_service` |
| `notification.delivered` | `notification_service` | `deliveryId`, `channel`, `providerMessageId` | — |
| `notification.failed` | `notification_service` | `deliveryId`, `channel`, `failureCode`, `terminal` | — |
| `notification.suppressed` | `notification_service` | `deliveryId`, `channel`, `reason` | — |
| `notification.preference-changed` | `notification_service` | `userId`, `channel`, `enabled` | — |
| `billing.trial-ending` | `billing_service` | `subscriptionId`, `trialEndsAt` | `notification_service` |
| `billing.payment-failed` | `billing_service` | `subscriptionId`, `failureCode` | `notification_service` |
| `billing.grace-period-ending` | `billing_service` | `subscriptionId`, `gracePeriodEndsAt` | `notification_service` |
| `billing.plan-changed` | `billing_service` | `subscriptionId`, `beforePlanVersionId`, `afterPlanVersionId` | `notification_service` |
| `billing.subscription-cancelled` | `billing_service` | `subscriptionId`, `effectiveAt` | `notification_service` |
| `billing.subscription-restricted` | `billing_service` | `subscriptionId`, `restrictedAt` | `notification_service` |
| `retention.hold-placed` | `retention_service` | `holdId`, `recordScope`, `sourceAuthority` | `obligations_service`, `document_service`, `export_service` |
| `retention.hold-released` | `retention_service` | `holdId`, `releaseEvidenceRef` | `obligations_service`, `document_service` |
| `retention.review-due` | `retention_service` | `recordScope`, `policyVersion`, `dueAt` | `obligations_service` |
| `retention.destruction-approved` | `retention_service` | `recordScope`, `approvedBy` | `document_service` |

Billing event names lose their underscores (`billing.trial_ending` →
`billing.trial-ending`). Voice event names lose theirs the same way.

### 5.13 Matter agent — `matter_agent_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `agent.session-created` | `sessionId` | `memory_service` |
| `agent.message-appended` | `sessionId`, `messageId`, `sequence`, `role` | `memory_service` |
| `agent.turn-completed` | `jobId`, `toolCallCount`, `outcome` | — |
| `agent.turn-failed` | `jobId`, `failureClass` | — |
| `agent.tool-executed` | `toolCallId`, `tool`, `capability` | — |
| `agent.tool-denied` | `toolCallId`, `tool`, `capability`, `reasonCode` | `notification_service` |
| `agent.action-proposed` | `actionId`, `actionKind` | — |
| `agent.action-confirmed` | `actionId`, `targetVersion` | `memory_service` |
| `agent.action-rejected` | `actionId`, `reasonCode` | — |
| `agent.suggestion-created` | `suggestionKind`, `targetRef`, `sourceDocumentVersionId` | `task_service`, `memory_service` |

No payload carries message text, tool arguments, or prompt content. The message
body stays in Neon and the `memory.sync` worker re-reads it by `messageId`,
because §2 forbids private matter content in an event.

`agent.tool-denied` is consumed by `notification_service` so a run of denials
against prohibited capabilities in one session can raise an operator alert. That
pattern is what a prompt injection looks like from the outside.

### 5.14 Memory scopes — `memory_service`

| Event | Payload | Consumers |
| --- | --- | --- |
| `memory.scope-initialised` | `scopeId`, `provider`, `entryCount` | — |
| `memory.scope-degraded` | `scopeId`, `state`, `reasonCode` | `notification_service` |
| `memory.scope-destroyed` | `scopeId`, `deletionReceiptId`, `entryCount` | `retention_service` |

`memory_service` previously published nothing. It still publishes nothing about
remembered content — these three describe the lifecycle of an external scope, so
retention can confirm erasure and operators can see a degraded provider. It
remains a consumer and a cache (`memory-service.md` §4).

## 6. Renames applied

Update these in code, fixtures, and any doc that still uses the left column.

| Retired name | Canonical name | Reason |
| --- | --- | --- |
| `document.version_superseded` | `document.version-superseded` | Only snake_case name in the system |
| `matter.classification_changed` | `matter.classification-changed` | Consumer/publisher spelling mismatch |
| `finding.remediation-created` | `finding.remediation-requested` | Consumer/publisher name mismatch |
| `obligation.due`, `obligation.overdue`, `obligation.completed` | `obligation.status-changed` | Date projections are not persisted transitions |
| `document.attested` | `instrument.attested` | Attestation acts on an instrument, not an upload |
| `document.registration-acknowledged` | `instrument.registration-acknowledged` | Same |
| `document.collection-ready` | `instrument.collection-ready` | Same |
| `identity-document.expiry-recorded` | `party.identity-document-expiry-recorded` | `identity-document` was not a registered aggregate |
| `task.review-requested` | `workflow.review-requested` | `task` is the internal resource name, `workflow` is the aggregate |
| `matter.signing-scheduled` | `workflow.signing-scheduled` | Signing is workflow state, not matter state |
| `billing.trial_ending` and siblings | `billing.trial-ending` and siblings | Underscores |
| `voice.transcript_finalised` and siblings | `voice.transcript-finalised` and siblings | Underscores |

## 7. Machine checks

These run in CI and are part of every service's definition of done
(`service-definition-of-done.md` §4).

1. **Registry parity.** `tests/contract/test_event_registry.py` parses this file
   and asserts that (a) every event a service subscribes to has exactly one
   publisher, (b) every event a service publishes appears in the registry, and
   (c) no code path emits a name absent from the registry. A consumed event with
   no publisher fails the build.
2. **Naming.** Every registered name matches
   `^[a-z][a-z-]*\.[a-z][a-z0-9-]*$` and its aggregate is in §4.
3. **Envelope.** Every published event validates against the envelope schema and
   carries a non-null `organisationId` and `correlationId`.
4. **Privacy.** A denylist test asserts no event payload field name or value in
   the fixture set matches the private-content patterns (party name keys, NIC
   patterns, `snippet`, `text`, `value`, `narrative`).
5. **Idempotency.** Every consumer has a test that processes the same event
   twice and asserts one effect.

## 8. What is deliberately not an event

- **Audit rows.** `AuditPort.record` is a write to the log, not a publication.
  A service that needs both does both.
- **Reads.** No `*.viewed` or `*.listed` events. Access logging is an audit
  concern (`audit-service.md`).
- **Commands.** `check_service` asking `task_service` for a remediation StepRun
  is a synchronous port call with an idempotency tuple, then a
  `finding.remediation-requested` event recording that it happened. The event
  does not carry the request.
- **Time passing.** No `obligation.became-overdue` tick. Overdue is computed
  from `dueAt` and server time.
