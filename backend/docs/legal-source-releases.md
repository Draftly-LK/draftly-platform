# Legal source release operator contract

The validator is
`src.modules.corpus_governance.infrastructure.manifest.validate_release`.
It takes canonical manifest bytes, a detached raw Ed25519 signature, a trusted
32-byte Ed25519 public key supplied by the caller, an exact audience and a source
root `Path`. It performs no network requests, key generation or source publication.
Production signer identity, trust distribution and key custody remain human-owned.

The release envelope has exactly `schemaVersion`, `audience` and `sources`.
`schemaVersion` is `legal-source-release-v1`; `audience` is `internal-research` or
`public-catalogue`; `sources` is an array. Encode with
`canonical_manifest_bytes`: UTF-8, sorted object keys, compact separators,
unescaped Unicode and no nonfinite/floating-point numbers. No trailing newline,
BOM or duplicate object keys is accepted. Sign those exact bytes. The returned
identity is `legal-sources-v1:` plus their SHA-256; caller release labels are not
accepted. The signature covers metadata, permissions and every input checksum.

Each source has these required fields:

| Fields | Meaning |
| --- | --- |
| `sourceId`, `title`, `reference`, `kind` | Public identity; kind is statute, amendment or gazette |
| `sourceUrl`, `publicationBody`, `sourcePublisher`, `language`, `retrievedAt` | Reviewed provenance; HTTP(S) source link and timestamp with timezone |
| `officialText`, `officialTranslation`, `provenanceStatus`, `rightsStatus`, `sourceUseClass`, `reviewState` | Explicit booleans and the service-plan enums; only approved review state enters a release |
| `original` | Object with contained relative POSIX `path` and lowercase 64-hex `sha256` for the original file |
| `commencementKnown`, `currencyStatus`, `relationships` | Explicit commencement boolean, service metadata state and relationship array |
| `rightsApproval`, `contentApproval`, `policy` | Independent recorded decisions described below |

Optional fields are `publicationDate`, `effectiveFrom`, `effectiveTo`,
`commencementSourceId`, `commencementPage`, `licenceReference` and `indexed`.
Unknown dates remain null/absent; publication is not inferred as commencement.
Dates use `YYYY-MM-DD`. Known commencement requires an effective date and its
reviewed source ID/page; an effective end cannot precede its start. Currency is
`current`, `superseded`, `reverify` or `unknown`, as independently recorded.

`indexed`, when present, is a separate `{path, sha256}` for approved UTF-8 index
input. It is required exactly when indexing is `full-text`; metadata-only releases
carry no index bytes. Original provenance and derivative hashes remain distinct.
Neither native extraction nor OCR automatically approves a derivative.

Each relationship has `relation` (`amends`, `supersedes`, `made-under` or
`commences`), `targetSourceId`, `reviewState` (`unreviewed` or `reviewed`), and
optional `targetReference` and positive integer `supportingPage`. The containing
source is the edge origin. Discovery follows only reviewed edges and returns only
sources in the same validated audience release; it does not invert stored edges.

Each approval object has a nonblank `reference`, nonblank `reviewedBy` and
timezone-aware `reviewedAt`. `contentApproval` additionally carries `sourceSha256`
and optional `indexedSha256`, matching the exact original and derivative.
`policy` has `audience`, `indexing`, `display`, `quotation`, `download` and its own
`approval` object. The enums are the corpus-governance service-plan values.
The trusted signer attests that these independently recorded approvals exist;
the validator cannot supply or grant those decisions.

Unknown rights/provenance, incomplete approvals, blocked indexing, quarantine,
retirement and inappropriate audiences refuse the entire release. Licensed and
restricted sources require a written permission reference. Restricted internal
sources cannot enter the public catalogue or permit source-file download/full
reader display. Internal `snippet-only` display requires the exact approved
internal audience, an explicit `approved-span` or `short-quotation-only` policy
and a written licence reference, in addition to the independent approval records.
The public read adapter returns metadata only even when another
explicit policy permits more. Consumers must separately enforce quotation,
display and download permissions before returning any content.

Paths must stay beneath the resolved root; absolute paths, traversal, backslashes,
drive/alternate-stream syntax and symlinks are refused. File hashes are checked
before returning a frozen `ValidatedRelease`. Builders use each
`ReleasedSource.indexed_content` directly, retaining its `source.policy`; they
must not rescan directories or reopen listed files after validation. A failed
supplied manifest must never fall back to a broad directory build.

`ManifestAuthorityReader` accepts that validated release.
`authorities(..., release_version=...)` and `related(...)` require its exact
identity and expose only `AuthorityMetadata`. `ReleaseUnavailableError` is the
shared failure contract; `ReleaseIntegrityError` and `PublicationDenied`
distinguish integrity and policy refusal. Consumers report a metadata coverage
gap on failure rather than substitute a caller label or newest metadata release.

The [existing owner review packet](../../docs/review/matter-flow/2026-10-09/legal-source-review-packet.md)
records the proposed official sources, acquisition warnings and remaining gaps.
All eleven staged originals still have pending rights/content review and blocked
indexing. Their exact local checksum inventory stays in ignored staging. No
source text, real signing key or invented approval reference is committed here.

Compile, Ruff and mypy checks cover this engineering slice. Test suites and live
publication are unverified under the user's explicit test waiver. Production
source rights, content, audience approval and signing custody remain pending.
