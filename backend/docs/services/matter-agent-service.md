# matter_agent_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `security-model.md`,
`api-conventions.md`, `events.md`, `jobs-and-workers.md`, `memory-service.md`,
`research-service.md`, `task-service.md`, `verification-service.md`, and
`document-service.md`. This service is the **matter master agent** — one durable
chat session per matter, orchestrating existing Draftly services through typed,
server-side tools.

| Field | Value |
| --- | --- |
| Owner | Draftly Team |
| Plan phase | V1, after the V0 phases in `backend-implementation-plan-v0.md` |
| Status level | L0 designed |
| Last reviewed | 2026-08-31 |

## What it owns

The matter chat session and its authoritative transcript, the agent turn loop, the
server-side tool executor and its allowlist, inline pending actions and their confirmation
lifecycle, and non-authoritative matter working notes.

## What it does not own

| Concern | Owning service |
| --- | --- |
| Semantic memory, Supermemory scopes and their lifecycle | `memory_service` |
| Global research conversations and legal retrieval | `research_service` |
| Capabilities, roles, practising status | `auth_service` |
| Matter ownership and lifecycle | `matter_service` |
| Verified facts and candidate approval | `verification_service` |
| Checklist state and requirement review | `task_service` |
| Deterministic checks and findings | `check_service` |
| Drafts, approval, export, attestation | `draft_service`, `approval_service`, `export_service`, `notarial_register_service` |
| The audit log itself | `audit_service` |
| Holds, destruction and tombstones | `retention_service` |

## Invariants

| # | Invariant | Test |
| --- | --- | --- |
| 1 | Every row it owns carries the tenant key and is filtered on it before anything else | `conformance/test_tenancy.py` |
| 2 | Matter isolation: a foreign matter is 404, indistinguishable from absent | `conformance/test_tenancy.py` |
| 3 | Every mutating application method produces exactly one audit event | `conformance/test_audit_coverage.py` |
| 4 | Metered work reserves before and consumes after, and fails closed without entitlement | `conformance/test_metering.py` |
| 5 | Neon is the only source of chat history; no code path renders history from a provider | `agent/test_history_source.py` |
| 6 | Effective permission is user ∩ allowlist ∩ matter ownership, never a union | `agent/test_effective_permission.py` |
| 7 | A capability outside the allowlist is unreachable even for a user who holds it | `agent/test_allowlist_closed.py` |
| 8 | The agent never verifies a fact, approves, exports, attests, waives, or changes holds, roles, billing or provider config | `agent/test_human_only_actions.py` |
| 9 | Memory is never evidence and no memory value reaches a draft | `agent/test_memory_not_authority.py` |
| 10 | Supermemory failure degrades recall only; chat, history and tools continue | `agent/test_provider_degradation.py` |
| 11 | A matter's Supermemory scope is rebuildable from Neon and rebuild is idempotent | `memory/test_scope_rebuild.py` |
| 12 | Without legal retrieval, a legal question always abstains | `agent/test_legal_abstention.py` |
| 13 | RECEIVED is reachable, SATISFIED and evidence acceptance are not | `agent/test_receipt_not_satisfaction.py` |
| 14 | A candidate never overwrites a verified structured field | `agent/test_candidate_conflict.py` |
| 15 | Every allowlisted capability is audited on both the executed and the denied path | `agent/test_audit_all_capabilities.py` |

## Summary

Build a new matter_agent_service that gives every matter exactly one durable chat session.
Users may start a clean conversation segment inside that session; closing a segment never
deletes or rewrites its messages, so the complete transcript remains auditable.
It orchestrates existing Draftly services through typed, server-side tools while preserving
tenant isolation, lawyer verification, approvals, audit history, and deterministic gates.

- Matter chat: one session per (user_id, matter_id).
- Global research conversations remain separate.
- Gemini Flash handles orchestration through a provider-neutral AgentModelPort.
- Draftly invokes internal application ports; the model receives no database or MCP access.
- Neon holds the complete authoritative chat transcript, together with session metadata,
  jobs, tool calls, confirmations, pending actions, audit references and deletion receipts.

- Supermemory is an optional, non-authoritative semantic-memory layer behind MemoryPort. It
  never serves visible chat history and never becomes authoritative.

- GCS stays limited to documents, OCR and existing derivatives. No chat transcript is
  written to GCS in V1.

- Legal retrieval is deferred. Until its engine is connected, the agent must abstain from
  legal conclusions requiring RTA or Notaries Ordinance authority.

## Architecture and Contracts

### Service and persistence

Add matter_agent_service and register it in the service catalogue, events registry,
bootstrap wiring, billing entitlements, API docs, and service-definition tests.

Persist:

- agent_sessions: unique constraint on user_id + matter_id, model/prompt versions, state,
  active conversation segment and timestamps.

- agent_conversations: durable segments beneath the session. Starting a new conversation
  closes the prior segment and creates a new active segment without deleting history.

- agent_messages: the authoritative transcript. Session, conversation and matter keys, a monotonic
  per-session sequence number, role, full message content, created-at timestamp, content
  hash, the originating agent job, and nullable references to the tool call or confirmation
  that produced it, plus structured citations to authoritative Draftly records. Unique on
  (session_id, sequence). Chat content lives here and nowhere
  else.

- agent_jobs: queued/running/succeeded/failed state and correlation IDs.
- agent_tool_calls: tool name, capability checked, safe input summary, result references,
  outcome (executed, denied, failed) with its reason code, initiating model and prompt
  version, status and timing.
- agent_pending_actions: typed arguments, target versions, expiry, confirmation state and
  actor.

- agent_stream_events: short-lived resumable SSE events, purged after 24 hours.
- matter_notes: non-authoritative working notes, the target of `note.create`.

Two further tables are needed but are **owned by `memory_service`, not by this service**,
because memory is initialised on matter creation rather than on agent session creation and
serves every consumer of matter context:

- external_memory_scopes: provider, opaque container tag, enabled/approval state, scope
  state (PENDING, INITIALIZING, READY, STALE, FAILED), last successful sync sequence,
  rebuild state and deletion receipt. A scope is optional; a matter with no scope is fully
  functional.

- external_memory_entries: scope, memory kind, Neon resource ID, resource version, provider
  document ID, sync state and timestamps. This is what makes supersession and rebuild
  possible — without a local index of what was ingested, a correction cannot find the stale
  memory and a rebuild cannot tell converged from duplicated. It holds references and
  versions, never content.

Every message row and its outbox event commit in a single database transaction, so a
transcript write is never observable without its downstream event and a rollback leaves
neither. Use the existing PostgreSQL outbox and worker. Do not introduce another queue or
agent framework.

Supermemory is updated asynchronously by the existing outbox worker, never on the request
path. A matter’s Supermemory scope is derived state and must be rebuildable from Neon by
replaying agent_messages in sequence order.

### Provider ports

Define:

- AgentModelPort: run a stateless tool-calling turn.
- MemoryPort: ingest minimal memory, retrieve relevant context, initialise, rebuild and
  destroy a scope. Defined and implemented by `memory_service`; this service is a caller
  only. Optional — every caller tolerates a null implementation.

- ConversationPort: append and retrieve ordered chat messages. Backed by Neon, always.
- AgentToolPort: common typed contract for allowlisted internal tools.

Implement:

- GeminiInteractionsAdapter using direct Google GenAI function calling with store=false;
  model is configured through MATTER_AGENT_MODEL, initially the current stable Gemini Flash
  tier.

- NeonConversationAdapter implementing ConversationPort over agent_messages. This is the
  only ConversationPort implementation; there is no provider-backed conversation adapter.

- SupermemoryMemoryAdapter implementing MemoryPort. Optional, disabled by default, and
  selected only when SUPERMEMORY_ENABLED is set.

- A null MemoryPort implementation used whenever Supermemory is disabled or unapproved.
- Deterministic fake adapters for automated tests.

Gemini function calls are proposals; Draftly validates and executes them server-side. This
follows Google’s documented function-calling model. Gemini function calling

### Events and jobs

Registered in `events.md` under a new `agent` aggregate. Payloads are identifiers, counts
and closed enums only — never message text, tool arguments or prompt content.

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

`memory_service` gains `memory.scope-initialised`, `memory.scope-degraded` and
`memory.scope-destroyed` on the existing `memory` aggregate.

Job types, registered in `jobs-and-workers.md` §5:

| Job | Trigger | Lease | Notes |
| --- | --- | --- | --- |
| `agent.run-turn` | `POST …/agent/messages` | 180s | 120s turn budget plus margin; emits resumable stream events |
| `memory.initialize` | `matter.created` | 600s | Container, profile, checklist, facts, document summaries, then READY |
| `memory.sync` | The six update triggers | 120s | Payload carries identifiers only; the worker re-reads content from Neon |
| `memory.rebuild` | Operator, or a STALE scope | 900s | Idempotent; converges rather than duplicating |

Scheduled, registered in §6:

| Schedule | Job | Purpose |
| --- | --- | --- |
| hourly | `agent.purge-stream-events` | Delete resumable stream events older than 24 hours |
| daily 03:15 Asia/Colombo | `memory.reconcile-scopes` | Repair STALE scopes; delete unmapped provider containers older than 24h after a fail-closed hold check |

### Supermemory isolation

Supermemory holds derived semantic memory only. Four rules hold regardless of how much
content it receives: Neon stays authoritative, the scope stays rebuildable from Neon,
memory never verifies a fact or authorizes an action, and matter deletion destroys the
container.

- Derive a non-guessable container tag using an HMAC of the current tenant/user ID, matter
  ID and namespace version.

- Use exactly one container per tenant and matter.
- Never expose raw user IDs, matter IDs, database credentials or storage paths.
- V1 sends the complete chat and the relevant matter context unredacted. This is an
  **approved external-data-transfer boundary to a named sub-processor**, not an exemption
  from any privacy control, and it is why real-client use stays behind provider approval and
  a signed DPA (`memory-service.md` §11.2).

- The privacy denylist is untouched. Logs, error bodies, event payloads, audit payloads,
  notification bodies and metric labels still carry no matter content
  (`service-definition-of-done.md` §4.7). The boundary is one hop wide — the provider
  request body — and nothing else in the system relaxes.

- Scope is content, not bulk. Send messages, verified facts, decisions, document summaries
  and workflow history. Never send raw PDF bytes, full OCR payloads, provider response
  payloads, database rows, or storage paths. The agent fetches current raw data through its
  Draftly tools when it needs it, so memory holds context rather than large stale
  duplicates.

- Every ingested memory carries its Neon resource ID and resource version, so a correction
  supersedes the stale memory instead of sitting beside it.

- The outbox payload carries identifiers only. The worker re-reads content from Neon before
  ingesting, because an event payload may never contain private matter content
  (events.md §2). The provider request body is the only place content travels.

- Provider access is disabled for real client matters unless residency, retention, deletion,
  DPA and security approval is explicitly enabled. Because Supermemory is optional, an
  unapproved or disabled provider degrades semantic recall and blocks nothing else.

- Approved matter destruction enqueues container deletion, verifies the provider response,
  records counts and a receipt, and retries failures. Destruction remains incomplete while
  external erasure is pending. Supermemory provides a container deletion operation covering
  its documents and memories. Supermemory container deletion

### Matter memory initialization

When a matter is created, Neon commits first and memory is built behind it:

```text
Create matter in Neon
→ enqueue memory.initialize
→ create isolated Supermemory container
→ ingest matter profile
→ ingest checklist and current state
→ ingest verified facts and candidate summaries
→ ingest document summaries
→ mark memory READY
```

- The whole pipeline is asynchronous. Supermemory failure never blocks or rolls back matter
  creation, and a matter whose memory never reaches READY is fully usable.

- The scope state machine is PENDING → INITIALIZING → READY, with STALE and FAILED as
  recoverable states. The agent reads memory only from a READY scope; any other state means
  it runs on recent messages and its Draftly tools alone.

- Initialization is idempotent and resumable. Re-running it against a partially built scope
  converges rather than duplicating, which makes it the same code path as rebuild.

After initialization, memory is updated when a chat message is created, a document is
processed, a field is verified or corrected, the checklist changes, a draft or working note
is created, or an issue is resolved. Each subscribes to that aggregate's already-registered
event; the agent's own chat event is the one new registration
(events.md §1 — a service doc may not invent an event name).

A verification or correction supersedes every memory carrying the same Neon resource ID at a
lower version. Superseded memory is replaced, not left to compete with the current value.

### Retention, holds and destruction

- The Neon chat records are the primary target of both legal hold and destruction. A hold on
  the matter blocks deletion of agent_sessions, agent_messages, agent_tool_calls and
  agent_pending_actions, and is re-checked at approval and again at execution
  (retention-service.md).

- Approved matter destruction removes the Neon chat records and, when a scope exists,
  destroys the Supermemory scope. A tombstone is written before any bytes are removed.

- Destruction is incomplete while either side is pending. A Supermemory deletion failure
  leaves the scope in a retrying state and the tombstone open; it never silently completes.

- A matter with no Supermemory scope destroys cleanly through the Neon path alone.

### Public API

Add:

- GET /api/v1/matters/{matterId}/agent — return or lazily provision the matter’s single
  session.

- GET /api/v1/matters/{matterId}/agent/messages?limit=&cursor= — the authoritative
  transcript, read from Neon through ConversationPort. Cursor pagination per
  api-conventions.md §2: opaque signed cursor encoding the sequence number and message ID,
  limit capped at 100, page envelope returned. Never served from Supermemory.

- POST /api/v1/matters/{matterId}/agent/messages — require Idempotency-Key; append the
  message and return an agent job.

- GET /api/v1/agent-jobs/{jobId} — normal job status.
- GET /api/v1/agent-jobs/{jobId}/events — resumable SSE using Last-Event-ID.
- POST /api/v1/matters/{matterId}/agent/actions/{actionId}/confirm — execute an inline
  protected action after reauthorization and version checks.

- POST /api/v1/matters/{matterId}/agent/actions/{actionId}/reject — preserve the rejected
  proposal and audit it.

Every route derives tenancy from RequestContext, repeats matter ownership checks and returns
404 for foreign resources.

## Tool and Execution Policy

### Effective permission

The agent has **full matter administration, never platform administration**, and it has no
identity of its own. Every tool call executes as the authenticated user, and the permission
that applies is an intersection:

```text
effective = authenticated user's capabilities
          ∩ agent tool allowlist
          ∩ matter ownership
```

- It is an intersection in every direction. The agent can never exceed the user who is
  typing, a user can never reach a capability the allowlist omits by asking the agent, and
  neither reaches a matter the user does not own.

- The allowlist is a positive server-side registry, not a refusal in the prompt. A
  capability absent from it is unreachable even when the user holds it, so a prompt
  injection reaching for a prohibited action fails at the executor rather than at the
  model's discretion.

- A reviewer using the agent gets a reviewer's powers. The agent is not an escalation path.
- Matter ownership is re-derived from RequestContext on every call, never carried over from
  the turn that proposed the action.

### Capability catalogue additions

Six capabilities are added to security-model.md §3.1 so the automatic write tools have real
keys rather than prose. Each is matter-scoped and none is territorial, so none joins the
require_practising_notary set in §3.3.

| Capability | Guards | Owning service |
| --- | --- | --- |
| `check.run` | Running deterministic checks on a matter | `check_service` |
| `note.create` | Saving a non-authoritative working note | `matter_agent_service` |
| `document.propose-link` | Creating an unverified document-to-parcel or document-to-requirement link | `document_service` |
| `checklist.record-receipt` | Recording that a document was physically received | `task_service` |
| `checklist.suggest-item` | Creating an ad-hoc AI_SUGGESTED checklist item | `task_service` |
| `candidate.create` | Creating an unverified structured-field candidate | `verification_service` |
| `candidate.update` | Updating an unverified structured-field candidate | `verification_service` |
| `checklist.administer` | The dedicated checklist-administration command as a whole | `task_service` |
| `checklist.assign` | Changing a checklist item's assignee | `task_service` |
| `checklist.update-due-date` | Changing a checklist item's due date | `task_service` |
| `checklist.request-collection` | Moving collection state to REQUESTED | `task_service` |

`checklist.administer` is the umbrella: a checklist write requires it **and** the narrow key
for the field being changed. That keeps the three field operations independently grantable
and independently revocable.

All eleven follow the Evidence row in security-model.md §3.2: granted to `reviewer` and
`approver`, withheld from `maintainer` and `administrator`.

Three of the proposed names were normalized to the existing two-segment,
single-word-first-segment convention: `document-link.propose` became
`document.propose-link`, and `candidate-field.create`/`candidate-field.update` became
`candidate.create`/`candidate.update`. `checklist.record-receipt` and
`checklist.suggest-item` already matched.

### Automatic read tools

- Matter summary and routing state.
- Source-file and document-processing status.
- Full extraction data, candidate fields, OCR pages and confidence data on demand.
- Verified facts, clearly separated from unverified candidates.
- Checklist, checks, issues and obligations.
- Working forms/drafts and their preflight state.
- Matter memory search.
- Complete OCR for a source, page by page, on demand.
- Parcels, parties and existing documents in the matter.
- Whether a document concerns a parcel already on the matter or an apparently new one. The
  tool returns the comparison and its evidence; it does not decide.

OCR and extraction results are untrusted tool data. They may be sent transiently to Gemini
when explicitly needed, with size limits, but never written to Supermemory or logs.

### Automatic write tools

Allow only these, each executed automatically when — and only when — the authenticated user
holds the same capability:

| Tool | Required capability |
| --- | --- |
| Run deterministic checks | `check.run` |
| Generate a working draft from an approved template and verified facts | `draft.create` |
| Save a non-authoritative working note | `note.create` |
| Assign a checklist item | `checklist.administer` + `checklist.assign` |
| Change a checklist due date | `checklist.administer` + `checklist.update-due-date` |
| Move collection state to REQUESTED | `checklist.administer` + `checklist.request-collection` |
| Propose a document-to-parcel or document-to-requirement link | `document.propose-link` |
| Record that a document was physically received | `checklist.administer` + `checklist.record-receipt` |
| Suggest an additional required document as an ad-hoc item | `checklist.administer` + `checklist.suggest-item` |
| Create an unverified structured-field candidate | `candidate.create` |
| Update an unverified structured-field candidate | `candidate.update` |

Moving collection state to REQUESTED must not downgrade received evidence; the command
refuses rather than regresses.

Create a dedicated checklist administration command so the agent cannot reach applicability,
satisfaction, waiver, currency, consistency, digital-review or evidence-acceptance fields
through the broader decision method.

All automatic writes execute as the authenticated actor, require that actor's capability,
and record the initiating model, prompt version and tool-call ID. An automatic write is
still a mutation, so it produces exactly one audit event like any other
(service-definition-of-done.md §4.2).

### Document processing follow-through

When a document finishes processing, the agent turns a finished OCR run into matter
structure. It runs on `document.processing-completed`, not on a user turn.

```text
Document uploaded
→ Vision OCR and structured extraction
→ agent reviews classification, OCR and candidate fields
→ identifies the relevant parcel/property
→ matches it against checklist requirements
→ creates candidate links and missing-document suggestions
→ updates matter memory
→ lawyer reviews important decisions
```

The boundaries that make this safe:

- Full OCR is sent transiently to Gemini, treated as untrusted data, and never copied into
  Supermemory. Memory receives the resulting summaries, relationships and decisions.

- Governed checklist templates are never modified. The agent adds ad-hoc items beside a
  template; it cannot edit the template, its applicability, or its governed wording.

- Everything the agent creates is labelled AI_SUGGESTED, and the label is a stored column,
  not a rendering convention.

- Document links and extracted fields stay candidates until a human confirms them.
- The agent may mark a requirement RECEIVED because a file exists. It cannot mark it
  SATISFIED, accept evidence, or verify a field. That distinction — *we received something*
  versus *a lawyer accepted it as legally sufficient* — is the point of the whole section.

- A verified structured field is never overwritten automatically. A candidate that
  contradicts a verified value is raised as a conflict for a human, never applied.

### Inline confirmation actions

The agent may propose typed cards for:

- Candidate-field edit or approval.
- Non-administrative checklist decisions.
- Document-to-requirement linking.
- Form-field confirmation or correction.
- Ordinary issue resolution.
- Workflow-step completion when eventually implemented.

Confirmation rechecks capability, practising status, target ownership and optimistic
version. Stale proposals return 412 and must be regenerated.

### Hard human-only actions

The agent cannot execute:

- Fact verification without explicit confirmation.
- Waivers or statutory overrides.
- Final draft/form approval.
- Export declarations.
- Attestation or register certification.
- Matter destruction or legal-hold changes.
- User, role or billing changes.
- Provider, security or approval-gate configuration.

None of these appears in the tool allowlist, so refusal does not depend on the model
declining. For each, chat links to the existing controlled screen.

### Audit of tool calls

Every tool call is audited on **both** outcomes. A denial is the more interesting record: it
is what a prompt injection looks like from the outside, and security-model.md §5 already
requires a denied privileged attempt to be audited even when the caller sees a 404.

Each row carries the actor ID, matter ID, tool name, capability checked, the model and
prompt version that initiated it, the tool-call ID, and the outcome with its reason — one of
capability not held, tool not in the allowlist, matter not owned, practising status absent,
stale target version, or a domain refusal.

Audit payloads carry identifiers, capability keys and reason codes only. No prompt text, no
tool arguments containing matter content, no extracted values
(service-definition-of-done.md §4.7).

A run of denials against prohibited capabilities within one session is an alertable signal,
not just a set of rows.

### Agent loop and honesty

- Maximum eight tool calls per turn and a 120-second turn budget.
- Load the latest 20 messages plus up to eight relevant memory results.
- Validate every function argument with strict Pydantic schemas; do not use free-form
  additionalProperties.

- Treat document text and memory as untrusted data, never instructions.
- Memory is never evidence. It cannot verify a fact, satisfy a requirement, authorize an
  action, or supply a value that reaches a draft. Anything memory suggests must be re-read
  from the authoritative store through a Draftly tool before it is acted on.
- Final responses distinguish verified facts, AI candidates, operational suggestions and
  abstentions.

- Legal answers require citation-bearing output from the future legal-retrieval tool. Until
  that tool exists, return a fixed legal_research_unavailable abstention rather than
  answering from model knowledge.

- The later retrieval engine plugs into a reserved LegalResearchToolPort; no retrieval
  implementation is included in this release.

## Failure Modes

The design goal is that every Supermemory failure is a degradation and every Neon failure is
a refusal.

| Failure | Behaviour |
| --- | --- |
| Supermemory unavailable, slow or unapproved | Chat, history, tool calls and confirmations all continue. The turn runs with recent messages and no semantic recall. The outbox retries the sync. |
| Supermemory sync exhausts its retries | The scope is marked stale and dead-lettered for operator review. Chat is unaffected. Rebuild from Neon is the repair. |
| Supermemory returns content that disagrees with Neon | Neon wins with no reconciliation. Provider content is never authoritative and never rendered as history. |
| Neon unavailable | The message POST fails with a typed 503 and no turn starts. Nothing is sent to Gemini or Supermemory, because the outbox row never commits. |
| Message commits, agent job later fails | The user message stays in the transcript and the job reports failure. A failed job never deletes or rewrites a message. |
| Gemini unavailable or over budget | Typed 503, no partial tool execution, no assistant message appended. |
| Tool call fails mid-turn | The tool call row records the failure, the turn ends with an honest partial answer, and no pending action is created. |
| Duplicate POST with the same Idempotency-Key | The stored response replays. Exactly one message row and one outbox event exist. |
| Scope rebuild interrupted | Rebuild is idempotent and resumable from the last synced sequence; a partial rebuild never surfaces as history. |
| memory.initialize fails at any step | The matter is unaffected and fully usable. The scope holds at FAILED, the job retries with backoff, and the agent runs without semantic recall. |
| Scope not READY when a turn starts | The turn proceeds on recent messages and Draftly tools. Absence of memory is never an error shown to the user. |
| Supersession write fails after a correction | The scope is marked STALE. A STALE scope is not read, so a stale memory can never outlive the correction it contradicts. |
| Container creation succeeds, Neon scope row fails | The orphan is reconciled by the same sweep that reconciles storage: an unmapped container older than 24h is deleted after a fail-closed hold check. |

## Frontend and Operations

Add /matters/[id]/assistant and a Matter Assistant navigation tab.

The screen contains:

- One durable matter session with a visible active conversation. “New conversation” closes
  the visible segment and preserves the prior transcript in audit history.
- Chronological compact messages, a sticky composer, and a live matter-context rail backed
  by the existing document, fact, checklist, issue, and draft APIs.
- Claim-level citations resolved only from record IDs returned by executed tools; citation
  links open the authoritative review surface.
- Streaming messages and reconnect state.
- Visible tool-call status and resulting Draftly resource links.
- Inline action cards with impact, evidence, confirm and reject controls.
- Clear labels for verified facts, candidates, memory and agent suggestions.
- A warning when Gemini real-data approval is disabled, because that blocks the turn.
- A quiet, non-blocking notice when Supermemory is disabled or degraded: recall is reduced,
  history and tools are unaffected. It is never presented as a chat failure.
- Existing document, facts, checklist and draft screens remain the authoritative review
  surfaces.

- Global /assistant remains a separate research-conversation experience; its real legal
  retrieval remains deferred.

Configuration includes:

- MATTER_AGENT_ENABLED
- MATTER_AGENT_MODEL=gemini-3.5-flash-lite (default; deployment-overridable)
- MATTER_AGENT_MAX_TOOL_CALLS=8
- MATTER_AGENT_TURN_TIMEOUT_SECONDS=120
- SUPERMEMORY_ENABLED=false
- SUPERMEMORY_API_KEY
- SUPERMEMORY_BASE_URL
- SUPERMEMORY_CONTAINER_HMAC_KEY
- SUPERMEMORY_REAL_DATA_APPROVED=false
- provider timeouts and result-size limits

Logs and metrics contain only IDs, durations, state, tool name, token counts and failure
classes—never prompts, OCR, candidate values or personal data.

## Implementation status

Backend gates as of 2026-08-31: 999 tests pass (6 skipped), ruff, ruff format,
mypy strict on 307 files, single Alembic head, `uv lock --check` clean.

Nine endpoints are live:

```text
GET  /api/v1/matters/{id}/agent
GET  /api/v1/matters/{id}/agent/messages
POST /api/v1/matters/{id}/agent/messages
GET  /api/v1/matters/{id}/agent/conversations
POST /api/v1/matters/{id}/agent/conversations
GET  /api/v1/agent-jobs/{jobId}
GET  /api/v1/agent-jobs/{jobId}/events          resumable SSE, polling retained
POST /api/v1/matters/{id}/agent/actions/{id}/confirm
POST /api/v1/matters/{id}/agent/actions/{id}/reject
```

### Tools

Eighteen of twenty-seven are implemented against the owning application
service. No tool reaches a repository or the database directly.

| Implemented | Service |
| --- | --- |
| `read_matter_summary`, `list_matter_inventory` | `matter_service` |
| `read_checklist_state` | `checklist_service` |
| `read_document_status`, `read_document_extraction`, `read_document_ocr_pages` | `document_service`, `DocumentReviewService` |
| `read_verified_facts` | `FactQueryService` |
| `read_draft_preflight`, `generate_working_draft` | `draft_service` |
| `search_matter_memory` | `MemoryPort` |
| `run_checks` | `check_service` |
| `save_working_note` | `matter_agent_service` |
| `assign_checklist_item`, `update_checklist_due_date`, `request_checklist_collection`, `record_document_receipt`, `propose_document_link` | `checklist_service` |
| `update_field_candidate` | `DocumentReviewService` |

Nine are **not** implemented. Each is denied with `tool_not_implemented`,
audited, and carries a stated reason in
`matter_agent.application.tools.OUT_OF_SCOPE`. A test asserts that every
allowlisted tool is either implemented or listed there, so the set cannot drift.

- `compare_parcel_identity` — no parcel aggregate exists in the domain.
- `create_field_candidate` — candidates are created by the extraction pipeline;
  the review service exposes edit and approve, not create.
- `suggest_checklist_item` — items are compiled from governed templates; ad-hoc
  creation is a content-governance change, not an agent capability.
- The six `propose_*` confirmation-card tools — the pending-action lifecycle is
  built and tested, but no tool creates a card yet.

### The RECEIVED / SATISFIED line

`ChecklistService.administer_item` is a new narrow command beside
`decide_satisfaction`. It reaches assignment, due date and collection only.
`guard_administrative_collection` restricts collection to REQUESTED and
RECEIVED and refuses to downgrade evidence that has already arrived, and
resolution is always recomputed from the requirement policy. The agent
therefore has no path to applicability, waiver, digital review, currency,
consistency or satisfaction even holding `checklist.administer`.

### Still outstanding

- **Frontend `/matters/[id]/assistant`** — implemented as a responsive assistant workspace
  with a chronological transcript, persistent composer, live matter context, source
  citations, conversation reset with preserved history, and bilingual copy.
- **Memory lifecycle** — `memory.initialize`, `memory.sync`, `memory.rebuild`
  and `memory.reconcile-scopes` are registered in `jobs-and-workers.md` and in
  `services.yaml`, but not implemented. `NullMemoryPort` is the default, so the
  agent runs correctly without them.
- **`contracts/openapi.v1.json`** is still not committed, and there are no
  contract fixtures. That gap is repo-wide, not specific to this service.
- **Confirmation cards** — the confirm/reject endpoints, version checks and
  audit are complete; nothing proposes a card yet.

## Tests and Rollout

Automated tests use fake Gemini and memory providers.

Cover:

- Concurrent access still creates one session per matter.
- Cross-tenant and cross-matter access returns 404.
- Container tags are isolated and reveal no internal IDs.
- Full extraction tools never persist their payload into memory, stream records or logs.
- The message row and its outbox event commit atomically; a forced rollback leaves neither.
- Chat history is served from Neon and is byte-identical with Supermemory disabled, empty,
  stale, or returning contradictory content.

- Cursor pagination over agent_messages is stable under concurrent appends, caps limit at
  100, and returns the page envelope.

- A Supermemory outage or timeout degrades recall only: sending, history, tool calls and
  confirmations all still succeed.

- A matter’s Supermemory scope rebuilds from Neon alone and is idempotent when the rebuild
  is interrupted and resumed.

- No code path reads Supermemory to render chat history; ConversationPort has exactly one
  implementation and it is Neon-backed.

- Matter creation succeeds and returns while memory.initialize is still running, and
  succeeds unchanged when the provider is unreachable throughout.

- The scope reaches READY only after every initialization step lands; a turn against a
  PENDING, STALE or FAILED scope runs without memory and reports no error.

- Re-running initialization against a partially built scope converges without duplicating.
- A verification or correction supersedes every memory at a lower version for the same Neon
  resource ID, and the superseded entry is no longer retrievable.

- No raw PDF bytes, OCR payload, provider payload or database row is ever sent to the
  provider; the assertion runs against the recorded provider request bodies.

- Every outbox payload for a memory job carries identifiers only and no matter content.
- Memory output cannot verify a fact, satisfy a requirement or authorize an action, and no
  value reaches a draft without passing through the verified tier.
- Prompt injection inside OCR, candidates or memory cannot widen scope or invoke forbidden
  tools.

- Confirmation is capability-gated, idempotent and rejects stale versions.
- Effective permission is an intersection: a user lacking a capability cannot obtain it
  through the agent, and a capability absent from the allowlist is unreachable even for a
  user who holds it.

- A reviewer driving the agent cannot exceed reviewer powers, and no tool path reaches a
  matter the authenticated user does not own.

- Each of the six added capabilities is enforced independently; holding
  `checklist.administer` without the narrow key still refuses.

- Checklist administration cannot reach applicability, satisfaction, waiver, currency,
  consistency, digital-review or evidence-acceptance fields, and cannot downgrade received
  evidence.

- Both successful and denied tool calls are audited with actor, matter, tool, capability,
  model version and reason; audit payloads contain no prompt text or matter content.

- Audit coverage is parameterised over the full allowlist, so every one of the eleven
  capabilities — `check.run`, `note.create`, the four `checklist.*` administration keys,
  `checklist.record-receipt`, `checklist.suggest-item`, `document.propose-link`,
  `candidate.create` and `candidate.update` — is asserted on both the executed and the
  denied path. A capability added to the allowlist without an audit assertion fails the
  build.

- Prompt injection instructing a prohibited action is refused by the executor, not by the
  model, and the refusal is audited.

- The agent can mark a requirement RECEIVED but cannot mark it SATISFIED, accept evidence,
  or verify a field, with or without a matching capability held by the user.

- A candidate that contradicts a verified structured field raises a conflict and never
  overwrites the verified value.

- Every agent-created link, checklist item and candidate carries AI_SUGGESTED in the
  database, and none is treated as confirmed by any downstream gate.

- A governed checklist template is unchanged after a document-processing run that added
  ad-hoc items beside it.

- Full OCR reaches Gemini transiently and never reaches Supermemory; the assertion runs
  against recorded provider request bodies for both providers.
- Final approvals, overrides, exports and attestations remain unreachable to the agent.
- Provider failures produce typed 503 responses without partially executing tools.
- Retry after an external-write/database failure does not duplicate messages.
- Approved destruction removes the Neon chat records, destroys any Supermemory scope,
  records the receipt and retries failures, and writes the tombstone first.

- A legal hold blocks destruction of the Neon chat records and of the Supermemory scope, at
  both approval and execution.

- A matter with no Supermemory scope destroys cleanly and reports complete.

- Without legal retrieval, legal questions always abstain.
- Frontend keyboard, screen-reader, streaming reconnect and bilingual tests.
- Existing backend tests, ruff, formatting, mypy, frontend tests, type-check, lint and build
  remain green.

Real Gemini and Supermemory integration suites run only behind explicit environment flags
with synthetic data. The default automated suite runs with Supermemory disabled, so the
Neon-only path is the one continuously proven. Roll out behind MATTER_AGENT_ENABLED: fake/local, synthetic staging,
provider-security approval, then a limited pilot. Real-client production remains blocked
until the Supermemory and Gemini data-processing gates are approved.
