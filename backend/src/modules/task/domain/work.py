"""Recorded operational work, separate from governed satisfaction and eligibility."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal

from src.modules.task.contracts import ReadinessReference
from src.platform.errors import DomainRuleError, PreconditionFailedError

WorkGroup = Literal["documents", "evidence", "drafting", "execution", "registration", "completion"]
WorkState = Literal[
    "not-started",
    "in-progress",
    "blocked",
    "complete",
    "stale",
    "pending-applicability",
    "not-applicable",
    "cancelled",
]
WorkOrigin = Literal["governed", "operational", "lawyer", "agent"]


@dataclass(frozen=True)
class WorkAction:
    kind: Literal["navigate", "decide"]
    section: str | None = None
    target_id: str | None = None


@dataclass(frozen=True)
class WorkTask:
    id: str
    user_id: str
    matter_id: str
    group: WorkGroup
    origin: WorkOrigin
    state: WorkState
    created_by: str
    created_at: datetime
    title: str | None = None
    title_key: str | None = None
    reason: str | None = None
    reason_key: str | None = None
    assigned_to: str | None = None
    completed_by: str | None = None
    completed_at: datetime | None = None
    evidence: tuple[ReadinessReference, ...] = ()
    action: WorkAction | None = None
    version: int = 1
    suggestion_status: str | None = None
    dedup_key: str | None = None
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkHistory:
    id: str
    task_id: str
    user_id: str
    matter_id: str
    decision: str
    actor_id: str
    created_at: datetime
    previous_state: str
    state: str
    version: int
    note: str | None = None
    evidence: tuple[ReadinessReference, ...] = ()


def progress_for(tasks: list[WorkTask]) -> tuple[int, int, int, bool]:
    known = [
        row
        for row in tasks
        if row.state not in {"pending-applicability", "not-applicable", "cancelled"}
    ]
    completed = sum(row.state == "complete" for row in known)
    assessing = not known or any(row.state == "pending-applicability" for row in tasks)
    return len(known), completed, round(100 * completed / len(known)) if known else 0, assessing


def task_decision(task: WorkTask, decision: str, *, actor: str, current: bool) -> WorkTask:
    if task.origin == "governed" or task.suggestion_status == "pending":
        raise DomainRuleError("Record this decision through the owning review action.")
    if task.state in {"cancelled", "not-applicable", "pending-applicability"}:
        raise DomainRuleError("This task cannot be completed in its current state.")
    if decision == "complete":
        if not current or task.state == "stale":
            raise PreconditionFailedError("The supporting records changed. Review the task again.")
        return replace(task, state="complete", completed_by=actor, completed_at=datetime.now(UTC))
    if decision == "review":
        if not current:
            raise PreconditionFailedError("Select the current supporting records before reviewing.")
        return replace(task, state="not-started")
    if decision == "cancel":
        if task.origin == "operational":
            raise DomainRuleError("A built-in workflow task cannot be removed.")
        return replace(task, state="cancelled", action=None)
    raise DomainRuleError("Unknown task decision.")
