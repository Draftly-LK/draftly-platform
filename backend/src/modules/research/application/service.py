from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.document.infrastructure.orm import SourceFileRow
from src.modules.matter.infrastructure.orm import MatterRow
from src.modules.research.case_ports import CaseSearchPort
from src.modules.research.domain.cases import SimilarCase
from src.modules.research.domain.models import (
    AuthorityKind,
    ComposedClaim,
    RetrievalPassage,
    Scope,
    ScopeType,
    SearchResult,
    SourceScope,
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
)
from src.modules.research.ports import GroundedAnswerComposerPort, LegalRetrievalPort
from src.modules.task.infrastructure.orm import ChecklistItemRow
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext

CORPUS_VERSION = "statutes-bm25-v1:8a7f096671b28cf0"
# Placeholder until the first question names the conversation. The research_0002
# migration backfills earlier conversations by the same rule.
DEFAULT_TITLE = "New research"
TITLE_LENGTH = 80
# A handful of case leads per question: enough to ground a claim, few enough to
# keep the evidence the model reads focused.
CASE_RESULT_LIMIT = 5
CASE_SOURCE_ID = "case-law"
CASE_CHANNEL = "case-law"


def case_passages(result_items: list[SimilarCase], corpus_version: str) -> list[RetrievalPassage]:
    """Similar-case hits as research evidence: the excerpt only, never verified."""
    passages: list[RetrievalPassage] = []
    for item in result_items:
        excerpt = " ".join(str(item.excerpt or "").split())
        if not excerpt:
            continue  # nothing to ground a claim in
        passages.append(
            RetrievalPassage(
                source_id=CASE_SOURCE_ID,
                authority_id=item.id,
                title=item.title,
                reference=item.citation,
                text=excerpt,
                page=0,
                corpus_version=corpus_version,
                verified=False,
                kind=AuthorityKind.CASE,
                source_url=item.source_url or None,
            )
        )
    return passages


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def title_from_question(content: str) -> str:
    """The first question, on one line, cut at a word boundary to fit a list row."""
    text = " ".join(content.split())
    if len(text) <= TITLE_LENGTH:
        return text or DEFAULT_TITLE
    cut = text[: TITLE_LENGTH - 1].rsplit(" ", 1)[0] or text[: TITLE_LENGTH - 1]
    return cut + "…"


class ResearchService:
    """Owns PostgreSQL history and fail-closed grounded answer orchestration."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval: LegalRetrievalPort,
        composer: GroundedAnswerComposerPort | None = None,
        cases: CaseSearchPort | None = None,
    ) -> None:
        self.db = session
        self.retrieval = retrieval
        self.composer = composer
        # The bounded similar-case port, called directly: the metered
        # CaseResearchService would charge a second research query.
        self.cases = cases

    async def _search_cases(self, content: str) -> tuple[list[RetrievalPassage], str | None]:
        """Case evidence and its corpus version; ([], None) when case search failed."""
        if self.cases is None:
            return [], None
        try:
            result = await self.cases.search_cases(content, limit=CASE_RESULT_LIMIT)
        except Exception:  # an unavailable case service must not fail the question
            return [], None
        return case_passages(result.items, result.corpus_version), result.corpus_version

    async def retrieve(
        self, content: str, scope: Scope, sources: SourceScope
    ) -> tuple[SearchResult, list[str], bool]:
        """Evidence for the selected sources, searched concurrently.

        Returns the combined result, the corpus versions searched, and whether
        case search was requested but unavailable.
        """
        want_statutes = sources in (SourceScope.STATUTES, SourceScope.ALL)
        want_cases = sources in (SourceScope.CASES, SourceScope.ALL)

        async def no_statutes() -> SearchResult:
            return SearchResult()

        async def no_cases() -> tuple[list[RetrievalPassage], str | None]:
            return [], None

        statutes, (cases, case_version) = await asyncio.gather(
            self.retrieval.search(content, scope, CORPUS_VERSION)
            if want_statutes
            else no_statutes(),
            self._search_cases(content) if want_cases else no_cases(),
        )
        case_unavailable = want_cases and case_version is None
        versions = ([CORPUS_VERSION] if want_statutes else []) + (
            [case_version] if case_version else []
        )
        degraded = list(statutes.degraded_channels) + ([CASE_CHANNEL] if case_unavailable else [])
        return (
            SearchResult(passages=[*statutes.passages, *cases], degraded_channels=degraded),
            versions,
            case_unavailable,
        )

    async def resolve_scope(
        self, ctx: RequestContext, scope_type: str, target_id: str | None
    ) -> Scope:
        kind = ScopeType(scope_type)
        if kind is ScopeType.LIBRARY:
            if target_id is not None:
                raise NotFoundError()
            return Scope(kind)
        if not target_id:
            raise NotFoundError()
        matter_id: str | None = None
        if kind is ScopeType.MATTER:
            matter_id = (
                await self.db.execute(
                    select(MatterRow.id).where(
                        MatterRow.id == target_id, MatterRow.user_id == ctx.actor_id
                    )
                )
            ).scalar_one_or_none()
        elif kind is ScopeType.STEP:
            matter_id = (
                await self.db.execute(
                    select(ChecklistItemRow.matter_id).where(
                        ChecklistItemRow.id == target_id, ChecklistItemRow.user_id == ctx.actor_id
                    )
                )
            ).scalar_one_or_none()
        else:
            matter_id = (
                await self.db.execute(
                    select(SourceFileRow.matter_id).where(
                        SourceFileRow.id == target_id, SourceFileRow.user_id == ctx.actor_id
                    )
                )
            ).scalar_one_or_none()
        if matter_id is None:
            raise NotFoundError()
        return Scope(kind, target_id, str(matter_id))

    async def create_conversation(
        self, ctx: RequestContext, scope: Scope, title: str | None
    ) -> ResearchConversationRow:
        conversation_id, branch_id = _id("rconv"), _id("rbranch")
        row = ResearchConversationRow(
            id=conversation_id,
            user_id=ctx.actor_id,
            matter_id=scope.matter_id,
            scope_type=scope.type.value,
            scope_target_id=scope.target_id,
            title=(title or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
            active_branch_id=branch_id,
        )
        self.db.add(row)
        # Flush the parent first. SQLAlchemy has no ORM relationship here to infer
        # insert ordering from, and PostgreSQL enforces the branch FK immediately.
        await self.db.flush()
        self.db.add(
            ResearchBranchRow(
                id=branch_id,
                conversation_id=conversation_id,
                user_id=ctx.actor_id,
                matter_id=scope.matter_id,
                root_message_id=None,
                created_by=ctx.actor_id,
            )
        )
        await self.db.flush()
        return row

    async def list_conversations(
        self, ctx: RequestContext, query: str | None
    ) -> list[ResearchConversationRow]:
        stmt = select(ResearchConversationRow).where(
            ResearchConversationRow.user_id == ctx.actor_id,
            ResearchConversationRow.archived_at.is_(None),
        )
        if query:
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ResearchConversationRow.title.ilike(term),
                    ResearchConversationRow.id.in_(
                        select(ResearchMessageRow.conversation_id).where(
                            ResearchMessageRow.user_id == ctx.actor_id,
                            ResearchMessageRow.content.ilike(term),
                        )
                    ),
                )
            )
        return list(
            (
                await self.db.execute(stmt.order_by(ResearchConversationRow.updated_at.desc()))
            ).scalars()
        )

    async def conversation(
        self, ctx: RequestContext, conversation_id: str
    ) -> ResearchConversationRow:
        row = (
            await self.db.execute(
                select(ResearchConversationRow).where(
                    ResearchConversationRow.id == conversation_id,
                    ResearchConversationRow.user_id == ctx.actor_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError()
        return row

    async def rename_conversation(
        self, ctx: RequestContext, conversation_id: str, title: str
    ) -> ResearchConversationRow:
        row = await self.conversation(ctx, conversation_id)
        row.title = " ".join(title.split())[:256] or row.title
        await self.db.flush()
        # updated_at is set by the database on update; load it now so the caller
        # can read it without a lazy load outside the async context.
        await self.db.refresh(row)
        return row

    async def archive_conversation(self, ctx: RequestContext, conversation_id: str) -> None:
        """Hide a conversation from the list. Messages and answers are kept."""
        row = await self.conversation(ctx, conversation_id)
        if row.archived_at is None:
            row.archived_at = datetime.now(UTC)
            await self.db.flush()

    async def list_messages(
        self, ctx: RequestContext, conversation_id: str
    ) -> list[ResearchMessageRow]:
        await self.conversation(ctx, conversation_id)
        stmt = (
            select(ResearchMessageRow)
            .where(
                ResearchMessageRow.conversation_id == conversation_id,
                ResearchMessageRow.user_id == ctx.actor_id,
            )
            .order_by(ResearchMessageRow.sequence)
        )
        return list((await self.db.execute(stmt)).scalars())

    async def submit(
        self,
        ctx: RequestContext,
        conversation_id: str,
        content: str,
        parent_message_id: str | None,
        job_id: str | None = None,
        sources: SourceScope = SourceScope.STATUTES,
    ) -> ResearchJobRow:
        conversation = await self.conversation(ctx, conversation_id)
        if parent_message_id:
            parent = (
                await self.db.execute(
                    select(ResearchMessageRow.id).where(
                        ResearchMessageRow.id == parent_message_id,
                        ResearchMessageRow.conversation_id == conversation_id,
                        ResearchMessageRow.user_id == ctx.actor_id,
                    )
                )
            ).scalar_one_or_none()
            if parent is None:
                raise NotFoundError()
        user_message_id, job_id = _id("rmsg"), job_id or _id("rjob")
        last_sequence = (
            await self.db.execute(
                select(func.max(ResearchMessageRow.sequence)).where(
                    ResearchMessageRow.conversation_id == conversation_id
                )
            )
        ).scalar_one_or_none() or 0
        if last_sequence == 0 and conversation.title == DEFAULT_TITLE:
            conversation.title = title_from_question(content)
        user_message = ResearchMessageRow(
            id=user_message_id,
            conversation_id=conversation_id,
            branch_id=conversation.active_branch_id,
            user_id=ctx.actor_id,
            matter_id=conversation.matter_id,
            sequence=last_sequence + 1,
            parent_message_id=parent_message_id,
            role="user",
            content=content,
        )
        job = ResearchJobRow(
            id=job_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            user_id=ctx.actor_id,
            matter_id=conversation.matter_id,
            state="queued",
            corpus_version=CORPUS_VERSION,
        )
        self.db.add_all([user_message, job])
        await self.db.flush()
        scope = Scope(
            ScopeType(conversation.scope_type), conversation.scope_target_id, conversation.matter_id
        )
        result, versions, case_unavailable = await self.retrieve(content, scope, sources)
        corpus_version = "+".join(versions) or CORPUS_VERSION
        job.corpus_version = corpus_version
        answer_id, assistant_id = _id("rans"), _id("rmsg")
        composed: tuple[ComposedClaim, ...] = ()
        if result.passages and self.composer is not None:
            try:
                composed = await self.composer.compose(content, result.passages)
            except Exception:  # provider failure must degrade to a grounded abstention
                composed = ()
        reason = None
        if not composed:
            if sources == SourceScope.CASES and case_unavailable:
                reason = "research.insufficient.caseLawUnavailable"
            elif not result.passages:
                reason = "research.insufficient.corpusUnavailable"
            else:
                reason = "research.insufficient.noSupportedClaims"
        answer = ResearchAnswerRow(
            id=answer_id,
            user_id=ctx.actor_id,
            matter_id=conversation.matter_id,
            conversation_id=conversation_id,
            message_id=assistant_id,
            kind="grounded" if composed else "insufficient-authority",
            question=content,
            corpus_version=corpus_version,
            reason_key=reason,
            suggested_action_key="research.insufficient.refineOrRequestReview",
        )
        assistant = ResearchMessageRow(
            id=assistant_id,
            conversation_id=conversation_id,
            branch_id=conversation.active_branch_id,
            user_id=ctx.actor_id,
            matter_id=conversation.matter_id,
            sequence=last_sequence + 2,
            parent_message_id=user_message_id,
            role="assistant",
            content="\n\n".join(claim.text for claim in composed) if composed else str(reason),
            answer_id=answer_id,
        )
        now = datetime.now(UTC)
        job.state, job.finished_at = "succeeded", now
        self.db.add_all([answer, assistant])
        await self.db.flush()
        passages = {passage.authority_id.upper(): passage for passage in result.passages}
        for position, claim in enumerate(composed, start=1):
            claim_row = ResearchClaimRow(
                id=_id("rclaim"),
                answer_id=answer_id,
                user_id=ctx.actor_id,
                matter_id=conversation.matter_id,
                position=position,
                text=claim.text,
            )
            self.db.add(claim_row)
            await self.db.flush()
            for citation_id in claim.citation_ids:
                passage = passages.get(citation_id.upper())
                if passage is None:
                    continue
                self.db.add(
                    ResearchCitationRow(
                        id=_id("rcite"),
                        claim_id=claim_row.id,
                        user_id=ctx.actor_id,
                        matter_id=conversation.matter_id,
                        source_id=passage.source_id,
                        authority_id=passage.authority_id,
                        corpus_version=passage.corpus_version,
                        passage=passage.text,
                        page=passage.page,
                        # Case law is never verified here, whatever the evidence said.
                        verified=passage.verified and passage.kind != AuthorityKind.CASE,
                        authority_kind=passage.kind.value,
                        title=passage.title[:512] or None,
                        reference=passage.reference[:256] or None,
                        source_url=(passage.source_url or "")[:1024] or None,
                    )
                )
        event_type = "grounded-answer" if composed else "abstention"
        self.db.add_all(
            [
                ResearchStreamEventRow(
                    id=_id("revt"),
                    job_id=job_id,
                    user_id=ctx.actor_id,
                    sequence=1,
                    event_type=event_type,
                    data={
                        "answerId": answer_id,
                        "reasonKey": reason,
                        "degradedChannels": result.degraded_channels,
                    },
                ),
                ResearchStreamEventRow(
                    id=_id("revt"),
                    job_id=job_id,
                    user_id=ctx.actor_id,
                    sequence=2,
                    event_type="complete",
                    data={"jobId": job_id, "state": "succeeded"},
                ),
            ]
        )
        await self.db.flush()
        return job

    async def job(self, ctx: RequestContext, job_id: str) -> ResearchJobRow:
        row = (
            await self.db.execute(
                select(ResearchJobRow).where(
                    ResearchJobRow.id == job_id, ResearchJobRow.user_id == ctx.actor_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError()
        return row

    async def events(
        self, ctx: RequestContext, job_id: str, after: int
    ) -> list[ResearchStreamEventRow]:
        await self.job(ctx, job_id)
        stmt = (
            select(ResearchStreamEventRow)
            .where(
                ResearchStreamEventRow.job_id == job_id,
                ResearchStreamEventRow.user_id == ctx.actor_id,
                ResearchStreamEventRow.sequence > after,
            )
            .order_by(ResearchStreamEventRow.sequence)
        )
        return list((await self.db.execute(stmt)).scalars())

    async def branch(self, ctx: RequestContext, message_id: str) -> ResearchBranchRow:
        message = (
            await self.db.execute(
                select(ResearchMessageRow).where(
                    ResearchMessageRow.id == message_id, ResearchMessageRow.user_id == ctx.actor_id
                )
            )
        ).scalar_one_or_none()
        if message is None:
            raise NotFoundError()
        conversation = await self.conversation(ctx, message.conversation_id)
        branch = ResearchBranchRow(
            id=_id("rbranch"),
            conversation_id=message.conversation_id,
            user_id=ctx.actor_id,
            matter_id=conversation.matter_id,
            root_message_id=message.id,
            created_by=ctx.actor_id,
        )
        self.db.add(branch)
        conversation.active_branch_id = branch.id
        await self.db.flush()
        return branch
