"""Matter agent API router.

```text
GET  /api/v1/matters/{id}/agent                        session, provisioned lazily
GET  /api/v1/matters/{id}/agent/messages               transcript, from Neon
POST /api/v1/matters/{id}/agent/messages               append + start a turn
GET  /api/v1/matters/{id}/agent/conversations          audit segments
POST /api/v1/matters/{id}/agent/conversations          archive + start fresh
GET  /api/v1/agent-jobs/{jobId}                        job status
POST /api/v1/matters/{id}/agent/actions/{id}/confirm   execute a card
POST /api/v1/matters/{id}/agent/actions/{id}/reject    refuse a card, audited
```

Every route derives tenancy from ``RequestContext``. A matter the caller does
not own produces the same 404 as a matter that does not exist
(``security-model.md`` §5), so no route confirms that a foreign matter is real.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context
from src.modules.matter_agent.api.schemas import (
    CitationRead,
    ConversationRead,
    JobRead,
    MessageListRead,
    MessageRead,
    PageInfo,
    PendingActionRead,
    RejectActionRequest,
    SendMessageRequest,
    SessionRead,
)
from src.modules.matter_agent.application.agent_service import AgentService
from src.modules.matter_agent.domain.models import (
    AgentConversation,
    AgentMessage,
    AgentSession,
    PendingAction,
)
from src.modules.matter_agent.infrastructure.stream_repository import SqlStreamEventRepository
from src.platform.db.idempotency import (
    IdempotencyKeyRequiredError,
    SqlIdempotencyStore,
    request_fingerprint,
)
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DraftlyError
from src.platform.pagination import Cursor, decode_cursor, encode_cursor, normalise_limit
from src.platform.request_context import RequestContext

router = APIRouter(tags=["matter-agent"])

_SEND_MESSAGE_ROUTE = "POST /matters/{matterId}/agent/messages"
_RETRY_ROUTE = "POST /matters/{matterId}/agent/jobs/{jobId}/retry"


def _parse_last_event_id(value: str | None) -> int:
    """A malformed resume token replays from the start rather than failing."""
    if value is None or not value.strip().isdigit():
        return 0
    return int(value.strip())


def _sse_frame(sequence: int, event_type: str, data: dict[str, object]) -> bytes:
    """One SSE frame. ``id`` is omitted on the terminal frame so a reconnect
    does not resume past it."""
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    lines = []
    if sequence:
        lines.append(f"id: {sequence}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {body}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def get_agent_service(session: AsyncSession = Depends(get_db)) -> AgentService:
    """Request-scoped service; every repository is bound to this session."""
    from src.bootstrap import build_agent_service

    service: AgentService = build_agent_service(session)
    return service


def _to_session_read(session: AgentSession) -> SessionRead:
    return SessionRead(
        id=session.id,
        matter_id=session.matter_id,
        state=session.state.value,
        model_version=session.model_version,
        prompt_version=session.prompt_version,
        created_at=session.created_at,
        updated_at=session.updated_at,
        active_conversation_id=session.active_conversation_id,
    )


def _to_message_read(message: AgentMessage) -> MessageRead:
    return MessageRead(
        id=message.id,
        sequence=message.sequence,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        job_id=message.job_id,
        pending_action_id=message.pending_action_id,
        conversation_id=message.conversation_id,
        citations=[
            CitationRead(
                source_id=item.source_id,
                source_type=item.source_type,
                label=item.label,
                verification_status=item.verification_status,
                locator=item.locator,
                source_file_id=item.source_file_id,
                page=item.page,
                version=item.version,
                transaction_id=item.transaction_id,
                subject_id=item.subject_id,
                passage=item.passage,
                corpus_version=item.corpus_version,
            )
            for item in message.citations
        ],
    )


def _to_conversation_read(conversation: AgentConversation) -> ConversationRead:
    return ConversationRead(
        id=conversation.id,
        state=conversation.state.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_action_read(action: PendingAction) -> PendingActionRead:
    return PendingActionRead(
        id=action.id,
        action_kind=action.action_kind,
        arguments={k: v for k, v in action.arguments.items() if not k.startswith("_")},
        result=action.result,
        reason_code=action.reason_code,
        target_ref=action.target_ref,
        target_version=action.target_version,
        state=action.state.value,
        expires_at=action.expires_at,
        created_at=action.created_at,
    )


@router.get("/matters/{matter_id}/agent", response_model=SessionRead)
async def read_session(
    matter_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SessionRead:
    """Return the matter's session, provisioning it on first use.

    Uses the unit of work because a first read creates a row and its audit
    event, and those commit together.
    """
    async with uow:
        return _to_session_read(await service.get_or_create_session(ctx, matter_id))


@router.get("/matters/{matter_id}/agent/messages", response_model=MessageListRead)
async def list_messages(
    matter_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    cursor: Annotated[str | None, Query()] = None,
) -> MessageListRead:
    """The authoritative transcript. Served from Neon, never from a provider."""
    page_limit = normalise_limit(limit)
    decoded: Cursor | None = decode_cursor(cursor) if cursor else None
    async with uow:
        page = await service.list_messages(ctx, matter_id, limit=page_limit, cursor=decoded)
    return MessageListRead(
        items=[_to_message_read(message) for message in page.items],
        page=PageInfo(
            next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
            has_more=page.has_more,
            limit=page_limit,
        ),
    )


@router.get(
    "/matters/{matter_id}/agent/conversations",
    response_model=list[ConversationRead],
)
async def list_conversations(
    matter_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[ConversationRead]:
    async with uow:
        rows = await service.list_conversations(ctx, matter_id)
    return [_to_conversation_read(item) for item in rows]


@router.post(
    "/matters/{matter_id}/agent/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def start_conversation(
    matter_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ConversationRead:
    async with uow:
        created = await service.start_conversation(ctx, matter_id)
    return _to_conversation_read(created)


@router.post(
    "/matters/{matter_id}/agent/messages",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(
    matter_id: str,
    body: SendMessageRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobRead:
    """Append the user's message and enqueue the turn.

    Returns a job immediately; the request never waits on the model
    (``api-conventions.md`` §6). The message row, the job row and the outbox
    entry commit in one transaction, so a queued turn always has a message
    behind it and a rollback leaves neither.

    A replayed ``Idempotency-Key`` returns the first job rather than starting a
    second turn, so a double-submitted message cannot be answered twice.
    """
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()

    store = SqlIdempotencyStore(session)
    fingerprint = request_fingerprint({"matterId": matter_id, **body.model_dump(by_alias=True)})
    async with UnitOfWork(session):
        await service.lock(ctx, matter_id)
        await service.get_or_create_session(ctx, matter_id)
        replayed = await store.find(
            user_id=ctx.actor_id,
            route=_SEND_MESSAGE_ROUTE,
            key=idempotency_key,
            request_hash=fingerprint,
        )
        if replayed is not None:
            return JobRead.model_validate(replayed)
        job = await service.start_turn(ctx, matter_id, content=body.content)
        read = JobRead(job_id=job.job_id, state=job.state.value, tool_call_count=0)
        await store.store(
            record_id=f"idem_{uuid.uuid4().hex[:16]}",
            user_id=ctx.actor_id,
            route=_SEND_MESSAGE_ROUTE,
            key=idempotency_key,
            request_hash=fingerprint,
            response=read.model_dump(by_alias=True),
        )
    return read


@router.get("/matters/{matter_id}/agent/latest-job", response_model=JobRead | None)
async def latest_job(
    matter_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> JobRead | None:
    async with uow:
        job = await service.latest_job(ctx, matter_id)
    return (
        JobRead(
            job_id=job.job_id,
            state=job.state.value,
            tool_call_count=job.tool_call_count,
            failure_class=job.failure_class,
        )
        if job
        else None
    )


@router.get("/agent-jobs/{job_id}", response_model=JobRead)
async def read_job(
    job_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> JobRead:
    """Job status. A job belonging to another user is a 404, not a 403."""
    job = await service.read_job(ctx, job_id)
    return JobRead(
        job_id=job.job_id,
        state=job.state.value,
        tool_call_count=job.tool_call_count,
        failure_class=job.failure_class,
    )


@router.post(
    "/matters/{matter_id}/agent/jobs/{job_id}/retry",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_job(
    matter_id: str,
    job_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobRead:
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()
    # Authorize before reading an idempotency response for this destination.
    await service.get_or_create_session(ctx, matter_id)
    await service.read_job(ctx, job_id)
    store = SqlIdempotencyStore(session)
    fingerprint = request_fingerprint({"matterId": matter_id, "jobId": job_id})
    replayed = await store.find(
        user_id=ctx.actor_id, route=_RETRY_ROUTE, key=idempotency_key, request_hash=fingerprint
    )
    if replayed is not None:
        return JobRead.model_validate(replayed)
    async with UnitOfWork(session):
        job = await service.retry_turn(ctx, matter_id, job_id)
        # Another request with this same key can finish while we wait for the
        # source job's row lock. Recheck under that lock before inserting.
        replayed = await store.find(
            user_id=ctx.actor_id, route=_RETRY_ROUTE, key=idempotency_key, request_hash=fingerprint
        )
        if replayed is not None:
            return JobRead.model_validate(replayed)
        read = JobRead(
            job_id=job.job_id,
            state=job.state.value,
            tool_call_count=job.tool_call_count,
            failure_class=job.failure_class,
        )
        await store.store(
            record_id=f"idem_{uuid.uuid4().hex[:16]}",
            user_id=ctx.actor_id,
            route=_RETRY_ROUTE,
            key=idempotency_key,
            request_hash=fingerprint,
            response=read.model_dump(by_alias=True),
        )
    return read


@router.get("/agent-jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    session: Annotated[AsyncSession, Depends(get_db)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Resumable server-sent events for one turn.

    Presentation state only: the job row is authoritative and polling
    ``GET /agent-jobs/{id}`` remains a complete alternative
    (``api-conventions.md`` §6). ``Last-Event-ID`` resumes from the next
    sequence, so a dropped connection costs no frames.

    A job owned by another user yields no events, not a 403 — the same
    existence hiding the rest of the surface uses.
    """
    job = await service.read_job(ctx, job_id)
    after = _parse_last_event_id(last_event_id)
    events = SqlStreamEventRepository(session)
    frames = await events.since(job_id=job_id, user_id=ctx.actor_id, after_sequence=after)

    async def emit() -> AsyncIterator[bytes]:
        for sequence, event_type, data in frames:
            yield _sse_frame(sequence, event_type, data)
        # A terminal frame so a client that connected late still learns the
        # outcome without falling back to a poll.
        yield _sse_frame(
            0,
            "job-state",
            {
                "jobId": job.job_id,
                "state": job.state.value,
                "toolCallCount": job.tool_call_count,
                "failureClass": job.failure_class,
            },
        )

    return StreamingResponse(
        emit(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/matters/{matter_id}/agent/actions/{action_id}", response_model=PendingActionRead)
async def read_action(
    matter_id: str,
    action_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> PendingActionRead:
    async with uow:
        return _to_action_read(await service.read_action(ctx, matter_id, action_id))


@router.post(
    "/matters/{matter_id}/agent/actions/{action_id}/confirm",
    response_model=PendingActionRead,
)
async def confirm_action(
    matter_id: str,
    action_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    response: Response,
) -> PendingActionRead:
    """Execute a proposed card after re-checking authority and version.

    Capability, practising status, ownership and the target version are all
    re-read here. A stale proposal is 412 and must be regenerated.
    """
    failure = None
    async with uow:
        try:
            action = await service.confirm_action(ctx, matter_id, action_id=action_id)
        except DraftlyError as exc:
            failure = exc
    if failure is not None:
        raise failure
    response.headers["ETag"] = f'"{action.target_version}"'
    return _to_action_read(action)


@router.post(
    "/matters/{matter_id}/agent/actions/{action_id}/reject",
    response_model=PendingActionRead,
)
async def reject_action(
    matter_id: str,
    action_id: str,
    body: RejectActionRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AgentService, Depends(get_agent_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> PendingActionRead:
    """Refuse a card. The rejected proposal is preserved and audited."""
    failure = None
    async with uow:
        try:
            action = await service.reject_action(
                ctx, matter_id, action_id=action_id, reason=body.reason
            )
        except DraftlyError as exc:
            failure = exc
    if failure is not None:
        raise failure
    return _to_action_read(action)
