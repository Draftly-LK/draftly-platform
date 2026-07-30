# content-governance-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `library-service.md`,
and the task-service design. This service is the **maintainer's tier**: it
governs the controlled legal *content* that per-matter work consumes — form
templates, workflow templates, and question sets — and owns the guarantee that
approved wording changes only through a new approved version.

Maps to plan **Phase 5** ("versioned rule definitions with authority metadata,
version, effective date"), the maintainer role, invariant **§5.3.6**, the
trust-boundary row *Legal corpus* (§5.2), and the *content governance* audit
event (§5.2). Frontend reads (`GET /api/templates`, `/api/questions`,
`/api/question-sets`) exist as mock accessors; the write path does not.

## 1. What it owns

The lifecycle of **controlled, versioned content definitions**: `FormTemplate`
(Form 8 and its kin), `Workflow` templates, and `QuestionSet`s / `Question`s.
Each carries an `approvalState` and moves `draft → approved → retired` only under
a maintainer's hand. It owns the create/version/approve/retire write path and
the read path that hands `approved` definitions to per-matter services.

It does **not** run a workflow (task-service runs an instance of an approved
template), does **not** bind facts into a draft (draft-service does), and does
**not** author legal wording — that stays lawyer-owned. It governs the
definition; other services consume it.

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
- **Workflow** (from `frontend/src/types/workflow.ts`) — `{ id, titleKey,
  regime, transactionTypes, function, approvalState, language, ownerId, version,
  steps: Step[] }`, where `function` is `examination | drafting | execution |
  attestation`. This is the **template**; task-service runs an instance of it.
- **Question** (from `frontend/src/types/question.ts`) — `{ id, prompt, scope,
  language, frequentlyWrong }` where `scope` is `matter | step | standalone`.
- **QuestionSet** — `{ id, titleKey, descriptionKey, questionIds, approvalState,
  ownerId }`.

Enums and shared values (exact):

| Field | Values |
| --- | --- |
| `FormTemplate.approvalState` / `Workflow.approvalState` / `QuestionSet.approvalState` | `draft`, `approved`, `retired` |
| `FormTemplateBlock.kind` | `locked-prescribed`, `editable` |
| `Question.scope` | `matter`, `step`, `standalone` |
| `Workflow.function` | `examination`, `drafting`, `execution`, `attestation` |
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

## 4. Ports it depends on

In `ports/`:

- `ContentRepository` — persist and load `FormTemplate`, `Workflow`, and
  `QuestionSet`/`Question` definitions with their versions; list by
  `approvalState`; fetch the current `approved` version for a per-matter
  consumer.
- `AuditPort` — `record(event)`; every governance transition writes a *content
  governance* audit event (§5.2).

No object storage, no retrieval, no processing. Governance is metadata and
versioning; it touches neither matter storage nor the legal corpus index.

## 5. The methods

### Read (maintainer console and per-matter consumers)

- **list_templates(ctx, filter) -> FormTemplateRead[]** — `GET /api/templates`.
- **list_questions(ctx, filter) -> QuestionRead[]** — `GET /api/questions`.
- **list_question_sets(ctx, filter) -> QuestionSetRead[]** — `GET
  /api/question-sets`.

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
- **retire_content(ctx, kind, id) -> ContentRead** — moves `draft` or `approved`
  → `retired`. A retired definition stops feeding new matter work but stays in
  history; matters already bound to it keep their pinned version.

Every write re-checks the maintainer role from the repository context, applies
the domain transition, and audits a *content governance* event with actor,
target, before/after version references, and correlation id (inv. 8).

## 6. The template-vs-run split

This service resolves the split the frontend `Workflow` type only hints at. The
**definition** — the `Workflow` (or `FormTemplate`, or `QuestionSet`) with its
`approvalState`, `version`, and `ownerId` — lives **here**. task-service takes an
`approved` definition and runs an **instance** (the step runs, decisions, and
overrides against a specific matter). Governance owns "what the correct wording
and steps are"; task-service owns "what happened in this matter".

```text
content-governance-service          task-service
──────────────────────────          ────────────
Workflow (approvalState=approved) ──▶ StepRun instance in matter M
FormTemplate (approved, locked)   ──▶ Draft bound to that template version
```

A per-matter run may consume an `approved` definition only. It cannot pull a
`draft`, and a mid-matter `retire` does not yank the version a running matter
already pinned.

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Approved wording changes only via a new approved version (§5.3.6) | `approved` definitions are immutable; edits create a new `draft` version; approval never mutates in place |
| Locked wording cannot be altered (§9.2 release blocker) | `locked-prescribed` blocks are fixed at approval; changing them requires a new approved template version |
| Only a maintainer moves content through states | Role re-checked from context on every write; `draft→approved→retired` is maintainer-gated |
| Per-matter services consume `approved` only | Reads for matter work filter to `approvalState = approved`; draft/retired never feed a matter |
| Retire preserves history, does not yank pinned versions | Retired rows retained; a running matter keeps its bound version (mirrors inv. 7) |
| Versioned rule definitions carry authority metadata (Phase 5) | Approval records version, effective date, and authority metadata |
| Every governance mutation audited (inv. 8, §5.2) | `AuditPort.record` a content-governance event on create/version/approve/retire |
| Controlled content separate from matter data (§5.2) | Definitions live in their own tier; the service touches no matter storage |

## 8. Failure modes to handle explicitly

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

## 9. Test list

- **Unit:** `draft→approved→retired` transitions; editing an `approved`
  definition creates a new draft rather than mutating; `locked-prescribed`
  blocks fixed after approval; illegal-transition rejection; maintainer gate.
- **Contract:** `FormTemplate`, `Workflow`, `Question`, and `QuestionSet`
  schemas against the frontend types; the create/version/approve/retire request
  and response shapes.
- **Integration:** approve then consume — a per-matter read returns only the
  `approved` version; retire does not affect a matter pinned to a prior version;
  audit event written on every transition.
- **Security:** non-maintainer cannot create, approve, or retire; no altered
  locked wording escapes; cross-role escalation denied; no secret or raw client
  data in logs.

## 10. Open decisions

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
