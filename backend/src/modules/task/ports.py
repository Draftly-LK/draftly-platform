"""Persistence and current-source reads for operational matter work."""

from typing import Protocol

from src.modules.task.contracts import ReadinessReference
from src.modules.task.domain.work import WorkHistory, WorkTask
from src.platform.pagination import Cursor
from src.platform.request_context import RequestContext


class WorkRepository(Protocol):
    async def list_tasks(self, user_id: str, matter_id: str) -> list[WorkTask]: ...
    async def get(self, user_id: str, matter_id: str, task_id: str) -> WorkTask | None: ...
    async def find_dedup(self, user_id: str, matter_id: str, key: str) -> WorkTask | None: ...
    async def create(self, task: WorkTask) -> WorkTask: ...
    async def update(self, task: WorkTask, expected_version: int) -> WorkTask: ...
    async def append_history(self, history: WorkHistory) -> None: ...
    async def history(
        self, user_id: str, matter_id: str, task_id: str, *, after: Cursor | None, limit: int
    ) -> list[WorkHistory]: ...


class WorkReferencePort(Protocol):
    async def current_reference(
        self, ctx: RequestContext, matter_id: str, reference: ReadinessReference
    ) -> ReadinessReference | None: ...


class WorkProjectionPort(Protocol):
    async def projected_tasks(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[WorkTask, ...]: ...


class WorkProposalAuthorizationPort(Protocol):
    async def authorize(
        self, ctx: RequestContext, capability: str, matter_id: str | None = None
    ) -> None: ...
