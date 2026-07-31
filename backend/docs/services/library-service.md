# library-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`corpus-governance-service.md`, `research-service.md`, and
`memory-service.md`. This service is the **read side of the controlled legal
corpus**: browse and look up only sources approved for the requested use.

Maps to plan **Phase 6** (the separate versioned legal corpus), API row
**Research** (§7), and the trust-boundary row *Legal corpus* (§5.2). The `/library`
screen is hardcoded today; there is no accessor and no endpoint behind it.

## 1. What it owns

**Read-only browse and lookup** over the controlled legal-source catalogue:
list authorities filtered by type or topic and open one authority under its
approved display policy. It owns the reference view of the published corpus:
what sources exist, what each one is, its provenance, and which representations
may be shown.

It is distinct from `research-service`, which **answers questions**. This service
does not compose answers, does not cite claims, and does not abstain. It hands
back policy-filtered authorities for a human to inspect. It writes nothing:
`corpus-governance-service` owns source review, policies, approval, quarantine,
and release manifests.

V0 exposes a catalogue of approved official statutes, amendments, and gazettes.
It does not expose the harvested CommonLII, NLR, or SLR full-text collection.

## 2. Where it sits

```text
GET /api/library        ─┐
GET /api/library/{id}   ─┴─→ api/v1/research.py ─→ application/library_service.py
                                                          │ orchestrates
                                                          ▼
                                    ports: LegalCataloguePort, AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` and reads through `LegalCataloguePort`, a policy-filtered view
of the same approved corpus release that research uses. Library code never
reads research-repository directories or quarantine storage. The service
imports no retrieval internals, SQLAlchemy, or FastAPI.

The frontend `/library` screen
(`frontend/src/components/library/library-screen.tsx`) currently renders a
**hardcoded in-component list** — four literal rows, no data call. These two
endpoints replace that list. The migration removes hardcoded case-law rows and
does not retain them as an offline fallback. V0 type filters expose Statutes,
Amendments, and Gazettes; Case Law remains disabled with neutral
rights-review-pending copy until approved records exist.

## 3. Domain models it needs

The M3 backend expands the frontend `Authority` with catalogue governance
fields:

- **Authority** — `{ id, title, reference, type: AuthorityType, courtLevel:
  CourtLevel, weight: AuthorityWeight, verified: boolean }`. The row shown in a
  browse list and the header of a detail view.
- **LegalSourceSummary** — `Authority` plus `publicationBody`, `sourceUrl`,
  `retrievedAt`, `checksum`, `provenanceStatus`, `rightsStatus`,
  `displayPolicy`, `downloadPolicy`, `language`, and `corpusVersion`.
- **AuthorityDetail** — the summary plus only the representation permitted by
  its policy: approved full text, approved snippets, or metadata/link-out.

Enums (exact values from the frontend):

| Enum | Values |
| --- | --- |
| `AuthorityType` | `statute`, `amendment`, `gazette`, `case-rule`, `practice-direction` |
| `CourtLevel` | `supreme-court`, `court-of-appeal`, `high-court`, `district-court`, `not-applicable` |
| `AuthorityWeight` | `binding`, `persuasive`, `historical`, `unverified-candidate` |

For V0, browse filters expose `statute`, `amendment`, and `gazette`. Case-law
metadata is disabled until individual records have independent approved
provenance. Machine-derived case-rule records are Draftly editorial content and
are never a substitute for an approved underlying source.

## 4. Ports it depends on

In `ports/`:

- `LegalCataloguePort` — reads an approved signed corpus release:
  `list_authorities(filter, corpus_version) -> LegalSourceSummary[]` and
  `get_authority(id, corpus_version) -> AuthorityDetail`. The adapter applies
  display and download policies before returning data and has no quarantine or
  matter-storage access.
- `AuditPort` — `record(event)`; corpus access is auditable (§5.2 lists content
  access among audited events).

## 5. The methods

### browse(ctx, filter) -> AuthorityListRead

`GET /api/library`. Lists authorities in the corpus, filterable by
`AuthorityType` and independently verified topic taxonomy. Each row carries its
provenance, rights, verification, display, and download state. Read-only,
pinned to a recorded approved corpus version.

### get_authority(ctx, authority_id) -> AuthorityDetailRead

`GET /api/library/{id}`. Returns one policy-filtered authority:

```text
full-text    -> approved text and section navigation
snippet-only -> approved metadata and permitted passages
metadata-only or link-out -> metadata and approved source URL
blocked      -> no catalogue record
```

V0 defaults statutes, amendments, and gazettes to catalogue metadata plus an
official-source link. Full text is returned only when its exact source record
has `displayPolicy=full-text`.

## 6. The corpus trust boundary

The controlled legal corpus is a **separate source, index, and access path** from
confidential matter storage (§5.2). Two rules follow, and both are enforced by
construction here:

```text
┌──────────────────────────────────────────────┐
│ Approved legal corpus release                │  signed release manifest
│ statutes · amendments · gazettes             │  → policy-filtered catalogue
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

Restricted research sources are a third, separate boundary:

```text
CommonLII harvest and unreviewed NLR/SLR
  -> internal research retrieval only
  -> no Library source-text access
  -> no Library snippet, export, or download path
```

## 7. Invariants this service enforces

| Invariant | How |
| --- | --- |
| Read-only | The service exposes no write method; governance of corpus content is not here |
| Rights policy is enforced server-side | Response shape is selected from the approved source policy; the browser cannot request a broader representation |
| Every listed authority carries verification status + weight | `Authority.verified` and `weight` returned on every row and detail; unverified case-rules visibly marked |
| Corpus separate from matter data (§5.2) | Reads only through `LegalRetrievalPort`; no matter-storage access on the port |
| Machine-derived case-rules not silently authoritative | `weight = unverified-candidate` / `verified = false` shown, never hidden |
| Corpus access audited | `AuditPort.record` on browse and lookup where policy requires |
| Restricted research storage is unreachable | Catalogue adapter reads the public release only and has no path to restricted source text |

## 8. Failure modes to handle explicitly

- Requested authority id not in the pinned corpus version — return 404, do not
  fall through to a matter-storage lookup.
- Corpus index unavailable — the browse list fails explicitly; it does not
  return a partial or stale hardcoded fallback.
- A filter names an unknown `AuthorityType` — reject as a validation error
  rather than silently returning everything.
- A source is unknown, restricted, quarantined, or absent from the signed
  release — omit it from browse and return 404 on direct lookup.
- A caller asks for full text of a metadata-only record — return the approved
  metadata representation; never trust a client-selected display mode.
- A reviewed checksum no longer matches — remove the source from the release
  and fail explicitly.

## 9. Test list

- **Unit:** filter-by-type narrows the list; provenance and policy fields are
  present; unknown-type filter rejected; metadata-only never returns text.
- **Contract:** `Authority` list and detail schemas against `answer.ts`; the
  `AuthorityDetail` section/text shape.
- **Integration:** browse and lookup over the approved release; a matter
  document and every CommonLII path are absent; corpus-version consistency
  between list and detail; quarantine invalidation removes cached passages.
- **Security:** the corpus cannot reach matter storage; no private document id
  is enumerable through the library; no secret or raw client data in logs.

## 10. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **Own service or read facade.** Keep library as a thin read facade over the
   approved corpus release, with `LegalCataloguePort` enforcing catalogue
   policy and `LegalRetrievalPort` enforcing research indexing and quotation
   policy.
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
5. **V0 case-law visibility.** Keep case law disabled in the public catalogue
   until each record is independently verified and approved. Do not use the
   CommonLII harvest as production provenance.
