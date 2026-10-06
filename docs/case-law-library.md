# Judgment catalogue and similar-case search

The Case law tab in Legal sources browses the supplied LKCA and LKSC judgment
collection. Its fact-pattern search is a separate conveyancing retrieval path.
Research questions can also draw on the same case search, as unverified research
leads; see the research service plan.

## Collection and provenance

The build-time inputs are `data/commonlii/parsed/LKCA/judgments.jsonl` and
`data/commonlii/parsed/LKSC/judgments.jsonl` from the research checkout. The
supplied snapshot contains 7,439 LKCA and 2,162 LKSC records. Runtime services
read a frozen versioned artifact, not research-repository paths.

Catalogue IDs use the `commonlii-` prefix to join the existing search engine.
The collection code is separate from the parsed deciding court. Source text
and paragraph breaks are preserved; encoding and parser warnings remain visible.
Missing dates or titles are not generated. Parsed records remain unverified.

The similarity engine's conveyancing subset is broader than this reader
snapshot. Results present in the catalogue open in Draftly; other results offer
their source link. The interface reports these corpus limits rather than implying
that every catalogued judgment is included in conveyancing similarity search.

## Product behavior

- Browse and filter by case name or citation, collection, and year, using
  server-side pagination rather than downloading all records into the browser.
- Open a judgment with its metadata, provenance, source link and quality warnings.
  Complete text appears only when the record's display policy permits the actor.
- Enter a fact pattern to find up to eight similar conveyancing cases. Results
  show citations, evidence excerpts and retrieval signals, without composing a
  legal answer or assigning binding authority.
- BM25 lexical retrieval, case-graph expansion and optional dense embeddings feed
  reciprocal-rank fusion. The corroboration gate excludes dense-only matches.
  Unavailable service and valid no-similar-cases are separate states.

## Access and release requirements

Authentication applies to browse, reader and search routes. Similarity search
uses the existing research feature and monthly query allowance. Successful empty
searches consume a query; retries with the same logical request do not double
charge. Catalogue browsing does not consume research queries.

The existing restricted-research permission does not grant full-text Library
display. A release must record the written approval reference, exact records,
content checksums and covered audience before serving complete judgment text.
Until that record exists, the reader returns metadata and a source link.
Approval to display text does not mark legal propositions or extraction as
lawyer verified. There is no bulk download or export endpoint.

Dense embeddings remain opt-in and subject to the existing provider-data
approval. Source dumps and generated corpus databases are build artifacts and
must not be committed. Test fixtures and review captures use synthetic content.

## API additions

- `GET /api/v1/library/cases`: filtered, paginated judgment metadata.
- `GET /api/v1/library/cases/{caseId}`: policy-filtered judgment detail.
- `POST /api/v1/research/cases/search`: standalone fact-pattern retrieval, with
  an `Idempotency-Key` for retries.

The existing statute catalogue and assistant endpoints retain their contracts.
The internal retrieval service stays private; application services reach it
through typed ports and the versioned case interface.

## Build and configuration

Build from the platform root, using the research checkout as an explicit input:

```powershell
docker build -f deploy/retrieval/Dockerfile `
  --build-context deploy=deploy/retrieval `
  -t draftly-retrieval ../draftly-research
```

The image contains the frozen catalogue, manifest and search indexes. The backend
uses `RETRIEVAL_BASE_URL`, already wired to the private retrieval service by both
Compose stacks. Rebuild the retrieval image when the input snapshot changes.
No database migration is needed for these routes.

For approved full-text display, mount a reviewed JSON file read-only in the
retrieval container and set `CASE_DISPLAY_APPROVAL_FILE` to its container path:

```json
{
  "audience": "authenticated-library",
  "approvalReference": "recorded-review-reference",
  "userIds": ["approved-user-id"],
  "records": { "commonlii-REVIEWED-ID": "exact-64-character-text-sha256" }
}
```

The reference, audience, actor membership and per-record checksum must all match.
Missing or malformed approval leaves full text closed. Keep the approval file out
of source control; update it through the deployment's reviewed configuration.
The backend derives the actor header from authentication.

Compose does not automatically pass arbitrary `.env` values into retrieval.
After approval, an operator can use a private override file to mount the manifest:

```yaml
services:
  retrieval:
    environment:
      CASE_DISPLAY_APPROVAL_FILE: /run/draftly/case-display-approval.json
    volumes:
      - type: bind
        source: ${CASE_DISPLAY_APPROVAL_HOST_PATH:?set reviewed manifest path}
        target: /run/draftly/case-display-approval.json
        read_only: true
```

Keep the host manifest outside the checkout. Pass the override alongside the
chosen Compose stack with `-f`; the default stack remains metadata-only. Optional
dense settings also belong in retrieval's explicit environment override.

Dense search requires an embedding-enabled image, a runtime provider key,
`DRAFTLY_CASE_DENSE_ENABLED=1` and a recorded `DRAFTLY_CASE_DENSE_APPROVAL` in the
retrieval container. The default image makes no embedding calls. Native provider
failure detection is incomplete, so the API reports enabled status as unknown
instead of asserting a healthy dense channel.

The supplied build has 9,601 reader records, 5,121 conveyancing retrieval records
and 3,663 shared IDs. API coverage also supplies the historical year range.
Reader availability and full-text display approval are separate checks.
