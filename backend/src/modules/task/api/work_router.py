"""Versioned, replayable lawyer actions on operational work only."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.task.api.replay import RequirementCommandReplay
from src.modules.task.api.work_schemas import (
    SuggestionDecisionRequest,
    WorkChecklistRead,
    WorkCreateRequest,
    WorkDecisionRequest,
    WorkEditRequest,
    WorkHistoryPage,
    WorkHistoryRead,
    WorkProgressRead,
    WorkSuggestionPage,
    WorkTaskRead,
)
from src.modules.task.application.work_service import WorkTaskService
from src.modules.task.contracts import ReadinessReference
from src.modules.task.domain.work import WorkTask
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.pagination import Cursor, decode_cursor, encode_cursor
from src.platform.request_context import RequestContext

router = APIRouter(tags=["work-checklist"])


def get_work_service(session: AsyncSession = Depends(get_db)) -> WorkTaskService:
    from src.bootstrap import build_work_task_service

    return build_work_task_service(session)


def task_read(task: WorkTask) -> WorkTaskRead:
    values = asdict(task)
    values["completed_at"] = task.completed_at.isoformat() if task.completed_at else None
    return WorkTaskRead.model_validate(values)


@router.get("/matters/{matter_id}/work-tasks/{task_id}", response_model=WorkTaskRead)
async def get_work_task(
    matter_id: str,
    task_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
) -> WorkTaskRead:
    task = await service.read(ctx, matter_id, task_id)
    response.headers["ETag"] = f'"{task.version}"'
    return task_read(task)


@router.get("/matters/{matter_id}/task-suggestions", response_model=WorkSuggestionPage)
async def get_task_suggestions(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> WorkSuggestionPage:
    rows = await service.suggestions(ctx, matter_id, after=decode_cursor(cursor), limit=limit + 1)
    return WorkSuggestionPage(
        items=[task_read(row) for row in rows[:limit]],
        next_cursor=encode_cursor(Cursor(rows[limit - 1].created_at, rows[limit - 1].id))
        if len(rows) > limit
        else None,
    )


@router.get("/matters/{matter_id}/work-checklist", response_model=WorkChecklistRead)
async def get_work_checklist(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
) -> WorkChecklistRead:
    tasks, suggestions, progress, next_task = await service.checklist(ctx, matter_id)
    return WorkChecklistRead(
        matter_id=matter_id,
        tasks=[task_read(row) for row in tasks],
        suggestions=[task_read(row) for row in suggestions],
        progress=WorkProgressRead(
            total=progress[0], completed=progress[1], percent=progress[2], assessing=progress[3]
        ),
        next_task_id=next_task,
    )


@router.post("/matters/{matter_id}/work-tasks", response_model=WorkTaskRead, status_code=201)
async def create_work_task(
    matter_id: str,
    body: WorkCreateRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkTaskRead:
    _ = uow
    await service.authorize(ctx, matter_id, write=True)
    replay = RequirementCommandReplay(
        session, ctx.actor_id, f"/matters/{matter_id}/work-tasks", key, body.model_dump(mode="json")
    )
    cached = await replay.find(WorkTaskRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    task = await service.create(
        ctx,
        matter_id,
        title=body.title,
        reason=body.reason,
        group=body.group,
        evidence=tuple(ReadinessReference(**row.model_dump()) for row in body.evidence),
    )
    response.headers["ETag"] = f'"{task.version}"'
    return await replay.save(task_read(task))


@router.patch("/matters/{matter_id}/work-tasks/{task_id}", response_model=WorkTaskRead)
async def edit_work_task(
    matter_id: str,
    task_id: str,
    body: WorkEditRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkTaskRead:
    _ = uow
    await service.authorize(ctx, matter_id, write=True)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/work-tasks/{task_id}",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(WorkTaskRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    task = await service.edit(
        ctx,
        matter_id,
        task_id,
        expected_version=expected_version,
        title=body.title,
        reason=body.reason,
        group=body.group,
        evidence=tuple(ReadinessReference(**row.model_dump()) for row in body.evidence)
        if body.evidence is not None
        else None,
    )
    response.headers["ETag"] = f'"{task.version}"'
    return await replay.save(task_read(task))


@router.post("/matters/{matter_id}/work-tasks/{task_id}/decisions", response_model=WorkTaskRead)
async def decide_work_task(
    matter_id: str,
    task_id: str,
    body: WorkDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkTaskRead:
    _ = uow
    await service.authorize(ctx, matter_id, write=True)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/work-tasks/{task_id}/decisions",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(WorkTaskRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    task = await service.decide(
        ctx,
        matter_id,
        task_id,
        expected_version=expected_version,
        decision=body.decision,
        note=body.note,
        evidence=tuple(ReadinessReference(**row.model_dump()) for row in body.evidence)
        if body.evidence is not None
        else None,
    )
    response.headers["ETag"] = f'"{task.version}"'
    return await replay.save(task_read(task))


@router.post(
    "/matters/{matter_id}/task-suggestions/{task_id}/decisions", response_model=WorkTaskRead
)
async def decide_task_suggestion(
    matter_id: str,
    task_id: str,
    body: SuggestionDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkTaskRead:
    _ = uow
    await service.authorize(ctx, matter_id, write=True)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/task-suggestions/{task_id}/decisions",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(WorkTaskRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    task = await service.decide_suggestion(
        ctx, matter_id, task_id, expected_version=expected_version, decision=body.decision
    )
    response.headers["ETag"] = f'"{task.version}"'
    return await replay.save(task_read(task))


@router.get("/matters/{matter_id}/work-tasks/{task_id}/history", response_model=WorkHistoryPage)
async def get_work_history(
    matter_id: str,
    task_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: WorkTaskService = Depends(get_work_service),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> WorkHistoryPage:
    after = decode_cursor(cursor)
    rows = await service.history(ctx, matter_id, task_id, after=after, limit=limit + 1)
    more = len(rows) > limit
    selected = rows[:limit]
    return WorkHistoryPage(
        items=[
            WorkHistoryRead.model_validate(
                {**asdict(row), "created_at": row.created_at.isoformat()}
            )
            for row in selected
        ],
        next_cursor=encode_cursor(Cursor(selected[-1].created_at, selected[-1].id))
        if more
        else None,
    )
