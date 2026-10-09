"""Operational checklist wire contracts; these cannot carry eligibility decisions."""

from typing import Literal

from pydantic import Field, field_validator

from src.modules.task.api.schemas import ReadinessReferenceRead, _Camel, _StrictCamel
from src.modules.task.domain.work import WorkGroup, WorkOrigin, WorkState


class WorkCreateRequest(_StrictCamel):
    title: str = Field(min_length=1, max_length=300)
    reason: str | None = Field(default=None, max_length=4000)
    group: WorkGroup
    evidence: list[ReadinessReferenceRead] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a task title.")
        return value.strip()


class WorkEditRequest(_StrictCamel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    reason: str | None = Field(default=None, max_length=4000)
    group: WorkGroup | None = None
    evidence: list[ReadinessReferenceRead] | None = Field(default=None, max_length=100)


class WorkDecisionRequest(_StrictCamel):
    decision: Literal["complete", "review", "cancel"]
    note: str | None = Field(default=None, max_length=4000)
    evidence: list[ReadinessReferenceRead] | None = Field(default=None, max_length=100)


class SuggestionDecisionRequest(_StrictCamel):
    decision: Literal["accept", "dismiss"]


class WorkActionRead(_Camel):
    kind: Literal["navigate", "decide"]
    section: str | None = None
    target_id: str | None = None


class WorkTaskRead(_Camel):
    id: str
    version: int
    group: WorkGroup
    origin: WorkOrigin
    state: WorkState
    title: str | None
    title_key: str | None
    reason: str | None
    reason_key: str | None
    completed_by: str | None
    completed_at: str | None
    assigned_to: str | None
    evidence: list[ReadinessReferenceRead]
    action: WorkActionRead | None


class WorkProgressRead(_Camel):
    total: int
    completed: int
    percent: int
    assessing: bool


class WorkChecklistRead(_Camel):
    matter_id: str
    tasks: list[WorkTaskRead]
    suggestions: list[WorkTaskRead]
    progress: WorkProgressRead
    next_task_id: str | None


class WorkHistoryRead(_Camel):
    id: str
    task_id: str
    decision: str
    actor_id: str
    created_at: str
    previous_state: str
    state: str
    version: int
    note: str | None
    evidence: list[ReadinessReferenceRead]


class WorkHistoryPage(_Camel):
    items: list[WorkHistoryRead]
    next_cursor: str | None


class WorkSuggestionPage(_Camel):
    items: list[WorkTaskRead]
    next_cursor: str | None
