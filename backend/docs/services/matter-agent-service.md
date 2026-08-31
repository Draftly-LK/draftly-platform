# Matter Master Agent — End-to-End Vertical Slice

## Summary

Build a new matter_agent_service that gives every matter exactly one durable chat session.
It orchestrates existing Draftly services through typed, server-side tools while preserving
tenant isolation, lawyer verification, approvals, audit history, and deterministic gates.

- Matter chat: one session per (user_id, matter_id).
- Global research conversations remain separate.
- Gemini Flash handles orchestration through a provider-neutral AgentModelPort.
- Draftly invokes internal application ports; the model receives no database or MCP access.
- Chat content lives only in the matter’s hosted Supermemory container.
- Neon stores session metadata, message indexes/hashes, jobs, tool calls, pending actions,
  audit references, and deletion receipts—but not message content.

- Legal retrieval is deferred. Until its engine is connected, the agent must abstain from
  legal conclusions requiring RTA or Notaries Ordinance authority.

## Architecture and Contracts

### Service and persistence

Add matter_agent_service and register it in the service catalogue, events registry,
bootstrap wiring, billing entitlements, API docs, and service-definition tests.

Persist:

- agent_sessions: unique constraint on user_id + matter_id, model/prompt versions, state and
  timestamps.

- agent_message_index: ordered message metadata, provider document ID, role, content hash
  and timestamps; no content.

- agent_jobs: queued/running/succeeded/failed state and correlation IDs.
- agent_tool_calls: tool name, safe input summary, result references, status and timing.
- agent_pending_actions: typed arguments, target versions, expiry, confirmation state and
  actor.

- agent_stream_events: short-lived resumable SSE events, purged after 24 hours.
- external_memory_scopes: provider, opaque container tag, approval state and deletion
  receipt.

Use the existing PostgreSQL outbox and worker. Do not introduce another queue or agent
framework.

### Provider ports

Define:

- AgentModelPort: run a stateless tool-calling turn.
- MemoryPort: ingest minimal memory, retrieve relevant context and destroy a scope.
- ConversationPort: append and retrieve ordered chat messages.
- AgentToolPort: common typed contract for allowlisted internal tools.

Implement:

- GeminiInteractionsAdapter using direct Google GenAI function calling with store=false;
  model is configured through MATTER_AGENT_MODEL, initially the current stable Gemini Flash
  tier.

- SupermemoryMemoryAdapter and SupermemoryConversationAdapter.
- Deterministic fake adapters for automated tests.

Gemini function calls are proposals; Draftly validates and executes them server-side. This
follows Google’s documented function-calling model. Gemini function calling

### Supermemory isolation

- Derive a non-guessable container tag using an HMAC of the current tenant/user ID, matter
  ID and namespace version.

- Use exactly one container per tenant and matter.
- Never expose raw user IDs, matter IDs, database credentials or storage paths.
- Never send original documents, OCR JSON/text, provider payloads, tool arguments containing
  unnecessary personal data, or database rows.

- Chat messages are sent because Supermemory is the selected transcript store; tool results
  are reduced to safe summaries and Draftly resource references.

- Provider access is disabled for real client matters unless residency, retention, deletion,
  DPA and security approval is explicitly enabled.

- Approved matter destruction enqueues container deletion, verifies the provider response,
  records counts and a receipt, and retries failures. Destruction remains incomplete while
  external erasure is pending. Supermemory provides a container deletion operation covering
  its documents and memories. Supermemory container deletion

### Public API

Add:

- GET /api/v1/matters/{matterId}/agent — return or lazily provision the matter’s single
  session.

- GET /api/v1/matters/{matterId}/agent/messages?limit=&cursor= — ordered transcript through
  ConversationPort.

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

### Automatic read tools

- Matter summary and routing state.
- Source-file and document-processing status.
- Full extraction data, candidate fields, OCR pages and confidence data on demand.
- Verified facts, clearly separated from unverified candidates.
- Checklist, checks, issues and obligations.
- Working forms/drafts and their preflight state.
- Matter memory search.

OCR and extraction results are untrusted tool data. They may be sent transiently to Gemini
when explicitly needed, with size limits, but never written to Supermemory or logs.

### Automatic write tools

Allow only:

- Run deterministic checks.
- Generate a working draft from an approved template and verified facts.
- Save a non-authoritative working note.
- Update checklist administration:
  - assignment;
  - due date;
  - collection state to REQUESTED, provided this does not downgrade received evidence.

Create a dedicated checklist administration command so the agent cannot reach applicability,
satisfaction, waiver, currency, consistency, digital-review or evidence-acceptance fields
through the broader decision method.

All automatic writes execute as the authenticated actor, require that actor’s capability,
and record the initiating model, prompt version and tool-call ID.

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
- User roles, billing or provider-approval settings.

For these, chat links to the existing controlled screen.

### Agent loop and honesty

- Maximum eight tool calls per turn and a 120-second turn budget.
- Load the latest 20 messages plus up to eight relevant memory results.
- Validate every function argument with strict Pydantic schemas; do not use free-form
  additionalProperties.

- Treat document text and memory as untrusted data, never instructions.
- Final responses distinguish verified facts, AI candidates, operational suggestions and
  abstentions.

- Legal answers require citation-bearing output from the future legal-retrieval tool. Until
  that tool exists, return a fixed legal_research_unavailable abstention rather than
  answering from model knowledge.

- The later retrieval engine plugs into a reserved LegalResearchToolPort; no retrieval
  implementation is included in this release.

## Frontend and Operations

Add /matters/[id]/assistant and a Matter Assistant navigation tab.

The screen contains:

- One fixed matter thread—no “new conversation” control.
- Streaming messages and reconnect state.
- Visible tool-call status and resulting Draftly resource links.
- Inline action cards with impact, evidence, confirm and reject controls.
- Clear labels for verified facts, candidates, memory and agent suggestions.
- Warnings when Gemini or Supermemory real-data approval is disabled.
- Existing document, facts, checklist and draft screens remain the authoritative review
  surfaces.

- Global /assistant remains a separate research-conversation experience; its real legal
  retrieval remains deferred.

Configuration includes:

- MATTER_AGENT_ENABLED
- MATTER_AGENT_MODEL
- MATTER_AGENT_MAX_TOOL_CALLS=8
- MATTER_AGENT_TURN_TIMEOUT_SECONDS=120
- SUPERMEMORY_API_KEY
- SUPERMEMORY_BASE_URL
- SUPERMEMORY_CONTAINER_HMAC_KEY
- SUPERMEMORY_REAL_DATA_APPROVED=false
- provider timeouts and result-size limits

Logs and metrics contain only IDs, durations, state, tool name, token counts and failure
classes—never prompts, OCR, candidate values or personal data.

## Tests and Rollout

Automated tests use fake Gemini and memory providers.

Cover:

- Concurrent access still creates one session per matter.
- Cross-tenant and cross-matter access returns 404.
- Container tags are isolated and reveal no internal IDs.
- Full extraction tools never persist their payload into memory, stream records or logs.
- Prompt injection inside OCR, candidates or memory cannot widen scope or invoke forbidden
  tools.

- Confirmation is capability-gated, idempotent and rejects stale versions.
- Final approvals, overrides, exports and attestations remain unreachable to the agent.
- Provider failures produce typed 503 responses without partially executing tools.
- Retry after an external-write/database failure does not duplicate messages.
- Approved destruction deletes the external container, records the receipt and retries
  failures.

- Without legal retrieval, legal questions always abstain.
- Frontend keyboard, screen-reader, streaming reconnect and bilingual tests.
- Existing backend tests, ruff, formatting, mypy, frontend tests, type-check, lint and build
  remain green.

Real Gemini and Supermemory integration suites run only behind explicit environment flags
with synthetic data. Roll out behind MATTER_AGENT_ENABLED: fake/local, synthetic staging,
provider-security approval, then a limited pilot. Real-client production remains blocked
until the Supermemory and Gemini data-processing gates are approved.
