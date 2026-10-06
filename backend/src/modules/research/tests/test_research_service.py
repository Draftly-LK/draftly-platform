from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.modules.auth.domain.models import Role
from src.modules.research.application.service import (
    CORPUS_VERSION,
    ResearchService,
    title_from_question,
)
from src.modules.research.domain.models import (
    ComposedClaim,
    RetrievalPassage,
    Scope,
    ScopeType,
    SearchResult,
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
from src.modules.research.infrastructure.retrieval import NullLegalRetrieval
from src.modules.research.infrastructure.retrieval.statute_adapter import StatuteRetrievalAdapter
from src.platform.errors import NotFoundError
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


async def test_history_is_user_owned_and_unsupported_question_abstains() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: ResearchConversationRow.metadata.create_all(sync, tables=TABLES)
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await _exercise(session)
    await engine.dispose()


async def test_pinned_corpus_retrieves_registration_of_title_transfer_sections() -> None:
    result = await StatuteRetrievalAdapter().search(
        "What statutory authority governs a transfer under the Registration of Title Act?",
        Scope(type=ScopeType.LIBRARY),
        CORPUS_VERSION,
    )

    authority_ids = {passage.authority_id for passage in result.passages}
    assert {"SRC011:s39", "SRC011:s43", "SRC011:s45"} <= authority_ids
    assert result.degraded_channels == ["dense"]


async def test_grounded_answer_persists_only_retrieved_citations() -> None:
    class Retrieval:
        async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
            del query, scope
            return SearchResult(
                passages=[
                    RetrievalPassage(
                        source_id="SRC011",
                        authority_id="SRC011:s39",
                        title="Registration of Title Act",
                        reference="Section 39",
                        text="A disposition otherwise effected shall be void.",
                        page=13,
                        corpus_version=corpus_version,
                        verified=False,
                    )
                ]
            )

    class Composer:
        async def compose(
            self, question: str, passages: list[RetrievalPassage]
        ) -> tuple[ComposedClaim, ...]:
            del question, passages
            return (
                ComposedClaim(
                    text="A registered parcel must be transferred under the Act.",
                    citation_ids=("SRC011:s39", "FABRICATED:s1"),
                ),
            )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: ResearchConversationRow.metadata.create_all(sync, tables=TABLES)
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        owner = RequestContext(actor_id="user_owner", account_role=Role.REVIEWER)
        service = ResearchService(session, Retrieval(), Composer())
        scope = await service.resolve_scope(owner, "library", None)
        conversation = await service.create_conversation(owner, scope, "Transfer")
        await service.submit(owner, conversation.id, "What governs the transfer?", None)
        await session.commit()
        messages = await service.list_messages(owner, conversation.id)
        assert messages[-1].content == "A registered parcel must be transferred under the Act."
        citations = list((await session.execute(select(ResearchCitationRow))).scalars())
        assert [citation.authority_id for citation in citations] == ["SRC011:s39"]
    await engine.dispose()


def test_title_from_question_fits_one_list_row() -> None:
    assert title_from_question("  What   governs\n a transfer? ") == "What governs a transfer?"
    long = "Which provisions govern " + "a registered parcel transfer " * 6
    title = title_from_question(long)
    assert len(title) <= 80 and title.endswith("…") and not title.endswith(" …")
    assert title_from_question("   ") == "New research"


async def test_first_question_names_an_unnamed_conversation_only() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: ResearchConversationRow.metadata.create_all(sync, tables=TABLES)
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        owner = RequestContext(actor_id="user_owner", account_role=Role.REVIEWER)
        service = ResearchService(session, NullLegalRetrieval())
        scope = await service.resolve_scope(owner, "library", None)

        unnamed = await service.create_conversation(owner, scope, None)
        assert unnamed.title == "New research"
        await service.submit(owner, unnamed.id, "Double sale and prior registration?", None)
        await service.submit(owner, unnamed.id, "A later follow-up question", None)
        named = await service.create_conversation(owner, scope, "Chosen title")
        await service.submit(owner, named.id, "Some question", None)
        await session.commit()

        assert (await service.conversation(owner, unnamed.id)).title == (
            "Double sale and prior registration?"
        )
        assert (await service.conversation(owner, named.id)).title == "Chosen title"
    await engine.dispose()


async def _exercise(session: AsyncSession) -> None:
    owner = RequestContext(actor_id="user_owner", account_role=Role.REVIEWER)
    stranger = RequestContext(actor_id="user_stranger", account_role=Role.REVIEWER)
    service = ResearchService(session, NullLegalRetrieval())
    scope = await service.resolve_scope(owner, "library", None)
    conversation = await service.create_conversation(owner, scope, "Statutory question")
    job = await service.submit(owner, conversation.id, "What authority applies?", None)
    await session.commit()

    assert job.state == "succeeded"
    messages = await service.list_messages(owner, conversation.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].content == "research.insufficient.corpusUnavailable"
    assert [event.event_type for event in await service.events(owner, job.id, 0)] == [
        "abstention",
        "complete",
    ]

    try:
        await service.conversation(stranger, conversation.id)
    except NotFoundError:
        pass
    else:
        raise AssertionError("cross-user research history must be hidden with a 404")
