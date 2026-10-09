# Matter statute and amendment discovery design

Date: 2026-10-09. This records the user's approved additional scope alongside
the lawyer-led matter workflow. Architecture approval covers the controlled
retrieval engine, a versioned release for missing official sources, amendment
relationships, explicit known/unknown dates and retained legal source review.
The user explicitly selected both transaction-date and current-law relevance.

## Product behavior

From the existing Overview conversation, a lawyer can ask which legal authorities
may be relevant to the reviewed matter. Return principal statutes, related
amendments/regulations and supporting passages where the installed source policy
permits them. Each result has its source identity, official link, exact known
page/span precision, release identity and review state. Source leads, matched
passages, source-content review and legal applicability remain distinct.

Show transaction-date and current-date context together. Use the selected
transaction's current association revision and eligible reviewed attestation date
(`rta.instrument.attestation_date`) when available. An unavailable date or ambiguous
transaction requires clarification; never take the first transaction, a company's
resolution date or the most recent matter-wide date. Natural-language hypothetical
dates remain labeled assumptions, never verified canonical facts. They do not
mutate the register without its existing lawyer review command.

Known publication/certification dates do not supply unknown commencement dates.
An amendment requiring a commencement Order keeps that date unknown until the
supporting Order and date metadata are reviewed. Display the recorded temporal
facts and uncertainty, without equating a date-window comparison with a legal
decision that an enactment applies. Do not fabricate consolidated wording or
silently exclude related historical amendments that the lawyer needs to inspect.

## Observed gaps and reused ownership

The approved findings are in matter-statute-amendment-findings.md. The packaged
SQLite release contains 57 statutes and 18 amendments but no title gazette rows.
The deployed engine's exact contents remain unmeasured. Its platform Docker builder
copies processed statutes, amendments and cases but no gazette directory. Existing
metadata inventories already name downloaded gazettes; download does not establish
index inclusion or approval. Six generic synthetic bundled probes are diagnostics,
not retrieval precision or legal completeness measurements.

Research owns authorized, metered retrieval and claim composition. Its existing
MatterResearchPort and persistent matter conversation remain the consumer boundary.
The Task 6 fix supplies actual frozen-index identity and explicit unavailable versus
completed retrieval states; this extension must reuse those reviewed contracts.

Corpus-governance owns provenance, source rights, audiences, source review and
versioned releases. Its directory currently has no implemented tracked runtime
files; the library's existing SQLite facade is a read boundary, not a governance
writer. Build the smallest release-validation and metadata boundary required by
the existing corpus-governance plan rather than a new general administration app.

Content-governance already exports RequirementSourceRecord with publication,
effective, retrieval, verification and supersession metadata. Reuse its public
source references for rule provenance, with explicit source-ID mappings to corpus
records. Do not alter seed lawyer approvals, source-currency judgments, requirement
policy, form copy or legal gates merely to make search work. Source indexing and
audience policy stay with corpus-governance/research, as the content plan requires.

Library reads only the policy-filtered public release. Extend its existing typed
authority vocabulary for gazettes and metadata where necessary; it never reads
matter storage, quarantine files, or restricted case-law text. Matter legal results
remain in the existing research journey rather than requiring a Library redesign.

## Source preparation and release

Prepare immutable official-source acquisition records with canonical URL, issuer,
language, retrieval time, SHA-256, publication metadata, extraction warnings and
review state. Keep downloaded originals and extracted source content in ignored
local staging until their use policy permits publication. Committed tests use
independently synthetic legal-source fixtures; committed real source inventory is
metadata only unless an exact content-use decision permits more.

The initial comparison includes the Title Act, title regulation chain 1050/10,
1886/58 and 2308/27, and conditional Notaries/Prevention of Frauds/Companies/stamp
duty authorities identified in the approved findings. Broken official links,
missing originals, unclear language and absent commencement Orders remain explicit
acquisition or coverage gaps. A company or power of attorney is not assumed from
an unreviewed machine candidate. Source discovery is driven by reviewed context
and exact legal references, not a declaration that every source applies.

Amendment relationships retain the exact related source/section and their own
supporting source locator and review state. Distinguish partial amendments from
whole-source supersession. Unknown end dates do not mean current forever; preserve
the existing source currency/reverification rules and display their limitations.

Release validation checks file checksums, source identity and explicit independently
approved internal-research/public-catalogue policies. New sources default to
unreviewed/blocked indexing. A machine discovery, download, OCR result or this
architecture approval cannot create a lawyer's content/rights approval. Prepare
the concrete source-review packet before any required human publication decision.
No agent may enable provider/storage approval flags or invent a named lawyer.

Approved indexing reads only exact release-listed source files and verified hashes.
The platform deployment boundary may add approved gazette inputs/metadata to the
existing frozen index interface without editing the sibling research repository.
Release identity covers both indexed text and the date/relationship metadata that
answers use. Changed source or metadata creates a new immutable release; old saved
answers retain exact passages and release references with stale/unavailable state
when source policy demands it. Quarantined sources cannot silently replay.

## Query, persistence and interface

Use closed typed query parameters and current actor/matter authorization. When a
transaction is selected, verify its matter and current association revision before
using its reviewed facts. Preserve party/parcel associations and unknowns. The
retrieval corpus itself has no route into confidential matter storage.

Retrieve exact requested authorities and their recorded amendment relationships
alongside ranked topical candidates. An exact Gazette query cannot be satisfied
silently by different Acts. Return coverage and missing-authority reasons, metadata
and policy-permitted passages. Only claims supported by returned eligible passages
survive composition; absent authority/provenance/provider state is truthful.

Persist both date contexts, selected scope/reference versions, source/release
identities, source locators, uncertainty and supported claims in the existing
conversation/result history. Same logical retries cannot duplicate messages or
metering; an intentional repeated question after corrections is a fresh request.
Unavailable retrieval releases reservations under the reviewed Task 6 boundary.

Use the shared Overview/full-view conversation and source panel. Official links
come from recorded source metadata, never arbitrary model URLs. English/Sinhala
labels use existing tokens and next-intl. Legal/statutory/template/approval/waiver
wording remains human-owned. Source review does not approve a draft or satisfy a
checklist policy by itself.

## Evidence and delivery sequence

After Task 6 fixes and independent acceptance, finish the scoped Form 8 task.
Execute this source/query extension before the final Task 8 whole-branch journey
so the final gates and human packet cover the complete requested behavior once.
Use sequential fresh implementers and independent reviews, with focused atomic
commits for release policy/metadata and coupled retrieval/UI contracts. Preserve
the existing branch and PR 98; a human merges.

Required evidence includes: synthetic principal/amendment/regulation relationships;
two transactions with different reviewed dates; unknown/deferred commencement;
partial amendments; stale/corrupted/quarantined sources; unavailable transport;
exact-reference misses; permitted versus blocked passages; old release replay;
concurrent retry and current authorization; EN/SI source inspection; and real
application API persistence. Measure actual configured-engine source coverage;
never substitute bundled title counts or doubles for that result. Full gates,
final integrated review and the original 51-observation extraction benchmark remain
part of the workflow delivery. Human source/legal review and visual/terminology
acceptance are recorded separately from engineering tests.

## Verification waiver

The user explicitly waived further test-suite, browser and extraction benchmark
execution on 2026-10-09. Implementation, compile/build checks and independent code
review continue. Unmeasured acceptance remains unverified; the waiver does not
create source-content, rights, legal, template or human visual approval.
