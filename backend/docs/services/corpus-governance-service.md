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

V0 has two independently governed corpus audiences:

```text
internal-research
  -> statutes, amendments, gazettes, and restricted case-law retrieval

public-catalogue
  -> independently verified official statutes, amendments, and gazettes
```

The CommonLII-derived case-law collection is classified
`restricted-internal-research`. It may feed case search, citation-graph
retrieval, grounded answer composition, embeddings, and internal evaluation.
It is excluded from:

- Library browse and source-detail full text;
- judgment, report-scan, database-page, and headnote display;
- bulk downloads, exports, and public datasets; and
- any endpoint that returns the stored source document.

Research responses may expose Draftly-composed claims, case citations, and
bounded evidence passages needed to ground those claims. They do not expose a
source-document reader or reconstruct the underlying report.

Historical law-report material and modern NLR/SLR material use the same
audience-specific policy unless an official source, public-domain
determination, or written licence permits broader use. Publisher headnotes,
summaries, catchwords, pagination, annotations, and indexes are never treated
as official judgment text.

This boundary records the intended product behavior; it is not a conclusion
that internal commercial use is risk-free. Provider terms and Sri Lankan
copyright advice remain an explicit legal-review item.

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
- separate internal-research and public-catalogue release manifests;
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

`library_service` reads only the public-catalogue release.
`research_service` reads the internal-research release, including sources whose
public display and download policies are blocked.

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
  sourceUseClass
  licenceReference?
  indexingPolicy
  displayPolicy
  quotationPolicy
  downloadPolicy
  allowedAudiences
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

SourceUseClass =
  public-catalogue |
  restricted-internal-research |
  quarantined

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

CorpusAudience =
  internal-research |
  public-catalogue

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
  -> audience policies approved independently
  -> source included in one or both signed audience releases
  -> each runtime service consumes only its release
```

Only reviewed sources appear in a release. Unknown, denied, quarantined, or
incomplete records fail closed. A `restricted` source may appear in the
internal-research release only when its indexing, quotation, display, and
download restrictions are explicit. It cannot appear in the public-catalogue
release unless its public policy separately permits that audience.

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

The case-library extension imports parsed LKCA/LKSC metadata into a frozen,
versioned catalogue with input checksums and extraction warnings. This metadata
is explicitly unverified and is not presented as independently verified source
authority. The extension does not change restricted-research permissions.

Full judgment display is a separate record-level policy. It requires the written
approval reference, the exact text checksum, and the approved authenticated
audience. The default remains metadata-only with source link; missing, mismatched
or inapplicable approval cannot expose text. No bulk-download or export path is
added. See [the implementation](../../../docs/case-law-library.md).

V0 indexes the CommonLII-derived NLR/SLR and court collection for restricted
internal research. The research engine may search the text, retrieve grounded
passages, construct a citation graph, and compose an answer.

The Library does not publish the harvested source text. An individually
approved public-catalogue case record may later expose independently verified
metadata:

```text
case name
neutral or report citation
court
decision date
official or licensed source link
rights and verification status
```

Judgment text, report scans, headnotes, database pages, and bulk source passages
remain blocked from Library display and download unless the exact record has a
separate public policy permitting that use.

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

An audience-specific corpus build fails when:

- a source is not reviewed for that audience;
- indexing is broader than `indexingPolicy`;
- a passage is emitted when quotation is blocked;
- full text is returned under metadata-only or link-out policy;
- a download is generated when download is blocked;
- the source checksum differs from the reviewed checksum; or
- a source has no release-manifest entry for the requesting audience.

Runtime services receive audience- and policy-filtered records. They cannot
override source policy:

```python
if audience == "internal-research" and source.indexing_policy == "full-text":
    return retrieval_record
if audience == "public-catalogue" and source.display_policy == "full-text":
    return catalogue_full_text
if audience == "public-catalogue" and source.display_policy == "snippet-only":
    return catalogue_metadata_and_permitted_spans
if audience == "public-catalogue" and source.display_policy in {
    "metadata-only",
    "link-out",
}:
    return catalogue_metadata_and_source_link
raise PublicationDenied()
```

The research index and public catalogue are built from different signed release
manifests, never by walking research-repository directories at runtime.

## 8. Takedown and quarantine

### Implemented signed release boundary (2026-10-09)

`corpus_governance.infrastructure.manifest.validate_release` verifies canonical
UTF-8 JSON with a caller-trusted raw Ed25519 public key, then applies the domain
policy to every entry and verifies exact original and optional indexed-text
checksums beneath the supplied release root. The source identity exposed by the
read DTO always hashes the original; a separately reviewed derivative has its
own hash. A changed approval, metadata field or source hash changes the immutable
`legal-sources-v1:<sha256>` release identity. No production key or approval is
created by this implementation.

Rights, content and audience approval records each retain their reviewer,
timestamp and reference. Content approval binds both original and derivative.
Each signed envelope has exactly one audience. Missing, unknown, quarantined,
retired, blocked, checksum-mismatched and wrong-audience records fail closed.
The validator returns frozen records and already-checked immutable index bytes;
builders must consume those bytes rather than reopen mutable paths.

`contracts.LegalAuthorityReadPort` exposes metadata only.
`ManifestAuthorityReader` requires the exact validated release identity; a
mismatch is unavailable, never a lookup in a newer release. Related discovery
follows reviewed incoming and outgoing edges and returns the original records,
preserving edge direction, section references and supporting pages. No source
bytes, file paths or approval commands cross this DTO boundary.

The optional frozen producer now uses this validator before the existing engine
accepts exact release-listed bytes. Runtime repeats shared signed metadata/policy
validation and verifies the actual index attestation. Research enforces recorded
quotation/display policy before emitting a passage; public catalogue validation
uses its separate audience. No source release has been published by this wiring.
Runtime quarantine requires withdrawing the independently mounted current release
identity, not mutating a frozen release in place. Missing current state fails closed.
See [the release operator contract](../legal-source-releases.md).

A maintainer or legal reviewer can quarantine a source immediately. Quarantine:

- removes it from the applicable research and catalogue releases;
- invalidates cached source passages;
- marks dependent research answers unavailable for replay;
- preserves source, review, release, and audit history; and
- prevents replacement by a new file under the same source version.

It does not delete evidence of what was previously published. Permanent
deletion, where legally required, follows an approved takedown procedure and
retains the minimum non-content audit record.

## 9. Tests

### Unit

- Unknown and denied sources fail closed.
- Folder name and filename never imply official status.
- Policy combinations reject broader indexing, display, quotation, or download.
- Quarantined sources cannot enter a release.
- Approved metadata-only records never return text.
- Restricted internal-research records cannot enter the public catalogue.

### Contract

- LegalSource enums and policy fields.
- Catalogue-safe and retrieval-safe projections.
- Corpus release manifest and checksum schema.
- Quarantine and takedown events.

### Integration

- Build a statutes catalogue from approved manifest entries only.
- Include reviewed CommonLII-derived records in the restricted research index.
- Exclude every CommonLII source document from Library browse and download.
- Reject an unverified consolidated statute.
- Approve an official amendment as metadata-only with an official link.
- Quarantine an indexed source and rebuild without stale passages.

### Security and compliance

- Library workers cannot read the restricted research source store.
- Research tools cannot override source policy.
- Audit records do not copy restricted text.
- A release can be reproduced from its signed manifest and reviewed checksums.

## 10. Decisions

1. Ship statutes, amendments, and gazettes as a rights-reviewed catalogue
   before shipping case-law full text.
2. Use the CommonLII-derived case-law collection for restricted research while
   blocking Library source-text display and download.
3. Treat the curriculum as coverage taxonomy, not authority or publication
   content.
4. Require independent source verification for every catalogue entry.
5. Build the research index and public catalogue from separate signed release
   manifests.
6. Obtain written Sri Lankan IP review before broadening NLR/SLR/CommonLII
   access beyond restricted research.

## 11. Legal-review sources

- [Sri Lanka Intellectual Property Act, No. 36 of 2003 on WIPO Lex](https://www.wipo.int/wipolex/en/legislation/details/6705)
- CommonLII copyright policy and source-specific notices, to be archived in the
  rights-review record before relying on CommonLII material.
