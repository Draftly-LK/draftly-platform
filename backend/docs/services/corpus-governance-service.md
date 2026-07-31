# corpus-governance-service: implementation design

Companion to `library-service.md`, `research-service.md`, and
`backend/backend-implementation-plan-v0.md`.

This service is the publication gate between collected legal material and the
controlled Draftly corpus. It exists because obtaining a source, indexing a
source, displaying it, quoting it, and offering it for download are separate
rights decisions.

This document is an engineering policy, not a legal opinion. A Sri Lankan
intellectual-property lawyer must approve the production source policy and any
licence relied on for NLR, SLR, or third-party legal databases.

## 1. Decision

V0 publishes a catalogue of independently verified official statutes,
amendments, and gazettes. Full-text indexing or display is enabled only when
the exact source record passes provenance and rights review.

The CommonLII case-law harvest is quarantined. It is excluded from:

- the production corpus and vector index;
- library browse and source-detail responses;
- research retrieval and model context;
- generated snippets, quotations, and citation passages;
- training, evaluation, and embeddings;
- downloads, exports, and public datasets; and
- rebuild or refresh jobs.

Case names or citations discovered there may enter Draftly only after being
independently verified from an approved official, licensed, or public-domain
source. The CommonLII database is not the production provenance for that new
record.

Historical law-report material and modern NLR/SLR material remain
`quarantined` or `metadata-only` until a record-specific public-domain
determination, official source, or written licence is recorded. Publisher
headnotes, summaries, catchwords, pagination, annotations, and indexes are
never treated as official judgment text.

## 2. Local-source assessment

The research repository currently contains separate folders for statutes,
amendments, gazettes, and case law. Folder membership is discovery metadata,
not approval.

The proposed notarial-practice curriculum is useful for:

- topic taxonomy;
- acquisition priority;
- statute-to-topic relationships; and
- coverage-gap reporting.

It is not itself legal authority or proof of rights. Draftly must independently
verify every title, number, year, amendment relationship, and official source.
The curriculum text is not published unless its ownership and permission are
recorded.

## 3. What it owns

The service owns:

- source discovery records;
- immutable provenance and retrieval metadata;
- rights and licence classifications;
- separate indexing, display, quotation, and download policies;
- rights-review and content-review decisions;
- quarantine and takedown state;
- corpus release manifests and versions;
- approval of a source for a particular use; and
- audit events for every governance transition.

It does not:

- answer legal questions;
- browse or display the public library;
- infer that a source is official from its filename or directory;
- convert a third-party transcription into an official source;
- author case summaries or legal propositions;
- decide that fair use permits a commercial corpus; or
- silently broaden rights when an LLM or crawler can access the material.

`library_service` remains the read-only catalogue. `research_service` retrieves
only approved indexable sources.

## 4. Domain model

```text
LegalSource
  id
  title
  sourceType
  jurisdiction
  language
  publicationBody
  sourcePublisher
  sourceUrl
  retrievedAt
  checksum
  localObjectRef?
  officialText
  officialTranslation
  provenanceStatus
  rightsStatus
  licenceReference?
  indexingPolicy
  displayPolicy
  quotationPolicy
  downloadPolicy
  reviewState
  reviewedBy?
  reviewedAt?
  reviewReason?
  effectiveFrom?
  effectiveTo?
  supersedesSourceId?
  version
```

```text
ProvenanceStatus =
  verified-official |
  verified-licensed |
  verified-public-domain |
  unverified

RightsStatus =
  official-text |
  licensed |
  public-domain |
  restricted |
  unknown

IndexingPolicy =
  full-text |
  metadata-only |
  blocked

DisplayPolicy =
  full-text |
  snippet-only |
  metadata-only |
  link-out |
  blocked

QuotationPolicy =
  approved-span |
  short-quotation-only |
  blocked

DownloadPolicy =
  source-file |
  link-to-official-source |
  blocked

CorpusReviewState =
  discovered |
  provenance-recorded |
  rights-reviewed |
  content-reviewed |
  approved |
  quarantined |
  retired
```

Policy fields are explicit because one licence may permit internal indexing
without allowing public full-text display or downloads.

## 5. Publication workflow

```text
source discovered
  -> provenance recorded
  -> rights or licence classified
  -> content and official status reviewed
  -> policies approved independently
  -> source included in a signed corpus release
  -> library and research services may consume that release
```

Only `approved` sources appear in a production corpus release. Unknown,
restricted, quarantined, or incomplete records fail closed.

The approval checks include:

1. Source URL resolves to the recorded publication body or licensed provider.
2. Checksum matches the reviewed file.
3. Official-text status is supported by the source, not inferred from content.
4. Any licence is attached and its permitted uses map to explicit policies.
5. Editorial material is separated from official source text.
6. Language and official-translation status are verified.
7. Effective and supersession relationships are reviewed.
8. The source has an approved topic mapping independent of copied database
   arrangement.

## 6. V0 catalogue policy

### 6.1 Statutes and amendments

An approved record may expose:

- official title;
- Act or Ordinance number and year;
- source type and language;
- enactment, certification, or publication date;
- amendment and supersession relationships;
- curriculum-derived topic labels after independent verification;
- provenance status and retrieval date; and
- the official-source link.

The default V0 UI is `metadata-only` with
`downloadPolicy=link-to-official-source`. Full-text search may operate
internally only for `verified-official` records with
`indexingPolicy=full-text`.

### 6.2 Gazettes

Gazettes follow the same gate. A file named like a Gazette is not approved
until its number, date, part, language, publication body, and official source
are verified.

### 6.3 Case law

V0 does not publish the harvested NLR/SLR/CommonLII collection. An individually
approved case record may later expose independently verified metadata:

```text
case name
neutral or report citation
court
decision date
official or licensed source link
rights and verification status
```

Judgment text, report scans, headnotes, summaries, and source passages remain
blocked unless the exact record has an approved policy permitting that use.

### 6.4 Draftly editorial material

Draftly-created topic labels, citation relationships, rule candidates, and
lawyer-authored summaries are separate records:

```text
DraftlyEditorialRecord
  id
  kind
  textOrStructuredValue
  sourceAuthorityId
  evidenceSpan?
  createdBy
  verifiedBy?
  verifiedAt?
  version
```

An editorial record cannot copy a provider's headnote or summary. Its evidence
span must resolve to a source whose quotation and display policies permit that
use.

## 7. Enforcement

The corpus build fails when:

- a source is not `approved`;
- indexing is broader than `indexingPolicy`;
- a passage is emitted when quotation is blocked;
- full text is returned under metadata-only or link-out policy;
- a download is generated when download is blocked;
- the source checksum differs from the reviewed checksum; or
- a source has no release-manifest entry.

Runtime services receive policy-filtered records. They cannot override source
policy:

```python
if source.display_policy == "full-text":
    return approved_full_text
if source.display_policy == "snippet-only":
    return approved_metadata_and_permitted_spans
if source.display_policy in {"metadata-only", "link-out"}:
    return metadata_and_source_link
raise PublicationDenied()
```

The production retrieval index is built from the release manifest, never by
walking the research repository directories.

## 8. Takedown and quarantine

A maintainer or legal reviewer can quarantine a source immediately. Quarantine:

- removes it from the next production index and catalogue release;
- invalidates cached source passages;
- marks dependent research answers unavailable for replay;
- preserves source, review, release, and audit history; and
- prevents replacement by a new file under the same source version.

It does not delete evidence of what was previously published. Permanent
deletion, where legally required, follows an approved takedown procedure and
retains the minimum non-content audit record.

## 9. Tests

### Unit

- Unknown and restricted sources fail closed.
- Folder name and filename never imply official status.
- Policy combinations reject broader indexing, display, quotation, or download.
- Quarantined sources cannot enter a release.
- Approved metadata-only records never return text.

### Contract

- LegalSource enums and policy fields.
- Catalogue-safe and retrieval-safe projections.
- Corpus release manifest and checksum schema.
- Quarantine and takedown events.

### Integration

- Build a statutes catalogue from approved manifest entries only.
- Exclude every CommonLII path from catalogue and retrieval indexes.
- Reject an unverified consolidated statute.
- Approve an official amendment as metadata-only with an official link.
- Quarantine an indexed source and rebuild without stale passages.

### Security and compliance

- Production workers cannot read the quarantine store.
- Research tools cannot override source policy.
- Audit records do not copy restricted text.
- A release can be reproduced from its signed manifest and reviewed checksums.

## 10. Decisions

1. Ship statutes, amendments, and gazettes as a rights-reviewed catalogue
   before shipping case-law full text.
2. Quarantine the CommonLII harvest and stop automated refreshes.
3. Treat the curriculum as coverage taxonomy, not authority or publication
   content.
4. Require independent source verification for every catalogue entry.
5. Build production indexes only from approved release manifests.
6. Obtain written Sri Lankan IP review before enabling NLR/SLR text, snippets,
   embeddings, training, or downloads.

## 11. Legal-review sources

- [Sri Lanka Intellectual Property Act, No. 36 of 2003 on WIPO Lex](https://www.wipo.int/wipolex/en/legislation/details/6705)
- CommonLII copyright policy and source-specific notices, to be archived in the
  rights-review record before relying on CommonLII material.
