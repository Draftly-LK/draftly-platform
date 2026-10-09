from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_billing_service, get_request_context
from src.modules.billing.application.billing_service import BillingService
from src.modules.research.api.schemas import (
    ActionRead,
    ActionRequest,
    BranchRead,
    BranchRequest,
    ConversationListRead,
    ConversationRead,
    CreateConversationRequest,
    JobRead,
    MessageCitationRead,
    MessageClaimRead,
    MessageListRead,
    MessageRead,
    RenameConversationRequest,
    ScopeRead,
    SearchPassageRead,
    SearchRead,
    SearchRequest,
    SendMessageRequest,
)
from src.modules.research.application.service import CORPUS_VERSION, ResearchService
from src.modules.research.domain.models import AuthorityKind, SourceScope, authority_kind_of
from src.modules.research.infrastructure.orm import (
    ResearchAnswerRow,
    ResearchCitationRow,
    ResearchClaimRow,
    ResearchConversationRow,
    ResearchMessageRow,
)
from src.platform.db.idempotency import (
    IdempotencyKeyRequiredError,
    SqlIdempotencyStore,
    request_fingerprint,
)
from src.platform.db.session import get_db
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext


async def require_research_enabled(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> None:
    await billing.require_feature_or_raise(ctx.actor_id, "research.enabled")


router = APIRouter(
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(require_research_enabled)],
)
JobStateWire = Literal["queued", "running", "succeeded", "failed"]
ScopeTypeWire = Literal["library", "matter", "step", "document"]
MessageRoleWire = Literal["user", "assistant", "tool", "system"]


def get_service(session: AsyncSession = Depends(get_db)) -> ResearchService:
    from src.bootstrap import build_research_service

    return build_research_service(session)


def _conversation(row: ResearchConversationRow) -> ConversationRead:
    return ConversationRead(
        id=row.id,
        title=row.title,
        scope=ScopeRead(
            type=cast(ScopeTypeWire, row.scope_type),
            target_id=row.scope_target_id,
            matter_id=row.matter_id,
        ),
        active_branch_id=row.active_branch_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message(
    row: ResearchMessageRow,
    citations: list[MessageCitationRead] | None = None,
    claims: list[MessageClaimRead] | None = None,
) -> MessageRead:
    return MessageRead(
        id=row.id,
        conversation_id=row.conversation_id,
        branch_id=row.branch_id,
        parent_message_id=row.parent_message_id,
        edited_from_id=row.edited_from_id,
        role=cast(MessageRoleWire, row.role),
        content=row.content,
        answer_id=row.answer_id,
        citations=citations or [],
        claims=claims or [],
        created_at=row.created_at,
    )


@router.get("/conversations", response_model=ConversationListRead)
async def conversations(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    query: str | None = Query(default=None, max_length=256),
) -> ConversationListRead:
    return ConversationListRead(
        items=[_conversation(row) for row in await service.list_conversations(ctx, query)]
    )


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationRead:
    async with UnitOfWork(session):
        scope = await service.resolve_scope(ctx, body.scope.type, body.scope.target_id)
        row = await service.create_conversation(ctx, scope, body.title)
    return _conversation(row)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationRead:
    async with UnitOfWork(session):
        row = await service.rename_conversation(ctx, conversation_id, body.title)
    return _conversation(row)


@router.post("/conversations/{conversation_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(
    conversation_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a conversation from the list; its messages and answers are kept."""
    async with UnitOfWork(session):
        await service.archive_conversation(ctx, conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListRead)
async def messages(
    conversation_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
) -> MessageListRead:
    rows = await service.list_messages(ctx, conversation_id)
    answer_ids = [row.answer_id for row in rows if row.answer_id]
    citations_by_answer: dict[str, list[MessageCitationRead]] = {}
    claims_by_answer: dict[str, list[MessageClaimRead]] = {}
    if answer_ids:
        claims = list(
            (
                await service.db.execute(
                    select(ResearchClaimRow)
                    .where(
                        ResearchClaimRow.answer_id.in_(answer_ids),
                        ResearchClaimRow.user_id == ctx.actor_id,
                    )
                    .order_by(ResearchClaimRow.answer_id, ResearchClaimRow.position)
                )
            ).scalars()
        )
        answer_for_claim = {claim.id: claim.answer_id for claim in claims}
        if answer_for_claim:
            citation_rows = list(
                (
                    await service.db.execute(
                        select(ResearchCitationRow).where(
                            ResearchCitationRow.claim_id.in_(answer_for_claim),
                            ResearchCitationRow.user_id == ctx.actor_id,
                        )
                    )
                ).scalars()
            )
            cited_by_claim: dict[str, list[str]] = {}
            for citation in citation_rows:
                answer_id = answer_for_claim[citation.claim_id]
                kind = authority_kind_of(citation.authority_id, citation.authority_kind)
                cited_by_claim.setdefault(citation.claim_id, []).append(citation.authority_id)
                citations_by_answer.setdefault(answer_id, []).append(
                    MessageCitationRead(
                        id=citation.id,
                        source_id=citation.source_id,
                        authority_id=citation.authority_id,
                        passage=citation.passage,
                        page=citation.page,
                        # A case citation is an unverified research lead, always.
                        verified=citation.verified and kind != AuthorityKind.CASE,
                        authority_kind=kind.value,
                        title=citation.title,
                        reference=citation.reference,
                        source_url=citation.source_url,
                    )
                )
            for claim in claims:
                claims_by_answer.setdefault(claim.answer_id, []).append(
                    MessageClaimRead(text=claim.text, citation_ids=cited_by_claim.get(claim.id, []))
                )
    return MessageListRead(
        items=[
            _message(
                row,
                citations_by_answer.get(row.answer_id or ""),
                claims_by_answer.get(row.answer_id or ""),
            )
            for row in rows
        ]
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_message(
    conversation_id: str,
    body: SendMessageRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobRead:
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()
    route = "POST /api/v1/research/conversations/{id}/messages"
    store = SqlIdempotencyStore(session)
    fingerprint = request_fingerprint(
        {"conversationId": conversation_id, **body.model_dump(by_alias=True)}
    )
    replay = await store.find(
        user_id=ctx.actor_id, route=route, key=idempotency_key, request_hash=fingerprint
    )
    if replay is not None:
        return JobRead.model_validate(replay)
    async with UnitOfWork(session):
        job_id = f"rjob_{uuid.uuid4().hex}"
        reservation = await billing.reserve_usage(
            ctx.actor_id, "research_queries.monthly", 1, job_id
        )
        job = await service.submit(
            ctx,
            conversation_id,
            body.content,
            body.parent_message_id,
            job_id,
            sources=SourceScope(body.sources),
        )
        await billing.consume_usage(ctx.actor_id, reservation.id, 1)
        read = JobRead(job_id=job.id, state=cast(JobStateWire, job.state))
        await store.store(
            record_id=f"idem_{uuid.uuid4().hex[:16]}",
            user_id=ctx.actor_id,
            route=route,
            key=idempotency_key,
            request_hash=fingerprint,
            response=read.model_dump(by_alias=True),
        )
    return read


@router.post(
    "/messages/{message_id}/branch", response_model=BranchRead, status_code=status.HTTP_201_CREATED
)
async def branch_message(
    message_id: str,
    body: BranchRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BranchRead:
    del body
    async with UnitOfWork(session):
        row = await service.branch(ctx, message_id)
    return BranchRead(
        id=row.id,
        conversation_id=row.conversation_id,
        root_message_id=row.root_message_id or message_id,
        created_at=row.created_at,
    )


@router.get("/jobs/{job_id}", response_model=JobRead)
async def read_job(
    job_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
) -> JobRead:
    job = await service.job(ctx, job_id)
    return JobRead(
        job_id=job.id,
        state=cast(JobStateWire, job.state),
        failure_class=job.failure_class,
    )


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    rows = await service.events(ctx, job_id, after)

    async def emit() -> AsyncIterator[bytes]:
        for row in rows:
            payload = json.dumps(row.data, ensure_ascii=False, separators=(",", ":"))
            yield f"id: {row.sequence}\nevent: {row.event_type}\ndata: {payload}\n\n".encode()

    return StreamingResponse(
        emit(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/search", response_model=SearchRead, status_code=status.HTTP_202_ACCEPTED)
async def raw_search(
    body: SearchRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ResearchService, Depends(get_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SearchRead:
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()
    async with UnitOfWork(session):
        reservation = await billing.reserve_usage(
            ctx.actor_id,
            "research_queries.monthly",
            1,
            f"research-search:{idempotency_key}",
        )
        scope = await service.resolve_scope(ctx, body.scope.type, body.scope.target_id)
        result = await service.retrieval.search(body.query, scope, CORPUS_VERSION)
        await billing.consume_usage(ctx.actor_id, reservation.id, 1)
    return SearchRead(
        passages=[
            SearchPassageRead.model_validate(p, from_attributes=True) for p in result.passages
        ],
        degraded_channels=result.degraded_channels,
        corpus_version=result.corpus_version,
        source_release_version=result.source_release_version,
        authorities=result.authorities,
        coverage_gaps=result.coverage_gaps,
    )


@router.post("/actions", response_model=ActionRead)
async def record_action(
    body: ActionRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ActionRead:
    answer = (
        await session.execute(
            select(ResearchAnswerRow.id).where(
                ResearchAnswerRow.id == body.answer_id, ResearchAnswerRow.user_id == ctx.actor_id
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        raise NotFoundError()
    # Side effects remain explicitly separate; this endpoint records acceptance
    # of the command shape without pretending a matter/check mutation occurred.
    return ActionRead(id=f"raction_{uuid.uuid4().hex}", recorded=True)
