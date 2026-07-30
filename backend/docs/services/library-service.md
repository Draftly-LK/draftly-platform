# library-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `research-service.md`,
and `memory-service.md`. This service is the **read side of the controlled legal
corpus**: browse and look up the statutes, amendments, gazettes, and case-rules
that ground everything else.

Maps to plan **Phase 6** (the separate versioned legal corpus), API row
**Research** (§7), and the trust-boundary row *Legal corpus* (§5.2). The `/library`
screen is hardcoded today; there is no accessor and no endpoint behind it.

## 1. What it owns

**Read-only browse and lookup** over the controlled legal-source corpus: list
authorities filtered by type or topic, open one authority with its sections and
text. It owns the reference view of the corpus — what sources exist, what each
one is, and whether each is verified.

It is distinct from `research-service`, which **answers questions**. This service
does not compose answers, does not cite claims, and does not abstain. It hands
back authorities and their contents for a human to read. It writes nothing:
governance of the corpus is not its job (that is a separate concern; corpus
ingestion and indexing sit behind the retrieval engine, not here).

## 2. Where it sits

```text
GET /api/library        ─┐
GET /api/library/{id}   ─┴─→ api/v1/research.py ─→ application/library_service.py
                                                          │ orchestrates
                                                          ▼
                                    ports: LegalRetrievalPort, AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` and reads through the same `LegalRetrievalPort` that
`research-service` uses — the corpus index and source registry are one thing,
seen two ways (browse here, answer there). The service imports no retrieval
internals, no SQLAlchemy, no FastAPI.

The frontend `/library` screen
(`frontend/src/components/library/library-screen.tsx`) currently renders a
**hardcoded in-component list** — four literal rows, no data call. These two
endpoints replace that list.

## 3. Domain models it needs

It reuses the research corpus types (from `frontend/src/types/answer.ts`); it
introduces no new authority shape:

- **Authority** — `{ id, title, reference, type: AuthorityType, courtLevel:
  CourtLevel, weight: AuthorityWeight, verified: boolean }`. The row shown in a
  browse list and the header of a detail view.

Enums (exact values from the frontend):

| Enum | Values |
| --- | --- |
| `AuthorityType` | `statute`, `amendment`, `gazette`, `case-rule`, `practice-direction` |
| `CourtLevel` | `supreme-court`, `court-of-appeal`, `high-court`, `district-court`, `not-applicable` |
| `AuthorityWeight` | `binding`, `persuasive`, `historical`, `unverified-candidate` |

The corpus behind these is the same `src/draftly/retrieval` index and source
registry that grounds research — the controlled body of Sri Lankan RTA sources
(statutes, amendments, gazettes, and machine-derived case-rules). The section
text returned by the detail view comes from that registry, not from a new store.

## 4. Ports it depends on

In `ports/`:

- `LegalRetrievalPort` (`ports/legal_retrieval.py`) — the shared versioned
  interface over `src/draftly/retrieval`. For browse it needs list/lookup
  reads: `list_authorities(filter, corpus_version) -> Authority[]` and
  `get_authority(id, corpus_version) -> AuthorityDetail` (the authority plus its
  sections/text). These are read methods on the same port research uses; no
  matter-storage handle exists on it.
- `AuditPort` — `record(event)`; corpus access is auditable (§5.2 lists content
  access among audited events).

## 5. The methods

### browse(ctx, filter) -> AuthorityListRead

`GET /api/library`. Lists authorities in the corpus, filterable by
`AuthorityType` and topic (the frontend already renders type filters: statutes,
gazettes, case-rules, questions). Each row carries its `weight` and `verified`
status so an unverified machine-derived case-rule is visibly marked, exactly as
the hardcoded screen distinguishes "verified" from "candidate". Read-only,
pinned to a recorded corpus version.

### get_authority(ctx, authority_id) -> AuthorityDetailRead

`GET /api/library/{id}`. Returns one `Authority` plus its sections and text for
reading. Read-only. If the id is not in the pinned corpus, return 404.

## 6. The corpus trust boundary

The controlled legal corpus is a **separate source, index, and access path** from
confidential matter storage (§5.2). Two rules follow, and both are enforced by
construction here:

```text
┌──────────────────────────────────────────────┐
│ Legal corpus (public authority)              │  src/draftly/retrieval index
│ statutes · amendments · gazettes · case-rules│  → read-only via this service
└──────────────────────────────────────────────┘
        ▲ no path down to matter storage
┌──────────────────────────────────────────────┐
│ Confidential matter documents                │  matter Postgres + object store
│ NOT public authority                         │  → never surfaced by the library
└──────────────────────────────────────────────┘
```

A confidential matter document is not an authority and never appears in a browse
result. The corpus index has no handle to matter storage, so the library cannot
leak a private document into a public list.

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Read-only | The service exposes no write method; governance of corpus content is not here |
| Every listed authority carries verification status + weight | `Authority.verified` and `weight` returned on every row and detail; unverified case-rules visibly marked |
| Corpus separate from matter data (§5.2) | Reads only through `LegalRetrievalPort`; no matter-storage access on the port |
| Machine-derived case-rules not silently authoritative | `weight = unverified-candidate` / `verified = false` shown, never hidden |
| Corpus access audited | `AuditPort.record` on browse and lookup where policy requires |

## 8. Failure modes to handle explicitly

- Requested authority id not in the pinned corpus version — return 404, do not
  fall through to a matter-storage lookup.
- Corpus index unavailable — the browse list fails explicitly; it does not
  return a partial or stale hardcoded fallback.
- A filter names an unknown `AuthorityType` — reject as a validation error
  rather than silently returning everything.

## 9. Test list

- **Unit:** filter-by-type narrows the list; `verified`/`weight` present on every
  returned row; unknown-type filter rejected.
- **Contract:** `Authority` list and detail schemas against `answer.ts`; the
  `AuthorityDetail` section/text shape.
- **Integration:** browse and lookup over the pinned corpus index; a matter
  document never appears in a browse result; corpus-version consistency between
  list and detail.
- **Security:** the corpus cannot reach matter storage; no private document id
  is enumerable through the library; no secret or raw client data in logs.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Own service or read facade.** Is library a standalone service or a thin
   read facade over `research-service`'s retrieval port? Lean **a thin read
   facade sharing `LegalRetrievalPort`** — one corpus, one access path, browse
   and answer as two views. Splitting the store would duplicate the index.
2. **Topic taxonomy for the topic filter.** The frontend filters by
   `AuthorityType` today; a topic dimension needs a controlled vocabulary. Open
   pending the corpus source registry — do not invent topics.
3. **Questions in the library view.** The hardcoded screen lists a "questions"
   row (a `QuestionSet`). Those are governed content owned by
   `content-governance-service`, not corpus authorities. Decide whether the
   library screen composes both (authorities here + question sets from
   governance) or shows corpus authorities only. Lean **corpus authorities only;
   let the screen fetch question sets separately**.
4. **Section-text pagination** for large statutes in the detail view —
   recommended once real corpus lengths are known.
