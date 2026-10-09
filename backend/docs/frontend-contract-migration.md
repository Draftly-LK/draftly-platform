# Frontend contract migration — M2 mocks to M3 API

## Optional scoped Form 8 (2026-10-09)

`POST /matters/{id}/forms` and `POST /forms/{id}/field-decisions` now require
`Idempotency-Key`. Field decisions retain their `If-Match` requirement. The
client persists actor/matter-scoped opaque retry metadata and reuses the original
version precondition after an ambiguous response. Intentional successful next
requests receive a new key. Current authorization runs before stored replay.

Form creation accepts `scope` and `predecessorFormId`; form reads expose both.
The scope pins a transaction, its association revision, and explicit parcel,
transferor and transferee selections. Null subject selections remain gaps.
`FormFieldRead.missingCause` explains absent, unreviewed, conflicted, stale,
unassigned and unsupported bindings. These are product diagnostics, not legal
wording. Both locale dictionaries provide labels and links to facts and inputs.
Existing nullable legacy scope remains readable. No prescribed text or template
approval/registration capability changes.

Companion to `backend/backend-implementation-plan-v0.md` §8,
`api-conventions.md`, and the service docs under `docs/services/`.

Six service docs say they mirror `frontend/src/types/*` exactly. Four others
declare breaking changes to those same types inside their own migration
sections. Nobody owned the union, so a frontend engineer had no way to see the
full break list. This file is that list.

Scope: `draftly-platform/frontend/src/types/*.ts`, the mock accessors in
`src/lib/data.ts`, the writes in `src/lib/mocks/demo-store.ts`, and the
simulator in `processing-simulator.ts`.

## 1. Rules for the migration

1. **The backend schema is the contract.** Where a frontend type and a service
   doc disagree, the service doc wins and this file records the change.
2. **A break is announced here before it ships.** CI fails an OpenAPI diff that
   removes or renames a field with no row in §3.
3. **Mock accessors are deleted, not left as fallbacks.** A screen that silently
   falls back to fixtures hides an outage and, worse, hides a permission denial.
4. **Loading, empty, blocked, failed, and permission-denied states survive every
   replacement** (plan §8). A screen that only handles success is not migrated.
5. **A 2xx never means a fact is verified.** The frontend must read the state
   field, not the status code.

## 2. Order of replacement

Plan §8 order, adjusted for the services that did not exist when it was written:

1. API client, session identity, error envelope, `correlationId` plumbing.
2. Organisation selection, subscription, plan, usage.
3. Matters list, create, overview.
4. Documents: upload, processing status, viewer.
5. Facts: candidates, evidence, verify, correct, conflicts.
6. Checks and workflow runs.
7. Assistant: conversations, ask, grounded answers, citations.
8. Drafts: create, save, restore, **submit**, approve, export.
9. Obligations, notifications, audit history.
10. Party, notarial register, retention consoles.

## 3. Breaking type changes

### 3.1 `Matter` (`types/matter.ts`) — largest break

| Current | M3 | Why |
| --- | --- | --- |
| `status: open \| in-review \| blocked \| ready-to-draft \| closed` | `lifecycleStatus: inquiry \| active \| closed \| archived` **plus** `blockingStatus: clear \| blocked` | One field mixed lifecycle, workflow phase, blocking, and readiness (`matter-service.md` §1) |
| `activeFunction: examination \| drafting \| execution \| attestation` | `currentPhase` from ten canonical phases, with the four functions as a presentation grouping | Presentation grouping is not the legal workflow |
| `progress` — four mutable counters | `MatterOperationalProjection` + `MatterReadinessSummary`, read-only | Progress was client-writable |
| `ownerId` only | `ownerId` **plus** explicit `MatterMembership` rows | `ownerId` is a responsibility pointer, not the authorisation policy (`security-model.md` §4) |
| — | `organisationId` added, required | Tenant boundary |
| `parties` embedded | `MatterPartyReference[]` pointing at `party_service` | Identity data leaves the matter root (`party-service.md`) |

The frontend must render inquiry-versus-active, workflow setup
`pending / ready / failed`, the canonical phase, the blocking reason, and
readiness provenance — and must not let a user edit any derived value.

### 3.2 `Workflow` / `Step` (`types/workflow.ts`)

| Current | M3 |
| --- | --- |
| `StepState: not-started \| in-progress \| complete \| blocked` | adds `pending-applicability`, `not-applicable`, `stale` |
| `Workflow.function` (four values) | `phase` (ten values); the four become a grouping |
| — | `applicabilityReason`, `evaluatedFactVersions`, `evaluatedDocumentVersions` |
| — | `QuestionResponse` is new (`task-service.md` §4.4) |

Every state renders with **text and an icon, not colour alone**
(`task-service.md` decision 6).

### 3.3 `Obligation` (`types/obligation.ts`)

Five fields become the read model in `obligations-service.md` §21: `scope`,
nullable `matterId`, `type`, `class`, `dueAt` + `timezone`, `hardness`,
`assignee`, `sourceSummary`, `calculationExplanation`,
`lawyerConfirmationStatus`, `confidentialityLevel`.

The dashboard groups by class, shows provenance and confirmation status for hard
deadlines, and **excludes `restricted-compliance` items from the ordinary list**.

### 3.4 `AuditEvent` (`types/audit.ts`)

| Current | M3 |
| --- | --- |
| `matterId` required | nullable |
| — | `organisationId` required |
| `AuditTargetType` — 8 values | 20 values (`audit-service.md` §3.1) |
| `action: string` | closed enum |
| `before?/after?: unknown` | typed reference + diff |
| list returns an array | paginated `page` envelope |

The history screen filters to the eight target types it renders today and shows
the rest under a generic row until the type is widened. It currently renders a
**hardcoded four-item list** and calls nothing — wiring `GET /history` is part
of step 9.

### 3.5 `Draft` (`types/draft.ts`)

The type is mostly unchanged; the **flow** changes.

- `approveDraft` no longer posts approve on a `working` draft. The sequence is
  `POST …/submit` then `POST …/approve` (`draft-service.md` §5). A UI that
  approves directly will now get an illegal-transition error.
- `createDraft` no longer returns `null` when facts are missing. It returns 422
  `draft_eligibility_unmet` with `details.missingFactKeys`, and the screen names
  the missing keys.
- The required-fact set comes from the template, not the hardcoded
  `transferee` + `extent` pair.
- `exportDraft` no longer flips state locally. It creates a job and the screen
  polls `GET /exports/{id}`.
- New read-only fields: `submittedVersionId`, `submittedBy`, `submittedAt`.

### 3.6 New types with no frontend equivalent

`Approval`, `Export`, `Manifest`, `Party`, `IdentityEvidence`, `CddAssessment`,
`Attestation`, `RegisterEntry`, `MonthlyReturnPeriod`, `RetentionSchedule`,
`LegalHold`, `Organisation`, `OrganisationMembership`, `MatterMembership`,
`Subscription`, `PlanEntitlement`, `NotificationPreference`,
`NotificationDelivery`, `ResearchConversation`, `ResearchMessage`,
`QuestionResponse`, `CheckRuleDefinition`.

### 3.7 Renames with no semantic change

| Frontend | Backend domain | Resolution |
| --- | --- | --- |
| `fact` | `particular` | Keep `facts` in the route surface, map once in the router (`verification-service.md` open decision 2) |
| `Tasks` | `workflow` / `run` / `step` | Route surface uses workflow; "Tasks" is internal (`task-service.md` decision 3) |

## 4. Accessor replacement table

| Mock accessor | Endpoint | Service | Notes |
| --- | --- | --- | --- |
| `getCurrentUser()` | `GET /me` | auth | Returns the authenticated user, not `users[0]` |
| `getMatters()` / `getMatter(id)` | `GET /matters`, `GET /matters/{id}` | matter | Paginated; new read model |
| `createMatter()` | `POST /matters` | matter | Needs `Idempotency-Key`; returns `workflowSetupStatus: pending` |
| `getDocuments(matterId)` | `GET /matters/{id}/documents` | document | Was undeclared on the backend side |
| `addDocument()` / `addVersion()` | `POST …/documents`, `POST /documents/{id}/versions` | document | Multipart; returns queued, never processed |
| `patchProcessing()` | *removed* | document | Client cannot write processing state; poll `GET /documents/{id}/processing` |
| `retryProcessing()` | `POST /processing/{job}/retry` | document | Idempotent |
| `getFacts(matterId)` | `GET /matters/{id}/facts` | verification | Paginated |
| `verifyFact()` / `correctFact()` / `addFact()` | `POST …/facts/{id}/verify`, `…/correct`, `POST …/facts` | verification | Need `If-Match`; role-gated |
| `getChecks()` / `getCrossChecks()` | `GET …/checks`, `…/cross-checks` | check | Paginated |
| `resolveCheck()` | `POST …/checks/{id}/resolve` | check | Reason required for waive |
| `getWorkflows()` / `completeStep()` | `GET …/workflows`, `POST …/steps/{id}/complete` | task | New states must render |
| `getDrafts()` / `createDraft()` / `saveVersion()` / `restoreVersion()` | `/matters/{id}/drafts…` | draft | See §3.5 |
| `approveDraft()` | `POST …/submit` then `POST …/approve` | draft, approval | Two calls now |
| `exportDraft()` | `POST …/exports` then poll `GET /exports/{id}` | export | Job-based |
| `getTemplates()` / `getQuestions()` / `getQuestionSets()` | `GET /templates`, `/questions`, `/question-sets` | content-governance | Approved versions only |
| `getObligations()` | `GET /obligations` | obligations | New read model, paginated, filtered |
| `getAnswers()` | `GET /assistant/answers` | research | Paginated |
| `recordAssistantAction()` | `POST /assistant/actions` | research | Audit-only in V0 |
| *(no accessor — dead textbox)* | `POST /assistant/conversations/{id}/messages` | research | The assistant becomes real |
| `getAuditEvents()` | `GET /history` | audit | Paginated; global feed newly wired |
| *(hardcoded list)* | `GET /library` | library | Case law stays disabled in V0 |
| `resetDemo()` | *removed* | — | No demo reset against real data |

## 5. Client-side decisions that move to the server

Each of these currently lives in the browser and must be deleted there, not
merely duplicated:

| Decision | Now enforced by |
| --- | --- |
| Draft eligibility (`transferee` + `extent`) | `draft_service.create_draft` |
| Who may approve | `approval_service` + `security-model.md` §3 |
| Which findings block | `check_service` + `approval_service` |
| Whether a requirement is accepted | `task_service.review_document_requirement` |
| Processing state transitions | `document_service` worker |
| Audit ids, timestamps, and actor | `audit_service.record` |
| Readiness and progress | `task_service` evaluations |
| Feature availability by plan | `billing_service.require_feature` |

Hiding a button is presentation. It is never a control.

## 6. Definition of done for the migration

Per plan §8, plus:

- [ ] No mock accessor remains on a production path.
- [ ] No client-only permission or eligibility decision remains.
- [ ] Every replaced screen handles loading, empty, blocked, failed, and
      permission-denied.
- [ ] Every list consumes the `page` envelope and paginates.
- [ ] Every mutation sends `If-Match` where the aggregate is versioned and
      `Idempotency-Key` where the route requires it.
- [ ] Error rendering switches on `error.code`, never on `message`.
- [ ] The end-to-end journey — create matter, upload, verify, check, draft,
      submit, approve, export — completes through the real API.
