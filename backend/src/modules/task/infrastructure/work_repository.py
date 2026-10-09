"""Tenant/matter-scoped operational task storage and immutable decision history."""

from dataclasses import asdict, replace
from typing import cast

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.task.contracts import ReadinessReference
from src.modules.task.domain.work import (
    WorkAction,
    WorkGroup,
    WorkHistory,
    WorkOrigin,
    WorkState,
    WorkTask,
)
from src.modules.task.infrastructure.orm import WorkHistoryRow, WorkTaskRow
from src.platform.errors import PreconditionFailedError
from src.platform.pagination import Cursor


def _task(row: WorkTaskRow) -> WorkTask:
    return WorkTask(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        group=cast(WorkGroup, row.group),
        origin=cast(WorkOrigin, row.origin),
        state=cast(WorkState, row.state),
        title=row.title,
        title_key=row.title_key,
        reason=row.reason,
        reason_key=row.reason_key,
        assigned_to=row.assigned_to,
        completed_by=row.completed_by,
        completed_at=row.completed_at,
        evidence=tuple(ReadinessReference(**ref) for ref in row.evidence),
        created_by=row.created_by,
        created_at=row.created_at,
        version=row.version,
        suggestion_status=row.suggestion_status,
        dedup_key=row.dedup_key,
        provenance=row.provenance,
        action=None if row.state == "cancelled" else WorkAction("decide"),
    )


class SqlWorkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tasks(self, user_id: str, matter_id: str) -> list[WorkTask]:
        rows = await self._session.scalars(
            select(WorkTaskRow)
            .where(WorkTaskRow.user_id == user_id, WorkTaskRow.matter_id == matter_id)
            .order_by(WorkTaskRow.created_at, WorkTaskRow.id)
        )
        return [_task(row) for row in rows]

    async def get(self, user_id: str, matter_id: str, task_id: str) -> WorkTask | None:
        row = await self._session.scalar(
            select(WorkTaskRow).where(
                WorkTaskRow.user_id == user_id,
                WorkTaskRow.matter_id == matter_id,
                WorkTaskRow.id == task_id,
            )
        )
        return _task(row) if row else None

    async def find_dedup(self, user_id: str, matter_id: str, key: str) -> WorkTask | None:
        row = await self._session.scalar(
            select(WorkTaskRow).where(
                WorkTaskRow.user_id == user_id,
                WorkTaskRow.matter_id == matter_id,
                WorkTaskRow.dedup_key == key,
            )
        )
        return _task(row) if row else None

    async def create(self, task: WorkTask) -> WorkTask:
        values = asdict(task)
        values.pop("action")
        self._session.add(WorkTaskRow(**values))
        await self._session.flush()
        return task

    async def update(self, task: WorkTask, expected_version: int) -> WorkTask:
        values = asdict(task)
        for key in ("action", "id", "user_id", "matter_id", "created_at", "created_by"):
            values.pop(key)
        values["version"] = expected_version + 1
        result = await self._session.execute(
            update(WorkTaskRow)
            .where(
                WorkTaskRow.user_id == task.user_id,
                WorkTaskRow.matter_id == task.matter_id,
                WorkTaskRow.id == task.id,
                WorkTaskRow.version == expected_version,
            )
            .values(**values)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise PreconditionFailedError("The task changed. Refresh before recording a decision.")
        await self._session.flush()
        return replace(task, version=expected_version + 1)

    async def append_history(self, history: WorkHistory) -> None:
        self._session.add(WorkHistoryRow(**asdict(history)))
        await self._session.flush()

    async def history(
        self, user_id: str, matter_id: str, task_id: str, *, after: Cursor | None, limit: int
    ) -> list[WorkHistory]:
        query = select(WorkHistoryRow).where(
            WorkHistoryRow.user_id == user_id,
            WorkHistoryRow.matter_id == matter_id,
            WorkHistoryRow.task_id == task_id,
        )
        if after:
            query = query.where(
                or_(
                    WorkHistoryRow.created_at > after.created_at,
                    and_(
                        WorkHistoryRow.created_at == after.created_at, WorkHistoryRow.id > after.id
                    ),
                )
            )
        rows = await self._session.scalars(
            query.order_by(WorkHistoryRow.created_at, WorkHistoryRow.id).limit(limit)
        )
        return [
            WorkHistory(
                id=row.id,
                task_id=row.task_id,
                user_id=row.user_id,
                matter_id=row.matter_id,
                decision=row.decision,
                actor_id=row.actor_id,
                created_at=row.created_at,
                previous_state=row.previous_state,
                state=row.state,
                version=row.version,
                note=row.note,
                evidence=tuple(ReadinessReference(**ref) for ref in row.evidence),
            )
            for row in rows
        ]
