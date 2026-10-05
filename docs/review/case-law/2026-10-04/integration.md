# Case-library integration checks

Checks use the supplied corpus locally; no judgment text or case metadata is
included in this evidence. Automated fixtures and screen captures are synthetic.

## Corpus fidelity

- PASS: 7,439 LKCA and 2,162 LKSC records; 9,601 unique prefixed IDs.
- PASS: all 9,601 stored texts equal their original parsed input text.
- PASS: both input SHA-256 checksums match the generated manifest.
- PASS: historical years span 1878–2010.
- PASS: catalogue version is `commonlii-v1-a44c7378583d1341`.

## Frozen service and backend HTTP adapters

Built `deploy/retrieval/Dockerfile` with the research checkout and the explicit
`deploy` build context, with embeddings disabled. Ran the image with
`--read-only --tmpfs /tmp`, publishing only a temporary localhost port.

- PASS: coverage exposes 9,601 catalogue records, 5,121 conveyancing search
  records and 3,663 overlapping reader IDs.
- PASS: default-size browse, collection/year filtering and consecutive pages
  return valid records without overlapping IDs.
- PASS: detail without an approval manifest returns metadata with no text.
- PASS: absent reader ID is distinct from an unavailable service.
- PASS: a generic synthetic conveyancing fact pattern returns at most eight
  results with lexical or graph corroboration and excerpts bounded at 900 chars.
- PASS: unknown synthetic terms return valid `no_similar_cases`.
- PASS: disabled dense status is explicit; no embedding calls were made.
- PASS: unreachable private service raises `case_corpus_unavailable`, rather
  than a successful empty result.

Synthetic unit tests cover actor/checksum/audience approval, dense-only rejection,
quota rollback, concurrent replay and changed-body idempotency conflicts. Their
final gate results are recorded with the release checks.
