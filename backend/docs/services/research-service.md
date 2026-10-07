# research-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `document-service.md`,
and `memory-service.md`. This service is the **grounded legal assistant**: a
question about Sri Lankan RTA law goes in, a cited answer or an honest
abstention comes out.

The assistant UI is based mainly on selected components and interaction
patterns from [LibreChat](https://github.com/danny-avila/LibreChat). LibreChat
is MIT-licensed and already implements a mature chat shell, including
conversation history, streaming, branching, message rendering, attachments,
agents, tool-call presentation, search, and resumable streams. Draftly reuses
that shell under the licence terms but keeps legal authority, permissions,
retrieval, memory policy, and audit decisions in Draftly services.

Maps to plan **Phase 6** (grounded research), API row **Research** (§7), and the
trust-boundary row *Legal corpus* (§5.2). It is the flagship the frontend does
not yet have — today the assistant textbox submits into nothing.

## Standalone similar-case search (2026-10-04)

`POST /api/v1/research/cases/search` adds a standalone fact-pattern retrieval
path for the Case law tab. It reuses the existing conveyancing engine through
a versioned private HTTP port: BM25, case-graph expansion and optional dense
embeddings feed RRF, followed by lexical-or-graph corroboration. Dense-only
matches are rejected. This route does not compose answers or alter assistant
conversation retrieval.

Results carry bounded evidence excerpts, source citations, matching signals,
corpus version and coverage. Reader links resolve only for catalogue records;
other hits retain their source link. Parsed cases and extraction confidence do
not acquire lawyer verification or binding weight. Valid empty results and
unavailable retrieval are distinct states.

The path uses `research.enabled` and `research_queries.monthly`. Required
`Idempotency-Key` replay is actor-scoped; quota consumption, replay persistence
and the privacy-safe audit commit together. Failed searches roll back the
reservation. Completed abstentions consume one query. Fact patterns are sent
in POST bodies and omitted from ordinary logs.

This bounded direct search is a synchronous exception to the answer-job design
below, matching the existing raw-search interaction: it has a finite upstream
timeout and no generation or streaming stage. Dense retrieval remains opt-in
under recorded provider approval; its optional-channel status is explicit.
See [the case-library implementation](../../../docs/case-law-library.md).

## Case law in the research chat (2026-10-06)

Research is no longer statutes-only. Each question carries a legal source
scope, separate from the conversation scope (library, matter, step, document):

| `sources` | Searches |
| --- | --- |
| `statutes` (default) | The statutory corpus only, exactly as before |
| `cases` | The conveyancing case corpus only |
| `all` | Both, concurrently |

The frontend shows this as "All sources / Statutes & amendments / Case law",
defaulting to statutes so existing behaviour does not change.

**Retrieval.** Statute retrieval is unchanged (`LegalRetrievalPort`). Case
retrieval calls the bounded `CaseSearchPort` (`HttpCaseSearchAdapter`, private
`/v1/cases/search`) directly, with a limit of five results. It does not go
through `CaseResearchService`: that path meters and audits its own query, and
one research question must cost one research query. Each similar case becomes
evidence from its excerpt only, with the case id, name, citation and source
link. Full judgment text is never sent or shown.

**Grounding.** The composer's existing rule is unchanged: every claim must cite
one or more retrieved authority ids, an id that was not retrieved is dropped,
and a claim left without one is dropped. Statute-only evidence uses the
original statutes-only prompt. When case evidence is present, each case is
labelled `[CASE LAW - UNVERIFIED RESEARCH LEAD]`, and the model is told that
case passages are machine-parsed, possibly incomplete research leads that must
never be presented as verified, binding or settled law.

**Unverified case law.** A case citation is stored and returned with
`authorityKind: "case"` and `verified: false`, whatever the evidence said. The
client lists case citations under a separate "Case law" heading and tags the
claims that rely on them; by product decision (2026-10-07) it shows no
"unverified" wording, so the flag is not surfaced in the UI. Citations record their kind, title, reference and source link
(`research_0003`); earlier citations have none of these and read as statutes.
Each assistant message also returns its claims with the ids each one cites.

**Failure.** With `all`, an unavailable case service degrades to statute-only
evidence (`degradedChannels` includes `case-law`). With `cases`, it ends in an
insufficient-authority answer with `research.insufficient.caseLawUnavailable`.
No evidence from any selected source keeps the existing abstention. The answer
records the corpus versions it searched, joined with `+`.

## 1. What it owns

Answering a question over the **controlled legal corpus** and returning a
`GroundedAnswer` whose every claim traces to a source passage and an authority
status — or returning the `insufficient-authority` branch when the corpus does
not support an answer. It owns the composition of an answer from retrieval
results, the claim-level citation validation, and the abstain decision. It owns
the read path for past answers.

It does **not** run the retrieval algorithm itself — the existing Python engine
in `src/draftly/retrieval` does, behind a port. It does **not** verify
particulars, feed drafts, or promote a machine-derived case-rule to authority.
It produces citations marked with their verification status and hands the
decision to the lawyer.

The research corpus may include case-law text classified for restricted
internal research use, including the current CommonLII-derived collection.
That classification permits retrieval and grounded answer composition; it does
not permit the Library to republish full judgments, report scans, headnotes,
database pages, or bulk downloads. Research output is limited to Draftly-
composed claims, case citations, and bounded evidence passages required for
grounding.

This is a deliberate product boundary, not a conclusion that the acquisition
or use is legally risk-free. The source and access policy remains subject to
written Sri Lankan intellectual-property review and any provider terms.

It also owns research-conversation state: conversations, messages, branches,
answer jobs, visible tool calls, stream cursors, and attachment references.
Authentication remains in `auth-service`; uploaded bytes and document versions
remain in `document-service`; matter memory remains in `memory-service`.

LibreChat does not own or decide:

- legal retrieval and abstention;
- claim-level citation validation;
- authority ranking and verification status;
- legal-corpus versions;
- matter membership or document permissions;
- session-memory retention and reconsolidation;
- audit records; or
- whether a fact can enter a matter record or draft.

LibreChat-native generic RAG, public conversation sharing, arbitrary MCP
servers, agent marketplace content, code execution, and unrestricted web search
are disabled unless a later security and product decision approves them.

## 2. Where it sits

### 2.1 LibreChat UI adoption

Draftly uses LibreChat as the primary implementation reference and code-reuse
source for the assistant experience. It does not deploy the complete LibreChat
application as a second product.

The default V0 approach is:

1. Pin a reviewed LibreChat commit.
2. Copy or adapt only the required MIT-licensed client components into the
   Draftly Next.js frontend.
3. Replace LibreChat data-provider calls with typed Draftly API clients.
4. Apply Draftly design tokens, `next-intl`, accessibility rules, and matter
   navigation.
5. Preserve the LibreChat copyright notice and MIT licence for copied or
   substantially derived code.
6. Track each reused component and its source revision in a third-party notice
   file.

The client cannot be imported unchanged. LibreChat currently uses Vite,
React 18, React Router, and its own data-provider packages. Draftly uses
Next.js 15, React 19, and an existing matter shell. A compatibility spike must
test every selected component before it becomes a production dependency.

Reuse or adapt these interaction areas:

- conversation sidebar, new conversation, history, and search;
- message list, Markdown rendering, code and citation presentation;
- streaming and resumable-stream indicators;
- composer, edit, retry, stop, and attachment controls;
- conversation branching;
- agent identity and allowed-tool display; and
- tool-call status and result disclosure.

Draftly-specific components remain authoritative for:

- matter and step scope;
- claim-to-authority citations;
- source-passage opening and highlighting;
- verified versus unverified authority status;
- insufficient-authority abstention;
- memory source and supersession indicators;
- legal actions such as adding an answer to a matter or creating a check; and
- all approval, role, and audit states.

### 2.2 Service boundary

```text
Draftly assistant UI
(LibreChat-derived components)
          |
          | HTTPS + resumable SSE
          v
GET  /api/assistant/conversations
POST /api/assistant/conversations
PATCH /api/assistant/conversations/{id}           rename
POST /api/assistant/conversations/{id}/archive    hide from the list; records kept
GET  /api/assistant/conversations/{id}/messages
POST /api/assistant/conversations/{id}/messages
GET  /api/assistant/jobs/{id}/events
POST /api/assistant/messages/{id}/branch
POST /api/assistant/actions
          |
          v
api/v1/research.py -> application/research_service.py
          |
          +-> LegalRetrievalPort
          +-> CitationValidationPort
          +-> SessionMemoryPort
          +-> allowlisted Draftly MCP tools
          +-> ConversationRepository
          +-> DocumentReadPort
          \-> AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` (actor, roles, matter memberships) and orchestrates the domain
plus ports. `LegalRetrievalPort` is the seam over `src/draftly/retrieval`; the
service imports no retrieval internals, no SQLAlchemy, no FastAPI. Per plan §6,
production must reach the engine only through a **versioned package/interface**,
never by importing arbitrary research paths across the repository boundary.

Long-running answer composition follows plan §7: the ask returns a job
identifier and current state rather than holding the request open while
retrieval runs.

The job also exposes resumable server-sent events. A reconnecting client sends
its last acknowledged event ID and receives only later persisted events.
Streaming transport never changes which claims are retained in the final
answer.

## 3. Domain models it needs

In `domain/research.py`, mirroring the frontend contract in
`frontend/src/types/answer.ts` exactly:

- **GroundedAnswer** — a discriminated union on `kind`:
  - `{ id, kind: "grounded", question, claims: Claim[], corpusLimitKey }`
  - `{ id, kind: "insufficient-authority", question, reasonKey, suggestedActionKey }`
- **Claim** — `{ id, text, citations: Citation[] }`. A claim with no surviving
  citation cannot be retained (§7).
- **Citation** — `{ id, authority: Authority, evidence: EvidenceSpan }`. The
  `EvidenceSpan` (from `evidence.ts`: `documentId`, `page`, optional `region`,
  optional `charRange`, `snippet`) is the source passage the claim resolves to.
- **Authority** — `{ id, title, reference, type: AuthorityType, courtLevel:
  CourtLevel, weight: AuthorityWeight, verified: boolean }`.
- **AssistantScope** — `{ type: AssistantScopeType, targetId?, labelKey }`. The
  scope the question is asked in.

Conversation models support the LibreChat-derived shell without making its
storage model authoritative:

- **ResearchConversation**: `id`, `ownerId`, `scope`, `title`,
  `activeBranchId`, `createdAt`, `updatedAt`, `archivedAt?`.
- **ResearchMessage**: `id`, `conversationId`, `parentMessageId?`, `branchId`,
  `role` (`user | assistant | tool | system`), `content`, `attachmentRefs`,
  `answerId?`, `createdAt`, `editedFromId?`.
- **ResearchBranch**: `id`, `conversationId`, `rootMessageId`, `createdBy`,
  `createdAt`.
- **ToolCallRecord**: `id`, `messageId`, `toolName`, `status`
  (`requested | authorised | running | complete | failed | refused`),
  privacy-safe `inputSummary`, `resultReference?`, and timestamps.
- **AnswerJob**: `id`, `conversationId`, `userMessageId`, `state`,
  `lastEventId`, `corpusVersion`, and timestamps.
- **StreamEvent**: `jobId`, monotonic `eventId`, `kind`, `payload`, and
  `createdAt`. Events are persisted long enough to support the approved
  reconnection window.

Message edits create successor messages and branches. They do not overwrite the
earlier message or the answer and audit records derived from it.

Enums (exact values from the frontend):

| Enum | Values |
| --- | --- |
| `AuthorityType` | `statute`, `amendment`, `gazette`, `case-rule`, `practice-direction` |
| `CourtLevel` | `supreme-court`, `court-of-appeal`, `high-court`, `district-court`, `not-applicable` |
| `AuthorityWeight` | `binding`, `persuasive`, `historical`, `unverified-candidate` |
| `AssistantScopeType` | `matter`, `step`, `document`, `library` |

The grounded-or-silent rule lives in two fields. `Authority.verified: boolean`
is `false` and `AuthorityWeight` is `unverified-candidate` for any
machine-derived case-rule until a lawyer reviews it. A rendered answer may cite
such an authority, but it is visibly marked unverified — it never silently
carries the weight of a reviewed source.

## 4. Ports it depends on

In `ports/`:

- `LegalRetrievalPort` (`ports/legal_retrieval.py`) — the versioned interface
  over `src/draftly/retrieval`. `search(query, scope, corpus_version) ->
  RetrievalResult` returns candidate passages, each with its `SRC`/case id,
  span, and authority metadata. Provider-neutral so the engine is swappable and
  pinned to a recorded corpus version.
- `SessionMemoryPort` (from `memory-service`) — `ingest_episode` and `retrieve`,
  per-matter scoped. This is the "don't re-query" seam, see §6.
- `CitationValidationPort` — resolves every proposed citation to a corpus
  version, authority record, and exact source passage before the claim can be
  retained.
- `ResearchRepository` — persist and load `GroundedAnswer` records and the
  audit-only action log; matter-scoped queries only.
- `ConversationRepository` — persist conversations, immutable message
  successors, branches, tool-call records, answer jobs, and resumable stream
  events.
- `DocumentReadPort` — resolve attachment references and enforce matter
  membership without giving the research service direct object-storage access.
- `AuditPort` — `record(event)`; every ask and every action logs.

The corpus is a **separate index and access path**. `LegalRetrievalPort` has no
handle to matter storage; it cannot query confidential documents (§5.2 trust
boundary). This is enforced by construction — the port simply exposes no such
method.

### Draftly MCP tools

Draftly may expose its research capabilities to the legal-research agent
through an authenticated, allowlisted MCP server. LibreChat can present these
tool calls, but it does not grant their permissions.

Initial tool surface:

```text
search_statutes
search_cases
lookup_legal_reference
expand_citation_graph
get_source_passage
search_matter_memory
get_matter_context
```

Tool rules:

- The server derives actor and matter scope from the authenticated service
  session. The model cannot grant itself access by supplying a matter ID.
- Each tool has a typed input and output schema, timeout, result-size limit,
  and audit event.
- Corpus tools return authority IDs, corpus versions, and source spans rather
  than uncited prose.
- Matter tools call Draftly service ports and repeat membership checks.
- `get_matter_context` returns only the minimum permitted context for the
  current question.
- Tools are read-only in V0. Adding a result to a matter or creating a check
  requires a separate, explicit, role-gated user action.
- Arbitrary user-configured MCP servers are not available in a matter-scoped
  legal conversation.

## 5. The methods

### create_conversation(ctx, scope, title?) -> ResearchConversationRead

Creates a user-owned research conversation. A matter, step, or document scope
requires a fresh membership check. The persisted scope cannot be widened by a
later client request.

### list_conversations(ctx, query?, cursor?) -> ConversationPage

Returns only conversations visible to the actor. Search covers conversation
titles and permitted message text. Search indexing must preserve the same
matter access boundary as the source rows.

### append_message(ctx, conversation_id, message, attachments?) -> AnswerJobRead

Appends a user message without modifying previous messages. Each attachment is
an existing `DocumentVersion` reference or a new upload routed through
`document-service`. The method re-checks conversation and attachment access,
creates an AnswerJob, and starts the same grounded-answer pipeline used by
`ask`.

File attachment does not make an uploaded value authoritative. Matter
documents still pass through document processing and lawyer verification.

### branch_message(ctx, message_id) -> ResearchBranchRead

Creates a new branch rooted at an existing visible message. The original branch
and its answer records remain unchanged.

### stream_job(ctx, job_id, last_event_id?) -> event stream

Returns persisted events after `last_event_id`, then follows new events until
the job reaches a terminal state. Event payloads may include safe text deltas,
tool-call status, citation candidates, abstention, completion, or failure.
Partial deltas are presentation state and never become a persisted
`GroundedAnswer` until final citation validation succeeds.

### ask(ctx, question, scope) -> AnswerJobRead

The round-trip that does not exist today. `POST /api/assistant/ask`.

1. Resolve `scope` (an `AssistantScope`) and re-check any matter membership it
   references from the repository; do not trust the router.
2. Consult `SessionMemoryPort.retrieve` first (§6). On a hit for an already
   established question, serve the remembered answer without re-running the
   engine.
3. On a miss, call `LegalRetrievalPort.search` against the pinned corpus
   version. This is the long path; return a job id and `pending` state per §7,
   then compose asynchronously in `workers/research_jobs.py`.
4. Compose claims from the retrieval passages. For each claim, attach only
   citations that resolve to a real `EvidenceSpan` plus an `Authority`. Drop any
   claim whose citations do not validate.
5. If no claim survives validation, return the `insufficient-authority` branch
   with a `reasonKey` and `suggestedActionKey` — **abstain, do not fabricate**
   (§7 exit gate).
6. Ingest the result into session memory as episodes carrying `SRC`/case
   pointers, so a later identical or near ask is served from memory.
7. Audit `assistant.question-asked`. Persist the `GroundedAnswer`, append a
   terminal stream event, and return the updated job. The completed answer is
   available through the conversation message and answer read endpoints.

### get_answers(ctx) -> GroundedAnswer[]

`GET /api/assistant/answers`. Lists past answers for the actor. Read-only;
already wired in the frontend to a mock accessor (`getAnswers`).

### record_action(ctx, answer_id, action, matter_id?) -> ActionRead

`POST /api/assistant/actions`. Today this writes an **audit line only**
(`assistant.{action}`) via the demo store — the button's real side effect is not
implemented. The service records the action against the answer and audits it.
The action names the frontend already emits are `added-to-matter`,
`saved-to-library`, `check-created`, `authority-review-requested`, and
`question-asked`. Turning those into real side effects (creating a check,
persisting to the library) is out of this method's scope — see §9.

## 5A. Entitlement and metering

Research is the second most expensive thing Draftly does, and this document
previously named no gate at all, so `billing-service.md`'s `research.enabled`
and `research_queries.monthly` keys had no caller.

```text
auth_service.authorize(ctx, capability, matter_id?)
billing_service.require_feature(org, "research.enabled")
billing_service.reserve_usage(org, "research_queries.monthly", 1,
                              operation_id=answer_job_id)
   -> compose in the worker
   -> consume on a terminal answer, grounded or abstained
   -> release when the job fails without producing an answer
```

An **abstention still consumes a query**: the retrieval ran, and pricing an
honest `insufficient-authority` at zero would create a quiet incentive against
abstaining. A memory-served answer (§6) consumes nothing, because no retrieval
ran — that is the point of the cache.

Quota exhaustion returns 429 `quota_exhausted` before the job is created, never
a degraded or partial answer.

## 6. The "don't re-query" seam

This is the integration with `memory-service` (its §9). The first ask for a
matter hits the full retrieval pipeline; the result is remembered; later asks in
the same session are served from memory.

```text
ask #1: question ─→ LegalRetrievalPort.search (full statute/case pipeline)
                    └─ result composed, then ingested as episodes
                       (SRC/case id + span pointers, non-authoritative)
ask #2+: question ─→ SessionMemoryPort.retrieve (fast, remembered set)
                    └─ only a genuine delta re-triggers LegalRetrievalPort
```

Because remembered law is stored as `SRC`-id pointers, an answer served from
memory is still traceable and re-runnable — it does not become a second,
drifting source of truth. Session memory is a cache; the corpus stays
authoritative.

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Every retained claim resolves to a source passage and authority status (Phase 6 gate) | Each `Claim` keeps only `Citation`s with a real `EvidenceSpan` + `Authority`; unbacked claims are dropped |
| Unsupported questions abstain (Phase 6 gate) | The `insufficient-authority` union branch, with `reasonKey`/`suggestedActionKey`; never a fabricated claim |
| No invented citation (§9.2 release blocker) | Citation validation runs on every claim before an answer is retained |
| Machine-derived case-rules stay unverified | `Authority.verified = false` and `weight = unverified-candidate` until lawyer review; visibly marked |
| Corpus cannot query matter storage (§5.2) | `LegalRetrievalPort` exposes no matter-storage access; separate index and path |
| Never authority | A grounded answer is a suggestion; nothing here feeds a draft — only the verified tier does |
| Ask does not block on retrieval (§7) | Returns a job id and state; composition runs in the worker |
| Chat shell cannot widen authority | LibreChat-derived components call typed Draftly APIs; they do not decide corpus, matter, role, memory, or audit policy |
| Tool access follows the actor | MCP tools derive identity and scope from the authenticated service session and repeat matter membership checks |
| Conversation history is preserved | Edits and branches create successors; previous messages, answers, tool calls, and audit records are not overwritten |
| Streaming cannot bypass grounding | Partial events are presentation state; only the final citation-validated answer is persisted as GroundedAnswer |
| Organisation isolation | Conversations, messages, jobs, and stream events filter on `ctx.organisationId` before anything else; the corpus release is the one deliberately non-tenant store (`security-model.md` §2) |
| Research is metered | `research.enabled` plus `research_queries.monthly`; an abstention consumes, a memory-served answer does not (§5A) |
| Every ask and action audited (inv. 8) | `AuditPort.record` on `ask` and `record_action` |

## 8. Failure modes to handle explicitly

- Retrieval returns candidates but none validate to an `EvidenceSpan` —
  abstain via `insufficient-authority`, do not force a weak claim.
- Retrieval engine unavailable or times out — the job fails with an explicit
  retry state; no partial or guessed answer is persisted.
- Session-memory hit is stale (the corpus version moved) — treat as a miss and
  re-retrieve against the pinned version.
- Scope names a matter the actor cannot access — deny at membership re-check,
  return 404-not-403 (Phase 2 gate) so matter existence is not leaked.
- A question is asked in `library` scope with no matter context — allowed;
  answers over the public corpus only, no matter memory.
- A stream disconnects — resume after the last acknowledged persisted event;
  do not start a duplicate answer job.
- A replay cursor has expired — return an explicit non-resumable response and
  let the client load the persisted final message state.
- An attachment belongs to another matter or an inaccessible document version
  — reject it without disclosing the document's existence.
- A LibreChat upstream update changes component or data-provider contracts —
  keep the pinned reviewed revision until compatibility, accessibility,
  licence, and security tests pass.
- A model requests an unapproved MCP tool or a wider matter scope — refuse the
  call, display the refusal in the tool-call UI, and audit it.

## 9. Test list

- **Unit:** claim retention (drop claims with no valid citation); abstain
  produces the `insufficient-authority` branch; `unverified-candidate` weight
  and `verified=false` survive composition; discriminated-union serialisation
  matches `answer.ts`.
- **Contract:** `GroundedAnswer` response schema against the frontend type; the
  conversation, message, branch, tool-call, stream-event, and `ask` job
  envelopes; `LegalRetrievalPort` and MCP tool schemas.
- **Integration:** ask #1 hits retrieval and ingests episodes; ask #2 served
  from session memory without re-running the engine; corpus-version bump forces
  re-retrieval; a disconnected stream resumes without duplicating a job;
  branching preserves the original path; attachment access is re-checked;
  latency measured against the V0 target (Phase 6 gate).
- **Frontend compatibility:** each selected LibreChat component renders under
  Next.js 15 and React 19, uses Draftly's typed APIs and translations, passes
  keyboard and screen-reader checks, and has no dependency on LibreChat's Node
  API, MongoDB model, or authentication state.
- **Licence:** copied or substantially derived files retain required notices;
  the third-party notice records the pinned LibreChat revision.
- **Security:** the corpus cannot reach matter storage; cross-matter scope
  denied with 404-not-403; no matter data leaks into a `library`-scope answer;
  arbitrary MCP tools are unavailable; no secret or raw client data in logs.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Real side effects for assistant actions.** `added-to-matter`,
   `saved-to-library`, and `check-created` currently write only an audit line
   (`POST /api/assistant/actions`). Do they call into `verification_service`,
   `library-service`, and `check_service` respectively, or stay audit-only for
   V0? Lean **audit-only for V0, wire real effects in Phase 8** once those
   services expose write paths.
2. **Search-then-answer split.** Plan §7 lists `POST /research/search` and `POST
   /research/answers/{job}` separately. Does the frontend `ask` map to a single
   composed call, or expose raw search first? Lean **single `ask` for the
   assistant, keep raw `search` available for the library/browse path**.
3. **Voice dictation (Mic) — scope closed, date open.** The composer's Mic
   button is backed by `voice-service.md`, which ships in V0 if the schedule
   allows and otherwise in V1. Either way the transcript is a candidate the user
   must confirm and explicitly submit; voice never asks the assistant a question
   on its own (`voice-service.md` §9). This service needs no change when voice
   lands — it receives ordinary composer text.
4. **Corpus-version pinning per answer.** Whether a persisted `GroundedAnswer`
   records the exact corpus version it was composed against (recommended, for
   reproducibility and re-run).
5. **Memory-hit freshness window** — inherited from `memory-service` open
   decision 3 (how long a remembered retrieval serves before a delta forces a
   fresh query).
6. **LibreChat reuse boundary.** The default is selected client-component reuse
   inside Draftly, not a separately deployed LibreChat application. Confirm the
   first pinned upstream commit and component inventory after the compatibility
   spike.
7. **Conversation persistence.** Decide whether research conversations use
   dedicated PostgreSQL tables in this service or a shared conversation store.
   Matter permissions and immutable message successors are required either way.
8. **MCP deployment.** Prefer an internal authenticated streamable-HTTP MCP
   endpoint exposed only to the Draftly legal-research agent. Confirm whether
   the first V0 implementation calls the same application ports directly and
   adds MCP as an adapter afterward.
9. **Resumable-event retention.** Set the stream-event retention window and
   maximum replay size. Final messages and GroundedAnswers follow their
   approved records-retention policy and are not deleted with transient stream
   events.

## 11. LibreChat references

- [LibreChat repository](https://github.com/danny-avila/LibreChat)
- [LibreChat MIT licence](https://github.com/danny-avila/LibreChat/blob/main/LICENSE)
- [LibreChat MCP documentation](https://www.librechat.ai/docs/features/mcp)
- [LibreChat Agents documentation](https://www.librechat.ai/docs/features/agents)
- [LibreChat authentication documentation](https://www.librechat.ai/docs/features/authentication)
- [LibreChat access-control documentation](https://www.librechat.ai/docs/features/access_control)
