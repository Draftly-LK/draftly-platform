# Matter statute and amendment discovery implementation plan

## Latest explicit user direction (overrides older test instructions)

At 2026-10-09 07:43 UTC the user requested completion within one hour, then
explicitly instructed: "bypass tests and do changes". Do not run pytest, Vitest,
coverage, browser testing, OCR benchmarks or new test suites. Do not delete or
weaken existing tests. Prioritize the approved implementation and retain compile,
type, lint/build checks and independent code review. Report skipped verification
as unverified; source/legal/privacy/authorization gates remain binding. This
section overrides every older RED/GREEN/full-test instruction below.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Discover principal authorities and related amendments through the existing matter conversation, with inspected source provenance and both transaction/current date contexts.

**Architecture:** Extend the existing research and frozen-engine boundary with corpus-governance-owned versioned source metadata and release validation. Resolve dates through existing authorized scope and reviewed-fact read ports, and persist the source/date context alongside existing conversation evidence. New text enters an index only through exact independently approved audience release entries; missing approvals leave truthful source coverage gaps.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy/PostgreSQL, existing cryptography dependency, SQLite/frozen retrieval package boundary, TypeScript/Next.js, next-intl, pnpm.

**Spec:** `docs/superpowers/specs/2026-10-09-matter-statute-amendment-discovery.md` (approved architecture recorded in the controller's source findings; this spec travels with the plan).

## Global constraints

- Preserve V0 user/matter isolation; organization support is explicitly deferred.
- No client inputs, values, images, credentials or identifying logs in fixtures, commits or review packets.
- Do not modify `../draftly-research`, import arbitrary sibling paths, or copy sibling raw data.
- Use the current authorized research owner, metering, audit and installed closed tool contracts.
- Original evidence is immutable; only eligible reviewed scoped facts establish a transaction date.
- Statutory wording, prescribed template copy and approval/waiver language are human-owned.
- Do not change provider/model/privacy settings or enable storage/provider approval flags.
- Architecture approval is not source-content, rights, audience or template approval.
- New indexing defaults blocked; unknown, quarantined, retired, checksum-mismatched or incomplete source policies fail closed.
- Library receives only public-catalogue-safe metadata/links; restricted research passages do not reach it.
- Unknown commencement remains unknown; certification/publication is not substituted for commencement.
- Preserve English/Sinhala localization and existing design tokens.
- Frontend coverage requires literal `CI=true`, unchanged thresholds and exclusions.
- Work on `dev/codex/lawyer-led-matter-workflow`; explicit path staging and Conventional Commit epic scopes; human merges PR 98.

## Dependencies and deliverables

Start after independently accepted Task 6 fixes and Task 7 scoped Form 8. Finish before Task 8's whole-branch integration/gates. Source acquisition is already ignored local-only staging: eleven official PDFs/copies, 239 pages, all eleven hash matches, 50 pages without native text. The eleventh is a DRC-hosted 2026Order copy with legacy Sinhala/scan and identity-review warnings. Never treat these counts as reviewed extraction coverage. Official-source search subsequently identified Companies commencement Order leads2397/50 and2480/47, and related regulations2480/48; direct Government Printing acquisition failed and content review is incomplete. Gazette1050/10 and conditional authorities remain source gaps.

Three reviewable deliverables: (1) source policy/release metadata boundary, (2) existing-engine source/relationship retrieval, (3) scoped dated matter results and connected source inspection. Each ends with meaningful tests, coherent commits and independent review. No new general administration UI or general workflow framework.

## Shared typed interfaces

Create `backend/src/modules/corpus_governance/contracts.py` with immutable DTOs and a read port; domain validation remains framework-independent:

```python
@dataclass(frozen=True)
class AuthorityRelationship:
    relation: Literal["amends", "supersedes", "made-under", "commences"]
    target_source_id: str
    target_reference: str | None
    supporting_page: int | None
    review_state: Literal["unreviewed", "reviewed"]

@dataclass(frozen=True)
class AuthorityMetadata:
    source_id: str
    title: str
    reference: str
    kind: Literal["statute", "amendment", "gazette"]
    source_url: str
    source_sha256: str
    publication_date: date | None
    effective_from: date | None
    effective_to: date | None
    commencement_known: bool
    commencement_source_id: str | None
    commencement_page: int | None
    relationships: tuple[AuthorityRelationship, ...]
    release_version: str
    review_state: str
    currency_status: Literal["current", "superseded", "reverify", "unknown"]

class LegalAuthorityReadPort(Protocol):
    async def authorities(self, source_ids: tuple[str, ...], *, release_version: str) -> tuple[AuthorityMetadata, ...]: ...
    async def related(self, source_ids: tuple[str, ...], *, release_version: str) -> tuple[AuthorityMetadata, ...]: ...
```

Exact approval and indexing/display/quotation/download/audience fields belong to corpus-governance domain records, following its service plan enums; this public DTO does not expose permission-changing commands. A reviewed relationship is distinct from approved content use.

Metadata lookup pins the actual retrieved release identity, never the caller's label
or whichever metadata release is newest at lookup time. Related authority discovery
follows recorded incoming/outgoing links and preserves their actual direction and
locators. A release mismatch withholds unsupported metadata and reports a gap.

Extend `backend/src/modules/research/contracts.py` with an optional request context and result metadata, retaining old callers:

```python
@dataclass(frozen=True)
class LegalDateContext:
    current_date: date
    transaction_id: str | None = None
    association_version: int | None = None
    transaction_date: date | None = None
    fact_id: str | None = None
    fact_version: int | None = None
    reason: Literal["reviewed-date", "date-missing", "date-conflict", "transaction-required"] = "transaction-required"

# MatterResearchPort.answer(..., transaction_id: str | None = None,
#                          association_version: int | None = None)
# GroundedResearch adds date_context, authorities, coverage_gaps with safe defaults.
# SearchResult adds coverage_gaps: list[str] = field(default_factory=list).
```

Never send a client fact to a public corpus endpoint merely to resolve metadata. The research query remains subject to the existing provider-data approval and permission boundary. Metadata lookup uses public source IDs.

## Task A: Enforce immutable audience releases and reviewed metadata

**Files:** Create corpus-governance `__init__.py`, `contracts.py`, `domain/models.py`, `domain/policies.py`, `application/releases.py`, `infrastructure/manifest.py`, `tests/test_release_policy.py`, `tests/test_manifest_integrity.py`. Update the corpus-governance service plan and directly related release/operator documentation. Synthetic fixtures live under `backend/tests/fixtures/legal_sources/`; real staged PDFs stay ignored.

**Consumes:** Existing corpus-governance policy enums/requirements and `cryptography>=50.0.0`. **Produces:** Above read DTO/port; `validate_release(manifest_bytes, signature, trusted_public_key, audience, source_root)` yields an immutable validated release or typed unavailable/policy error.

- [ ] Write failing tests for a valid synthetic signed release, altered metadata, altered text, wrong audience, missing approval reference, unknown rights, quarantined source, blocked indexing, restricted internal text entering public catalogue, path traversal and duplicate IDs.

```python
def test_metadata_change_invalidates_release(synthetic_signed_release):
    manifest, signature, trusted_key, source_root = synthetic_signed_release
    changed = manifest.replace(b'"effectiveFrom":"2022-01-01"', b'"effectiveFrom":"2023-01-01"')
    with pytest.raises(ReleaseIntegrityError):
        validate_release(changed, signature, trusted_key, "internal-research", source_root)
```

- [ ] Run `uv run pytest src/modules/corpus_governance/tests -q --no-cov`; retain RED output and native exit. Tests use a locally generated test-only Ed25519 key and independently synthetic source text; no production key creation.
- [ ] Implement canonical UTF-8 JSON envelope validation, Ed25519 signature verification using the caller-supplied trusted public key, exact audience/review/rights policy checks and immutable file hashes. Missing trust/approval is unavailable. Production signing identity/key custody is external human-owned configuration; never borrow cursor signing keys or generate a production key. Validate paths against the resolved release root and reject symlink escapes. Hash both metadata and indexed source bytes into release identity.

```python
def validate_source(record, audience, actual_sha256):
    if record.review_state != "approved" or record.sha256 != actual_sha256:
        raise PublicationDenied()
    policy = record.policy_for(audience)
    if policy is None or not policy.approval_reference:
        raise PublicationDenied()
    return policy
```

- [ ] Implement read-only manifest metadata adapter. Return only the requested permitted audience projection. Known dates and reviewed relation locators are preserved; absent dates remain null. No legal consolidation or metadata-derived authority approval.
- [ ] Run GREEN tests plus Ruff/format/mypy and policy contract tests. Prepare a concrete local source review packet with exact files/hashes, extraction warnings, proposed audiences and explicit remaining missing sources. A named owner's approval/signing reference is necessary only for actual publication, not engineering tests.
- [ ] Inspect staged paths/text for privacy and encoding, then commit a coherent release boundary using scope from the existing research/corpus plan (`feat(e8-7): validate reviewed legal source releases`). Keep documentation and tests with the implementation.

## Task B: Return source identities and amendment relationships from the existing engine

**Files:** Modify `deploy/retrieval/Dockerfile`, `deploy/retrieval/requirements.txt`, `deploy/retrieval/serve_frozen.py`, `deploy/PRODUCTION.md`, research `domain/models.py`, `ports.py`, `infrastructure/retrieval/http_adapter.py`, `infrastructure/retrieval/statute_adapter.py`, library `domain/models.py`, `api/schemas.py`, `api/router.py`, `infrastructure/sqlite_catalogue.py`, `backend/contracts/openapi.v1.json`. Create a focused deployment release-preparation adapter under `deploy/retrieval/legal_release.py` and tests `backend/tests/unit/test_legal_release_engine_boundary.py`, `backend/tests/unit/test_legal_authority_metadata.py`. Update research/library service contracts. Add only gazette/source metadata support required by the existing catalogue contract; no Library redesign.

**Consumes:** Task A validated audience releases and the accepted Task 6 frozen-index attestation. **Produces:** Existing `/search` remains compatible and attested; a versioned source metadata/relationship response references the exact same release/index. Existing `RetrievalPassage` supports amendment/gazette kinds and metadata references without inventing page precision.

- [ ] Reproduce source selection through the approved versioned engine/package interface. Do not inspect/copy arbitrary sibling raw files. Test that a synthetic reviewed gazette present in the release reaches the existing index builder and an unapproved sibling file cannot. If the installed package excludes gazettes, expose the exact unsupported boundary and implement the smallest platform adapter using its approved document-ingestion interface; do not create a second retrieval algorithm or silently claim gazette support.
- [ ] Write RED transport tests: exact Gazette request with no indexed authority yields explicit coverage gap; returned release mismatch is unavailable; related amendments preserve partial section links; missing commencement stays unknown; public metadata never includes internal text; legacy release with no metadata is explicitly unknown.

```python
async def test_exact_gazette_miss_is_not_replaced_by_topical_hits(adapter):
    result = await adapter.search("Gazette 2308/27", matter_scope, "caller-label")
    assert "requested-authority-missing" in result.coverage_gaps
    assert all(p.source_id != "synthetic-gazette-2308-27" for p in result.passages)
```

- [ ] Implement release-listed build input preparation, hash/metadata validation, approved gazette document inclusion and frozen metadata attestation. Package the same Task A validator through an explicit platform build input; include its existing cryptography dependency in the retrieval image without importing arbitrary sibling files. The new attested identity covers approved indexed bytes, signed metadata and the frozen index artifact; use an explicitly versioned compatible protocol rather than reinterpreting a legacy identity as metadata-aware. Missing release/trust configuration preserves existing honest legacy behavior and explicit unsupported metadata; no production flag/config switch. Model URL/page/relationship data comes only from recorded source metadata. Invalid supplied manifests fail closed, never fall back silently to directory walking. Verify bundled database hash against its actual release manifest before using that identity; a caller label never substitutes for the actual local release either.
- [ ] Retrieve exact requested authority IDs/references and their recorded relationships alongside ranked topical passages through the existing engine boundary. Keep source metadata separate from grounded claims, and retain explicit missing-source/unsupported-source reasons. Source dates do not filter uncertain authorities out silently.
- [ ] Extend Library's closed type vocabulary and public projection only as required. Existing unverified legacy catalogue rows retain unverified status and unknown dates; no binding status from title/folder membership.
- [ ] Run GREEN transport/producer/catalogue tests, exact OpenAPI snapshot tests and static gates. Validate a synthetic full release through the real producer and HTTP consumer, not only separate mocked bodies. Measure the configured engine when available and report its exact attested release/coverage; unavailable local engine is not proof of production contents.
- [ ] Commit coupled producer/consumer/contracts/tests as `feat(e8-7): retrieve related legal authorities with release metadata`, after explicit staging/privacy checks. Independent review must assess the real package input and manifest boundary, not source-count assertions.

## Task C: Persist scoped date context and connect legal source inspection

**Files:** Create `backend/src/modules/research/application/matter_dates.py`; modify research `contracts.py`, `application/matter_research.py`, matter-agent `application/legal_tool.py`, `domain/models.py`, `api/schemas.py`, `infrastructure/repository.py`, `application/turn_runner.py`, `backend/src/bootstrap.py`, and `backend/contracts/openapi.v1.json`. Modify frontend `lib/api/agent.ts`, `components/matter/matter-conversation.tsx`, and EN/SI messages. Create research `tests/test_matter_dates.py`, matter-agent `tests/test_legal_authority_context.py`; extend migrated `backend/tests/integration/test_matter_agent_neon_e2e.py`, frontend `components/matter/assistant-screen.test.tsx` and `lib/api/agent.test.ts`, and the synthetic browser packet. Update research/matter-agent/library/corpus-governance service plans where their contracts change.

**Consumes:** Existing `MatterScopePort.get_transaction`, `ConfirmedFactReadPort.summarise`, Task A metadata read port, Task B attested retrieval and accepted Task 6 persistence/idempotency. **Produces:** Both date contexts plus exact transaction association and reviewed date-fact versions in durable inspectable legal citations/results. No new drafting or fact write tool.

- [ ] Write RED tests for two transactions with distinct dates, no selection, foreign transaction, changed association version, conflicting/unreviewed/stale date, absent date, certification with deferred commencement, and repeated question after correction. Use the exact `rta.instrument.attestation_date` type and reviewed transaction scope.

```python
async def test_other_transaction_date_is_not_used(resolver, ctx):
    context = await resolver.resolve(ctx, "synthetic-matter", transaction_id="tx-a", association_version=3)
    assert context.transaction_id == "tx-a"
    assert context.transaction_date is None
    assert context.reason == "date-missing"
```

- [ ] Resolve current transaction authorization/revision first, then eligible scoped confirmed facts through public owning contracts. Exactly one eligible attestation date establishes the transaction context; ambiguity/conflict/missing generates the existing lawyer-input path. Never choose a first/latest date or promote a natural-language hypothesis into canonical facts.
- [ ] Extend installed legal tool's closed schema with deliberate transaction/revision selection; persist metadata/source leads, both contexts and exact pins through the existing immutable message/result boundary. Add optional fields only when present to citation hashes so every pre-extension transcript hash remains identical. Use JSON storage's existing optional-field compatibility; add a migration only if a demonstrated owning persistence requirement cannot be served by the existing JSON contract, and include upgrade/downgrade/history refusal tests with it.
- [ ] Render source type, related authority links, official source URL, release identity, review state, known dates and unknown commencement in the shared Overview/Assistant source panel. Distinguish a metadata lead from a supporting passage. EN/SI labels use existing message keys/tokens, keyboard/focus behavior and safe official link handling. Transaction date missing leads to review/input, not an invented legal opinion or draft readiness.
- [ ] Run migrated actual API persistence/replay/auth/metering tests. Refresh/restart retains both date contexts and source metadata; same-key retries consume once; changed facts plus intentional repeated question produce a fresh request. Quarantine/current policy withholds replayed passages while preserving history/reference audit. Verify older transcripts and legacy source metadata remain readable.
- [ ] Run focused backend/static/OpenAPI gates, frontend `CI=true` coverage/typecheck/lint/build, and EN/SI browser mechanics with existing screenshot iteration cap. Preserve native logs and report measured limitations. Commit coupled API/UI/history changes as `feat(e8-7): show scoped statute and amendment date contexts` after explicit privacy/staging checks.

## Acceptance and final integration

- Each task receives an independent frozen-package review; original implementer resolves verified important findings in focused commits and fresh scoped rereview.
- Source publication occurs only after exact source owner/audience approval and a trusted signed release. Until then, source acquisition, code readiness and blocked runtime coverage are reported separately. No automated legal approval.
- Task 8 verifies this extension in the actual mixed-document API/browser journey with canonical facts, corrections, isolation, persistence and retry. It runs fresh repository-wide quality gates and the strongest integrated review once on the final source.
- Report every commit/objective map, source coverage measurement, extracted/empty-page warnings, exact native command/result, unresolved owner decisions and human acceptance separately. Never claim complete amendments, current consolidated law, or real-case legal applicability from synthetic tests.
