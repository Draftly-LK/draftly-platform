"""Case law in the research chat: source selection, grounding and unverified status."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.modules.auth.domain.models import Role
from src.modules.library.contracts import CaseCorpusUnavailableError, CaseCoverage
from src.modules.research.api.router import messages as list_messages_route
from src.modules.research.application.service import (
    CASE_RESULT_LIMIT,
    CORPUS_VERSION,
    ResearchService,
    case_passages,
)
from src.modules.research.domain.cases import CaseSearchResult, SimilarCase
from src.modules.research.domain.models import (
    AuthorityKind,
    ComposedClaim,
    RetrievalPassage,
    Scope,
    SearchResult,
    SourceScope,
    authority_kind_of,
)
from src.modules.research.infrastructure.orm import (
    ResearchAnswerRow,
    ResearchBranchRow,
    ResearchCitationRow,
    ResearchClaimRow,
    ResearchConversationRow,
    ResearchJobRow,
    ResearchMessageRow,
    ResearchStreamEventRow,
    ResearchToolCallRow,
)
from src.modules.research.infrastructure.retrieval.composer import (
    CASE_HEADER,
    STATUTE_SYSTEM,
    build_prompt,
    grounded_claims,
)
from src.platform.request_context import RequestContext

TABLES = [
    ResearchConversationRow.__table__,
    ResearchBranchRow.__table__,
    ResearchMessageRow.__table__,
    ResearchJobRow.__table__,
    ResearchStreamEventRow.__table__,
    ResearchToolCallRow.__table__,
    ResearchAnswerRow.__table__,
    ResearchClaimRow.__table__,
    ResearchCitationRow.__table__,
]
OWNER = RequestContext(actor_id="user_owner", account_role=Role.REVIEWER)
CASE_VERSION = "commonlii-v1-synthetic"
STATUTE_ID = "SRC011:s39"
CASE_ID = "commonlii-LKCA-1999-1"

STATUTE = RetrievalPassage(
    source_id="SRC011",
    authority_id=STATUTE_ID,
    title="Registration of Title Act",
    reference="Section 39",
    text="A disposition otherwise effected shall be void.",
    page=13,
    corpus_version=CORPUS_VERSION,
    verified=True,
)
SYNTHETIC_CASE = SimilarCase(
    case=None,
    id=CASE_ID,
    title="Synthetic Vendor v. Synthetic Purchaser",
    citation="[1999] LKCA 1",
    source_url="https://example.test/cases/LKCA/1999/1.html",
    score=0.5,
    matched_signals=["lexical"],
    reader_available=False,
    excerpt="Where a vendor without title sells, later-acquired title inures to the buyer.",
)


class StatuteRetrieval:
    def __init__(self, *, fail_if_called: bool = False) -> None:
        self.calls = 0
        self.fail_if_called = fail_if_called

    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
        del query, scope, corpus_version
        self.calls += 1
        assert not self.fail_if_called, "statutes were searched for a case-law-only question"
        return SearchResult(passages=[STATUTE], degraded_channels=["dense"])


class CaseSearch:
    def __init__(self, *, available: bool = True, items: list[SimilarCase] | None = None) -> None:
        self.calls: list[int] = []
        self.available = available
        self.items = [SYNTHETIC_CASE] if items is None else items

    async def search_cases(self, query: str, *, limit: int) -> CaseSearchResult:
        del query
        self.calls.append(limit)
        if not self.available:
            raise CaseCorpusUnavailableError()
        coverage = CaseCoverage(1, 1, 1, {"LKCA": 1}, 1999, 1999)
        outcome = "similar_cases_found" if self.items else "no_similar_cases"
        return CaseSearchResult(CASE_VERSION, coverage, self.items, outcome, [], "disabled")


class CitingComposer:
    """Cites whichever of the given ids were retrieved, plus one invented id."""

    def __init__(self, *cite: str) -> None:
        self.cite = cite
        self.seen: list[RetrievalPassage] = []

    async def compose(
        self, question: str, passages: list[RetrievalPassage]
    ) -> tuple[ComposedClaim, ...]:
        del question
        self.seen = list(passages)
        payload = {
            "claims": [
                {"text": f"Claim citing {cid}.", "citations": [cid, "INVENTED:s1"]}
                for cid in self.cite
            ]
            + [{"text": "Unsupported claim.", "citations": ["FABRICATED-CASE-9"]}]
        }
        return grounded_claims(payload, passages)


@asynccontextmanager
async def research_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: ResearchConversationRow.metadata.create_all(sync, tables=TABLES)
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def ask(
    session: AsyncSession, service: ResearchService, sources: SourceScope | None
) -> tuple[ResearchAnswerRow, list[ResearchCitationRow]]:
    scope = await service.resolve_scope(OWNER, "library", None)
    conversation = await service.create_conversation(OWNER, scope, "Synthetic question")
    if sources is None:
        await service.submit(OWNER, conversation.id, "Who holds title after a resale?", None)
    else:
        await service.submit(
            OWNER, conversation.id, "Who holds title after a resale?", None, sources=sources
        )
    await session.commit()
    answer = (await session.execute(select(ResearchAnswerRow))).scalars().one()
    citations = list((await session.execute(select(ResearchCitationRow))).scalars())
    return answer, citations


async def test_default_is_statutes_only_and_never_calls_case_search() -> None:
    async with research_session() as session:
        statutes, cases = StatuteRetrieval(), CaseSearch()
        service = ResearchService(session, statutes, CitingComposer(STATUTE_ID), cases)
        answer, citations = await ask(session, service, None)

        assert statutes.calls == 1
        assert cases.calls == []
        assert answer.kind == "grounded"
        assert answer.corpus_version == CORPUS_VERSION
        assert [(c.authority_id, c.authority_kind, c.verified) for c in citations] == [
            (STATUTE_ID, "statute", True)
        ]
        assert (citations[0].title, citations[0].reference) == (
            "Registration of Title Act",
            "Section 39",
        )


async def test_case_law_only_grounds_claims_in_unverified_case_evidence() -> None:
    async with research_session() as session:
        statutes, cases = StatuteRetrieval(fail_if_called=True), CaseSearch()
        service = ResearchService(session, statutes, CitingComposer(CASE_ID), cases)
        answer, citations = await ask(session, service, SourceScope.CASES)

        assert cases.calls == [CASE_RESULT_LIMIT]
        assert answer.kind == "grounded"
        assert answer.corpus_version == CASE_VERSION
        [citation] = citations
        assert citation.authority_kind == "case"
        assert citation.verified is False
        assert citation.title == "Synthetic Vendor v. Synthetic Purchaser"
        assert citation.reference == "[1999] LKCA 1"
        assert citation.source_url == "https://example.test/cases/LKCA/1999/1.html"
        assert citation.passage == SYNTHETIC_CASE.excerpt


async def test_all_sources_combine_statute_and_case_evidence_in_one_answer() -> None:
    async with research_session() as session:
        composer = CitingComposer(STATUTE_ID, CASE_ID)
        service = ResearchService(session, StatuteRetrieval(), composer, CaseSearch())
        answer, citations = await ask(session, service, SourceScope.ALL)

        assert {p.kind for p in composer.seen} == {AuthorityKind.STATUTE, AuthorityKind.CASE}
        assert answer.corpus_version == f"{CORPUS_VERSION}+{CASE_VERSION}"
        kinds = {(c.authority_id, c.authority_kind, c.verified) for c in citations}
        assert kinds == {(STATUTE_ID, "statute", True), (CASE_ID, "case", False)}
        claims = list((await session.execute(select(ResearchClaimRow))).scalars())
        # The claim citing only an invented case id is dropped, as before.
        assert len(claims) == 2


async def test_invented_citations_are_dropped_for_statutes_and_cases() -> None:
    passages = [STATUTE, *case_passages([SYNTHETIC_CASE], CASE_VERSION)]
    claims = grounded_claims(
        {
            "claims": [
                {"text": "Mixed.", "citations": [CASE_ID, "commonlii-LKSC-2001-99"]},
                {"text": "Only invented.", "citations": ["SRC999:s1", "commonlii-LKCA-1800-1"]},
                {"text": "", "citations": [STATUTE_ID]},
                "not a claim",
            ]
        },
        passages,
    )
    assert claims == (ComposedClaim(text="Mixed.", citation_ids=(CASE_ID.upper(),)),)
    assert grounded_claims(None, passages) == ()


async def test_all_sources_still_answer_from_statutes_when_case_search_is_down() -> None:
    async with research_session() as session:
        service = ResearchService(
            session, StatuteRetrieval(), CitingComposer(STATUTE_ID), CaseSearch(available=False)
        )
        answer, citations = await ask(session, service, SourceScope.ALL)

        assert answer.kind == "grounded"
        assert answer.corpus_version == CORPUS_VERSION
        assert [c.authority_kind for c in citations] == ["statute"]
        event = (await session.execute(select(ResearchStreamEventRow))).scalars().first()
        assert event is not None
        assert "case-law" in event.data["degradedChannels"]


async def test_case_law_only_abstains_safely_when_case_search_is_down() -> None:
    async with research_session() as session:
        composer = CitingComposer(CASE_ID)
        service = ResearchService(
            session, StatuteRetrieval(fail_if_called=True), composer, CaseSearch(available=False)
        )
        answer, citations = await ask(session, service, SourceScope.CASES)

        assert answer.kind == "insufficient-authority"
        assert answer.reason_key == "research.insufficient.caseLawUnavailable"
        assert citations == []
        assert composer.seen == []  # nothing to compose from, so the model is not called


async def test_case_law_only_with_no_similar_cases_is_insufficient_authority() -> None:
    async with research_session() as session:
        service = ResearchService(
            session, StatuteRetrieval(), CitingComposer(CASE_ID), CaseSearch(items=[])
        )
        answer, _ = await ask(session, service, SourceScope.CASES)
        assert answer.kind == "insufficient-authority"
        assert answer.reason_key == "research.insufficient.corpusUnavailable"


def test_case_evidence_is_never_verified_and_needs_an_excerpt() -> None:
    blank = SimilarCase(
        case=None,
        id="commonlii-LKCA-1999-2",
        title="No excerpt",
        citation="",
        source_url="",
        score=0.1,
        matched_signals=["graph"],
        reader_available=False,
        excerpt="   ",
    )
    [passage] = case_passages([SYNTHETIC_CASE, blank], CASE_VERSION)
    assert passage.verified is False
    assert passage.kind == AuthorityKind.CASE
    assert passage.page == 0


def test_older_citations_without_a_recorded_kind_are_read_by_id() -> None:
    assert authority_kind_of("SRC011:s39", None) == AuthorityKind.STATUTE
    assert authority_kind_of("commonlii-LKSC-2001-3", None) == AuthorityKind.CASE
    assert authority_kind_of("SRC011:s39", "case") == AuthorityKind.CASE


def test_statute_only_evidence_keeps_the_original_prompt() -> None:
    prompt, system = build_prompt("Q?", [STATUTE])
    assert prompt.startswith("Answer the question using only the statutory passages below.")
    assert system == STATUTE_SYSTEM
    assert CASE_HEADER not in prompt


def test_case_evidence_is_labelled_as_an_unverified_research_lead() -> None:
    passages = [STATUTE, *case_passages([SYNTHETIC_CASE], CASE_VERSION)]
    prompt, system = build_prompt("Q?", passages)
    assert "[STATUTE]" in prompt
    assert f"{CASE_HEADER} [{CASE_ID}]" in prompt
    assert "research lead" in system and "Never present case law as verified" in system


async def test_messages_report_claims_and_citation_kinds_to_the_client() -> None:
    async with research_session() as session:
        service = ResearchService(
            session, StatuteRetrieval(), CitingComposer(STATUTE_ID, CASE_ID), CaseSearch()
        )
        scope = await service.resolve_scope(OWNER, "library", None)
        conversation = await service.create_conversation(OWNER, scope, "Synthetic")
        await service.submit(OWNER, conversation.id, "Q?", None, sources=SourceScope.ALL)
        await session.commit()

        read = await list_messages_route(conversation.id, OWNER, service)
        assistant = read.items[-1]
        assert [claim.citation_ids for claim in assistant.claims] == [[STATUTE_ID], [CASE_ID]]
        by_id = {c.authority_id: c for c in assistant.citations}
        assert by_id[CASE_ID].authority_kind == "case"
        assert by_id[CASE_ID].verified is False
        assert by_id[STATUTE_ID].authority_kind == "statute"
        assert by_id[STATUTE_ID].title == "Registration of Title Act"
