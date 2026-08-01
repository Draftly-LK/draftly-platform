# memory-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`corpus-governance-service.md`, `document-service.md`,
`document-processing.md`, and `voice-service.md`. This service is the
per-matter **session memory** — the working memory that lets the assistant
resume a matter across sessions without re-querying everything each turn.

Its design is **HiMem-shaped**.

## 1. What it owns

A per-matter store of **non-authoritative working memory**: document summaries,
pointers to retrieved law, session working notes, voice-transcript events, and
decision state. It lets the assistant answer "what were we working on" and
"where did this answer come from" on reopen, and it caches established context
so the same statute or case lookup does not run again every turn.

It does **not** hold verified facts, does **not** feed drafts, and is **never**
authority. The verified matter record stays in its own gated, lawyer-controlled,
audited tier (see §3). This service sits underneath it.

## 2. Why adopt the shape, not the benchmark module

The benchmarked HiMem backend is a benchmark approximation, not a shippable
store. Read directly from `logical-context/experiments/himem/backend.py`:

- **In-memory only.** State lives in Python dicts and is wiped by `reset()` and
  `teardown()`. Nothing survives a restart, so as-is it cannot resume a session
  — which is the entire point of this service.
- **No per-matter isolation.** It is scoped by a single `run_id`; multi-tenant
  namespacing is a stated non-goal there.
- **No correction or supersession.** There is no ADD/UPDATE/DELETE and no
  validity interval. "Current truth" is achieved only by recency plus a
  timestamp cutoff — the old value is not marked superseded, it just ranks
  lower.

What the benchmark backend does have, and what this service keeps: the two-tier
memory shape, the hybrid retrieval, and real provenance. The missing pieces
(persistence, per-matter keying, supersession) are specified in the team's own
`logical-context/memory-system-design.md` and are added here.

## 3. The two-tier line

```text
┌───────────────────────────────────────────────┐
│ Verified matter record  (authority)            │  Postgres, lawyer-gated, audited
│ verified/corrected particulars → feed drafts   │  → verification_service
└───────────────────────────────────────────────┘
                    ▲ only lawyer-verified facts cross up
┌───────────────────────────────────────────────┐
│ Session memory  (non-authoritative)            │  this service
│ episodes + notes + pointers → suggestions only │
└───────────────────────────────────────────────┘
```

Nothing in session memory is authority. A fact enters a draft only from the
verified tier, never from here. This is the two-tier rule the memory evaluation
kept regardless of store, and it is what makes a memory weakness (silent
note-overwrite) tolerable.

## 4. The cache discipline (the key rule)

**Everything in session memory is reconstructable from the authoritative
stores** — verified facts in Postgres, documents in object storage, law in the
signed internal-research corpus release, and voice transcript events in the
voice-service event store. Session memory is a cache, not a source of truth.

This single rule neutralises the benchmark HiMem's main weakness. If a note is
silently overwritten or drifts stale, the worst case is a re-derivation; the
history, the corrections, and the audit trail live in the authoritative tier,
not here. Memory never becomes the only place a fact exists.

## 5. Memory shape (ported from the benchmark)

Two layers, from `backend.py` (`_EpisodeMemory`, `_NoteMemory`,
`_reconsolidate_note`, `NOTE_WINDOW`):

- **Episodes** — one immutable, verbatim record per event (a document summary
  arriving, a retrieval result, a lawyer note, or a live transcript event).
  Kept exactly as written, with its source pointer.
- **Notes** — rolling summaries that group related episodes by **thread**,
  **topic**, and **participant**. One episode joins several notes; each note is
  a window of its most recent source episodes and is reconsolidated when a new
  episode joins. A note always retains its full `source_event_ids`, so
  provenance back to raw episodes survives every reconsolidation.

## 6. What gets remembered

Each item carries a **source pointer**; prefer pointers over paraphrases so
everything traces back:

| Remembered item | Source pointer |
| --- | --- |
| Document summary | `DocumentVersion` id (immutable) |
| Retrieved law | Approved legal-source id, corpus release, policy version, and query |
| Retrieved case | Restricted internal-research case-source id, release, policy version, and query |
| Session working note | session id, author, timestamp |
| Decision / checklist state | the matter event that set it |
| Live partial transcript | `TranscriptEvent` id, session id, and sequence |
| Final provider transcript | `CandidateTranscript` id |
| User-edited transcript | `TranscriptRevision` id |
| Confirmed transcript | `ConfirmedTranscript` id |

The four voice rows are a **conditional** contract: `voice_service` ships in V0
or V1 by schedule (`voice-service.md` §1). Memory must function with no voice
publisher at all — the `voice.*` subscriptions simply never fire — and must not
treat their absence as an error.

Voice partials are stored as episodes in a dedicated `voice-live` thread. Every
partial remains verbatim and source-linked. A newer partial supersedes the
earlier current fragment; the final transcript supersedes all partials for
ordinary retrieval. History queries may still return the earlier sequence.

Partial episodes do not reconsolidate long-term notes because repeated provider
revisions would create noisy summaries. Final, edited, and confirmed transcript
events do trigger normal note reconsolidation.

## 7. Retrieval

Hybrid, lexical-first, ported from `_score_note` / `_score_episode` /
`_recency_score`:

1. Filter episodes to those before the query's time cutoff.
2. Score notes (token overlap, key-entity bonus, level weight, recency); a
   scoring note boosts its recent source episodes.
3. Score episodes directly (lexical overlap, topic/thread/participant match,
   recency, exact-id bonus).
4. Take the max of note-boost and direct score per episode, rank, keep the top
   results — each with its provenance (`event_id`, snippet, source).

**Paraphrase robustness.** The benchmark showed HiMem is strong but
lexical-overlap-dependent — it lost about 9 judge points when probe wording was
paraphrased. An optional embedding channel recovered 3 to 8 points on
paraphrased probes but *reduced* the score on the original suite by pushing
stale-but-related episodes into the capped result set. So the embedding channel
is available behind the port and must be tuned against a Draftly sample, not
switched on blind.

## 8. Corrections and staleness

This is what the benchmark module lacked and this service must add. Session
memory subscribes to authoritative-tier events:

- `document.version-superseded` (from `document_service`) — the episodes and
  notes derived from the old document version are invalidated and refreshed from
  the successor.
- particular corrected or rejected (from `verification_service`) — memory
  derived from the old value is invalidated.
- `corpus.source-quarantined` or `corpus.source-policy-changed` (from
  `corpus-governance-service`) — every episode and note containing the affected
  source passage is invalidated and excluded from replay.
- `corpus.release-retired` — episodes pinned only to that release are
  revalidated against an active approved release before use.
- `voice.transcript-partial-superseded` (from `voice_service`) — the earlier
  partial remains in history but is excluded from current-context retrieval.
- `voice.transcript-finalised` — all partial episodes for that session are
  superseded by the final candidate transcript.
- `voice.transcript-revised` or `voice.transcript-confirmed` — current
  retrieval follows the latest user-reviewed version while preserving the
  provider transcript and earlier edits.

On top of the ported shape, add the validity-interval and truth-maintenance
semantics from `memory-system-design.md`: an invalidated episode is marked
superseded with a pointer to what replaced it, not deleted. History stays
queryable, so "what is the current answer" returns the live value while "what
did we believe before" still resolves.

## 9. The "don't re-query" win

```text
turn 1:  question ─→ internal legal retrieval release
                     └─ result ingested with source/release/policy pointers
turn 2+: question ─→ session memory (fast, ~0.024s-class) serves the remembered
                     context; only a genuine delta triggers a fresh retrieval
```

Memory holds the established working set for the matter, so the assistant
resumes instead of rebuilding context, and repeated lookups do not re-run the
retrieval engine. Because remembered law is stored as approved source and
release pointers, a served answer is still traceable and re-runnable. A
quarantined source is invalidated rather than replayed from memory.

## 10. SessionMemoryPort

Provider-neutral port so the store is swappable, mirroring the benchmark's
`MemoryBackend` contract (`setup` / `ingest` / `retrieve`) adapted to Draftly:

- `ingest_episode(matter_id, event) -> None`
- `ingest_voice_event(scope_id, transcript_event_ref) -> None`
- `retrieve(matter_id, probe) -> RetrievalResult` (episodes plus provenance)
- `invalidate(matter_id, source_ref)` and `supersede(matter_id, old, new)`
- `purge(scope)` — called by `retention_service` on an approved destruction
- organisation and per-matter scoping on every call

### 10.1 The read surface

Memory previously had no endpoints at all, which made "resume the matter"
unreachable from the browser. Two read routes, both organisation- and
matter-scoped and both paginated:

```text
GET /api/v1/matters/{id}/memory/context      what were we working on
GET /api/v1/matters/{id}/memory/search?q=    retrieve with provenance
```

Both return episodes with their source pointers and supersession state, and both
are explicitly labelled non-authoritative in the response envelope so no client
can mistake a remembered value for a verified one. There is **no write route**:
memory is populated by events, never by a browser.

The application service orchestrates the port; it imports no SQLAlchemy and no
embedding SDK.

## 11. Persistence — the matter Postgres

Session memory persists in the **same Neon or self-hosted Postgres as the
matter** (see `infrastructure.md`), in its own per-matter-keyed tables:
episodes, notes, note-to-episode links, and an optional embeddings table when
the vector channel is enabled. One store, one backup path, and memory writes can
be transactional with the matter events that trigger them. Per-matter keying
gives isolation; a cross-matter read is a bug, not a feature.

Standalone assistant dictation that has no matter uses a capturing-user scope
instead of a matter scope. It must never be returned in another user's or
another matter's memory query.

## 12. Honesty rules

- Non-authoritative — never feeds a draft; only the verified tier does.
- Source pointer on every remembered item.
- Reconstructable from the authoritative stores at all times.
- Corrections in the authoritative tier propagate down and invalidate stale
  memory.
- Corpus quarantine and policy narrowing invalidate affected legal passages;
  memory cannot preserve access that the current source policy removed.
- Every voice-memory episode points to a persisted voice-service event or
  transcript version.
- Partial transcript history is stored, but only the latest non-superseded
  transcript state participates in ordinary current-context retrieval.
- Per-matter isolation is absolute, and organisation isolation sits outside it:
  every episode, note, and embedding row carries `organisation_id` and every
  query filters on it before the matter key (`security-model.md` §2).
- Memory is purged when `retention_service` destroys a scope, and rebuilt from
  the surviving authoritative stores when the scope itself survives
  (`retention-service.md` §6).

## 13. Test list

- **Unit:** note reconsolidation keeps `source_event_ids`; retrieval ranking
  (note-boost versus direct score); recency and cutoff behaviour; supersession
  marks rather than deletes.
- **Contract:** `SessionMemoryPort` operations; `RetrievalResult` provenance
  fields.
- **Integration:** ingest to retrieve over Postgres;
  `document.version-superseded` invalidates the right episodes; cross-matter
  isolation; reconstruct memory from the authoritative stores after a wipe;
  ingest an ordered partial-transcript stream, supersede it with the final
  transcript, and preserve historical retrieval.
- **Voice memory:** every partial has a `TranscriptEvent` pointer; provider
  partials do not reconsolidate notes; final, edited, and confirmed versions do;
  standalone dictation remains capturing-user scoped.
- **Evaluation:** on a Draftly sample, measure retrieval quality with and
  without the embedding channel, and the paraphrase gap, to set the channel
  weight and note-window size.

## 14. Open decisions

1. **Embedding channel** — on or off by default, and its weight, tuned on a
   Draftly sample (§7).
2. **Note window size** — episodes per note before the oldest rolls off
   (benchmark default 6).
3. **Caching aggressiveness** — how long a remembered retrieval result serves
   before a delta forces a fresh query.
4. **Voice-event retention** — how long superseded partial episodes and their
   source events remain available after a final transcript is confirmed,
   subject to privacy, audit, and matter-retention policy.
