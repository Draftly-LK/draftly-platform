"""Server-owned operational next action; legal completion stays with existing owners."""

from dataclasses import dataclass
from datetime import UTC, datetime

from src.modules.content_governance.contracts import CAP_AUDIT_READ
from src.modules.matter.contracts import (
    MatterMutationLockPort,
    MatterReadPort,
    require_rta_capability,
)
from src.modules.task.application.checklist_service import ChecklistService
from src.modules.task.contracts import ReadinessDependency, ReadinessReference, ReadinessSourcePort
from src.modules.task.domain.errors import ChecklistSnapshotNotFoundError
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext


@dataclass(frozen=True)
class MatterReadiness:
    state: str
    next_action: str
    evaluated_at: datetime
    dependencies: tuple[ReadinessDependency, ...]
    requirement_total: int | None
    requirement_completed: int | None


class ReadinessService:
    def __init__(
        self,
        matters: MatterReadPort,
        lock: MatterMutationLockPort,
        checklist: ChecklistService,
        sources: dict[str, ReadinessSourcePort],
    ) -> None:
        self._matters, self._lock, self._checklist, self._sources = (
            matters,
            lock,
            checklist,
            sources,
        )

    async def evaluate(self, ctx: RequestContext, matter_id: str) -> MatterReadiness:
        matter = await self._matters.get_access_summary(ctx.actor_id, matter_id)
        if matter is None:
            raise NotFoundError()
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=matter,
            capability=CAP_AUDIT_READ,
        )
        await self._lock.lock(ctx.actor_id, matter_id)
        dependencies: list[ReadinessDependency] = []
        total = completed = None
        for category, source in self._sources.items():
            try:
                dependencies.extend(await source.readiness_dependencies(ctx, matter_id))
            except Exception:
                # Authorization happened above. Failure is explicit and cannot clear any gate.
                dependencies.append(ReadinessDependency(category, "unknown"))
        try:
            checklist = await self._checklist.get_checklist(
                user_id=ctx.actor_id, matter_id=matter_id
            )
            applicable = [row for row in checklist.items if row.lifecycle.value != "NOT_TRIGGERED"]
            total = len(applicable)
            completed = sum(row.computed_resolution.value == "SATISFIED" for row in applicable)
            for row in applicable:
                item = row.item
                ref = ReadinessReference("requirement", item.id, item.version)
                if row.computed_resolution.value != "SATISFIED":
                    dependencies.append(ReadinessDependency("requirements", "pending", (ref,)))
                if (
                    row.requirement.physical_original_policy.value != "NOT_REQUIRED"
                    and item.physical_original.value != "ORIGINAL_INSPECTED"
                ):
                    dependencies.append(ReadinessDependency("manual", "pending", (ref,)))
        except ChecklistSnapshotNotFoundError:
            dependencies.append(ReadinessDependency("requirements", "unknown"))
        except Exception:
            dependencies.append(ReadinessDependency("requirements", "unknown"))
        unknown = any(row.state == "unknown" for row in dependencies)
        priority = (
            "upload",
            "processing",
            "grouping",
            "classification",
            "extraction",
            "facts",
            "requirements",
            "manual",
            "checks",
            "issues",
        )
        next_action = next(
            (
                category
                for category in priority
                if any(
                    row.category == category and (row.state != "unknown" or category == "checks")
                    for row in dependencies
                )
            ),
            "unknown" if unknown else "draft-review",
        )
        # A clean operational queue is an invitation to review output, never legal approval.
        return MatterReadiness(
            "unknown" if unknown else "blocked" if dependencies else "needs-review",
            next_action,
            datetime.now(UTC),
            tuple(dependencies),
            total,
            completed,
        )
