# research-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `document-service.md`,
and `memory-service.md`. This service is the **grounded legal assistant**: a
question about Sri Lankan RTA law goes in, a cited answer or an honest
abstention comes out.

Maps to plan **Phase 6** (grounded research), API row **Research** (§7), and the
trust-boundary row *Legal corpus* (§5.2). It is the flagship the frontend does
not yet have — today the assistant textbox submits into nothing.

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

## 2. Where it sits

```text
GET  /api/assistant/answers  ─┐
POST /api/assistant/ask      ─┼─→ api/v1/research.py ─→ application/research_service.py
POST /api/assistant/actions  ─┘                                  │
   (plan §7 resource: Research: POST /research/search,           │ orchestrates
    POST /research/answers/{job})                                ▼
                          ports: LegalRetrievalPort, SessionMemoryPort,
                                 ResearchRepository, AuditPort
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
- `ResearchRepository` — persist and load `GroundedAnswer` records and the
  audit-only action log; matter-scoped queries only.
- `AuditPort` — `record(event)`; every ask and every action logs.

The corpus is a **separate index and access path**. `LegalRetrievalPort` has no
handle to matter storage; it cannot query confidential documents (§5.2 trust
boundary). This is enforced by construction — the port simply exposes no such
method.

## 5. The methods

### ask(ctx, question, scope) -> GroundedAnswer

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
7. Audit `assistant.question-asked`. Persist the `GroundedAnswer`. Return it.

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
memory is still traceable and re-runnable — it does not become a second, drifting
source of truth. Session memory is a cache; the corpus stays authoritative.

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

## 9. Test list

- **Unit:** claim retention (drop claims with no valid citation); abstain
  produces the `insufficient-authority` branch; `unverified-candidate` weight
  and `verified=false` survive composition; discriminated-union serialisation
  matches `answer.ts`.
- **Contract:** `GroundedAnswer` response schema against the frontend type; the
  `ask` job envelope (id + state); `LegalRetrievalPort` result shape.
- **Integration:** ask #1 hits retrieval and ingests episodes; ask #2 served
  from session memory without re-running the engine; corpus-version bump forces
  re-retrieval; latency measured against the V0 target (Phase 6 gate).
- **Security:** the corpus cannot reach matter storage; cross-matter scope
  denied with 404-not-403; no matter data leaks into a `library`-scope answer;
  no secret or raw client data in logs.

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
3. **Voice dictation (Mic).** The composer shows a Mic button; voice is
   explicitly V1 and out of V0 scope (plan §2.2). Any later voice input must
   create a reviewable candidate — it cannot silently ask or verify.
4. **Corpus-version pinning per answer.** Whether a persisted `GroundedAnswer`
   records the exact corpus version it was composed against (recommended, for
   reproducibility and re-run).
5. **Memory-hit freshness window** — inherited from `memory-service` open
   decision 3 (how long a remembered retrieval serves before a delta forces a
   fresh query).
