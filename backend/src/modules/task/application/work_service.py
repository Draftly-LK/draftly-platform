"""Operational tasks, human acceptance, exact dependencies and non-authoritative progress."""

from dataclasses import replace
from datetime import UTC, datetime

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import CAP_AUDIT_READ, CAP_CHECKLIST_DECIDE
from src.modules.matter.contracts import (
    MatterMutationLockPort,
    MatterReadPort,
    require_rta_capability,
)
from src.modules.task.application.checklist_service import ChecklistService
from src.modules.task.contracts import ReadinessReference
from src.modules.task.domain.errors import ChecklistSnapshotNotFoundError
from src.modules.task.domain.work import (
    WorkAction,
    WorkGroup,
    WorkHistory,
    WorkState,
    WorkTask,
    progress_for,
    task_decision,
)
from src.modules.task.ports import (
    WorkProjectionPort,
    WorkProposalAuthorizationPort,
    WorkReferencePort,
    WorkRepository,
)
from src.platform.errors import DomainRuleError, NotFoundError, PreconditionFailedError
from src.platform.idempotency import fingerprint
from src.platform.ids import new_id
from src.platform.pagination import Cursor
from src.platform.request_context import RequestContext

GROUPS = ("documents", "evidence", "drafting", "execution", "registration", "completion")


def built_in_tasks(user_id: str, matter_id: str) -> tuple[WorkTask, ...]:
    """Work records only: none represents governed legal readiness or closure."""
    return tuple(
        WorkTask(
            id=f"work:{matter_id}:{group}",
            user_id=user_id,
            matter_id=matter_id,
            group=group,
            origin="operational",
            state="not-started",
            title_key=f"matterChecklist.tasks.{group}.title",
            reason_key=f"matterChecklist.tasks.{group}.reason",
            created_by="system",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            action=WorkAction("decide"),
        )
        for group in ("execution", "registration", "completion")
    )


class WorkTaskService:
    def __init__(
        self,
        repository: WorkRepository,
        matters: MatterReadPort,
        lock: MatterMutationLockPort,
        references: WorkReferencePort,
        projection: WorkProjectionPort,
        checklist: ChecklistService,
        audit: AuditPort,
        proposal_authorizer: WorkProposalAuthorizationPort,
    ) -> None:
        (
            self._repo,
            self._matters,
            self._lock,
            self._refs,
            self._projection,
            self._checklist,
            self._audit,
        ) = repository, matters, lock, references, projection, checklist, audit
        self._proposal_authorizer = proposal_authorizer

    async def authorize(self, ctx: RequestContext, matter_id: str, *, write: bool = False) -> None:
        matter = await self._matters.get_access_summary(ctx.actor_id, matter_id)
        if matter is None:
            raise NotFoundError()
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=matter,
            capability=CAP_CHECKLIST_DECIDE if write else CAP_AUDIT_READ,
        )
        if write:
            await self._lock.lock(ctx.actor_id, matter_id)

    async def _pins(
        self,
        ctx: RequestContext,
        matter_id: str,
        evidence: tuple[ReadinessReference, ...],
        *,
        refresh: bool = False,
    ) -> tuple[ReadinessReference, ...]:
        result = []
        for ref in evidence:
            if ref.kind not in {
                "document",
                "source",
                "source-file",
                "fact",
                "transaction",
                "form",
                "requirement",
            }:
                raise DomainRuleError(
                    "This supporting record type is not available for task links."
                )
            current = await self._refs.current_reference(ctx, matter_id, ref)
            if current is None:
                raise NotFoundError("The supporting record was not found in this matter.")
            if not refresh and current != ref:
                raise PreconditionFailedError(
                    "The supporting record changed. Refresh before continuing."
                )
            result.append(current)
        return tuple(result)

    async def _current(self, ctx: RequestContext, task: WorkTask) -> bool:
        try:
            await self._pins(ctx, task.matter_id, task.evidence)
            return True
        except (NotFoundError, PreconditionFailedError, DomainRuleError):
            return False

    async def create(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        title: str,
        reason: str | None,
        group: WorkGroup,
        evidence: tuple[ReadinessReference, ...] = (),
    ) -> WorkTask:
        await self.authorize(ctx, matter_id, write=True)
        if not title.strip():
            raise DomainRuleError("Enter a task title.")
        pins = await self._pins(ctx, matter_id, evidence)
        task = WorkTask(
            id=new_id("work"),
            user_id=ctx.actor_id,
            matter_id=matter_id,
            group=group,
            origin="lawyer",
            state="not-started",
            title=title.strip(),
            reason=reason,
            evidence=pins,
            created_by=ctx.actor_id,
            created_at=datetime.now(UTC),
            action=WorkAction("decide"),
        )
        await self._repo.create(task)
        await self._record(ctx, task, "created", "not-started")
        return task

    async def create_suggestion(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        title: str,
        reason: str,
        group: WorkGroup,
        evidence: tuple[ReadinessReference, ...] = (),
        provenance: dict[str, str] | None = None,
        dedup_key: str,
        title_key: str | None = None,
        reason_key: str | None = None,
    ) -> WorkTask:
        await self.authorize(ctx, matter_id)
        await self._proposal_authorizer.authorize(ctx, "checklist.administer", matter_id)
        await self._proposal_authorizer.authorize(ctx, "checklist.suggest-item", matter_id)
        await self._lock.lock(ctx.actor_id, matter_id)
        key = fingerprint(
            {"dedup": dedup_key, "evidence": [ref.__dict__ for ref in evidence], "group": group}
        )
        existing = await self._repo.find_dedup(ctx.actor_id, matter_id, key)
        if existing:
            return existing
        if not title.strip() or group not in GROUPS:
            raise DomainRuleError("The suggested task is incomplete.")
        pins = await self._pins(ctx, matter_id, evidence)
        task = WorkTask(
            id=new_id("work"),
            user_id=ctx.actor_id,
            matter_id=matter_id,
            group=group,
            origin="agent",
            state="pending-applicability",
            title=title.strip(),
            title_key=title_key,
            reason=reason,
            reason_key=reason_key,
            evidence=pins,
            created_by=ctx.actor_id,
            created_at=datetime.now(UTC),
            suggestion_status="pending",
            dedup_key=key,
            provenance=provenance or {},
        )
        await self._repo.create(task)
        await self._record(ctx, task, "suggested", task.state)
        return task

    async def _load(
        self, ctx: RequestContext, matter_id: str, task_id: str, expected_version: int
    ) -> WorkTask:
        task = await self._repo.get(ctx.actor_id, matter_id, task_id)
        if task is None:
            task = next(
                (row for row in built_in_tasks(ctx.actor_id, matter_id) if row.id == task_id), None
            )
            if task:
                await self._repo.create(task)
        if task is None:
            raise NotFoundError()
        if task.version != expected_version:
            raise PreconditionFailedError(
                "The task changed. Refresh before continuing.", currentVersion=task.version
            )
        return task

    async def read(self, ctx: RequestContext, matter_id: str, task_id: str) -> WorkTask:
        await self.authorize(ctx, matter_id)
        task = await self._repo.get(ctx.actor_id, matter_id, task_id)
        if task is None:
            task = next(
                (row for row in built_in_tasks(ctx.actor_id, matter_id) if row.id == task_id), None
            )
        if task is None:
            raise NotFoundError()
        return (
            replace(task, state="stale")
            if task.state not in {"cancelled", "not-applicable"}
            and not await self._current(ctx, task)
            else task
        )

    async def suggestions(
        self, ctx: RequestContext, matter_id: str, *, after: Cursor | None, limit: int
    ) -> list[WorkTask]:
        await self.authorize(ctx, matter_id)
        rows = [
            row
            for row in await self._repo.list_tasks(ctx.actor_id, matter_id)
            if row.origin == "agent"
        ]
        if after:
            rows = [row for row in rows if (row.created_at, row.id) > (after.created_at, after.id)]
        return rows[:limit]

    async def edit(
        self,
        ctx: RequestContext,
        matter_id: str,
        task_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        reason: str | None = None,
        group: WorkGroup | None = None,
        evidence: tuple[ReadinessReference, ...] | None = None,
    ) -> WorkTask:
        await self.authorize(ctx, matter_id, write=True)
        task = await self._load(ctx, matter_id, task_id, expected_version)
        if (
            task.origin == "operational"
            or task.suggestion_status == "pending"
            or task.state == "cancelled"
        ):
            raise DomainRuleError("This task cannot be edited.")
        if title is not None and not title.strip():
            raise DomainRuleError("Enter a task title.")
        pins = await self._pins(ctx, matter_id, evidence) if evidence is not None else task.evidence
        updated = replace(
            task,
            title=title.strip() if title is not None else task.title,
            reason=reason if reason is not None else task.reason,
            group=group or task.group,
            evidence=pins,
            state="stale" if task.state == "complete" else task.state,
        )
        updated = await self._repo.update(updated, expected_version)
        await self._record(ctx, updated, "edited", task.state)
        return updated

    async def decide(
        self,
        ctx: RequestContext,
        matter_id: str,
        task_id: str,
        *,
        expected_version: int,
        decision: str,
        note: str | None = None,
        evidence: tuple[ReadinessReference, ...] | None = None,
    ) -> WorkTask:
        await self.authorize(ctx, matter_id, write=True)
        task = await self._load(ctx, matter_id, task_id, expected_version)
        # Renewed review is an explicit decision to adopt the current versions,
        # retaining the old pins in the preceding immutable history entry.
        updated = task
        if (
            decision == "complete"
            and evidence is not None
            and any(ref not in evidence for ref in task.evidence)
        ):
            raise DomainRuleError("Review changed supporting records before completing this task.")
        if decision == "review":
            pins = await self._pins(
                ctx,
                matter_id,
                evidence if evidence is not None else task.evidence,
                refresh=evidence is None,
            )
            updated = replace(task, evidence=pins)
        elif evidence is not None:
            updated = replace(task, evidence=await self._pins(ctx, matter_id, evidence))
        current = await self._current(ctx, updated)
        updated = task_decision(updated, decision, actor=ctx.actor_id, current=current)
        updated = await self._repo.update(updated, expected_version)
        await self._record(ctx, updated, decision, task.state, note)
        return updated

    async def decide_suggestion(
        self,
        ctx: RequestContext,
        matter_id: str,
        task_id: str,
        *,
        expected_version: int,
        decision: str,
    ) -> WorkTask:
        await self.authorize(ctx, matter_id, write=True)
        task = await self._load(ctx, matter_id, task_id, expected_version)
        if task.origin != "agent" or task.suggestion_status != "pending":
            raise DomainRuleError("This suggestion already has a decision.")
        if decision == "accept":
            await self._pins(ctx, matter_id, task.evidence)
            updated = replace(
                task, state="not-started", suggestion_status="accepted", action=WorkAction("decide")
            )
        elif decision == "dismiss":
            updated = replace(task, state="cancelled", suggestion_status="dismissed")
        else:
            raise DomainRuleError("Unknown suggestion decision.")
        updated = await self._repo.update(updated, expected_version)
        await self._record(ctx, updated, decision, task.state)
        return updated

    async def history(
        self, ctx: RequestContext, matter_id: str, task_id: str, *, after: Cursor | None, limit: int
    ) -> list[WorkHistory]:
        await self.authorize(ctx, matter_id)
        task = await self._repo.get(ctx.actor_id, matter_id, task_id)
        if task is None and not any(
            row.id == task_id for row in built_in_tasks(ctx.actor_id, matter_id)
        ):
            raise NotFoundError()
        return await self._repo.history(ctx.actor_id, matter_id, task_id, after=after, limit=limit)

    async def checklist(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[list[WorkTask], list[WorkTask], tuple[int, int, int, bool], str | None]:
        await self.authorize(ctx, matter_id)
        # Serialize with evidence mutations: counts, pins and decisions form one read.
        await self._lock.lock(ctx.actor_id, matter_id)
        tasks = list(await self._projection.projected_tasks(ctx, matter_id))
        try:
            governed = await self._checklist.get_checklist(
                user_id=ctx.actor_id, matter_id=matter_id
            )
            for row in governed.items:
                item = row.item
                state: WorkState = (
                    "not-applicable"
                    if item.applicability.value in {"NOT_APPLICABLE", "WAIVED_BY_LAWYER"}
                    or row.lifecycle.value == "NOT_TRIGGERED"
                    else "stale"
                    if row.has_invalid_support
                    else "complete"
                    if row.computed_resolution.value == "SATISFIED"
                    else "pending-applicability"
                    if item.applicability.value in {"PROVISIONAL_REQUIRED", "CONDITIONAL"}
                    and item.applicability_decided_by is None
                    else "blocked"
                    if row.blocks_approval
                    else "not-started"
                )
                links = await self._checklist.list_links(user_id=ctx.actor_id, item_id=item.id)
                evidence = tuple(
                    ReadinessReference(
                        "document",
                        link.detected_document_id,
                        link.document_version,
                        link.interpretation_generation,
                    )
                    for link in links
                    if link.is_live
                )
                tasks.append(
                    WorkTask(
                        id=item.id,
                        user_id=ctx.actor_id,
                        matter_id=matter_id,
                        group="evidence",
                        origin="governed",
                        state=state,
                        title_key=row.requirement.label_key,
                        reason_key=row.requirement.explanation_key,
                        created_by=governed.snapshot.created_by,
                        created_at=item.created_at,
                        assigned_to=item.assigned_to,
                        evidence=evidence,
                        action=WorkAction("navigate", "checks", item.id),
                        version=item.version,
                    )
                )
        except ChecklistSnapshotNotFoundError:
            tasks.append(
                WorkTask(
                    id="work:assessment",
                    user_id=ctx.actor_id,
                    matter_id=matter_id,
                    group="evidence",
                    origin="operational",
                    state="pending-applicability",
                    title_key="matterChecklist.tasks.assessment.title",
                    reason_key="matterChecklist.tasks.assessment.reason",
                    created_by="system",
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                    action=WorkAction("navigate", "facts"),
                )
            )
        persisted = await self._repo.list_tasks(ctx.actor_id, matter_id)
        existing_ids = {row.id for row in persisted}
        tasks.extend(
            row for row in built_in_tasks(ctx.actor_id, matter_id) if row.id not in existing_ids
        )
        suggestions: list[WorkTask] = []
        for stored in persisted:
            current = await self._current(ctx, stored)
            effective = (
                replace(stored, state="stale")
                if not current and stored.state not in {"cancelled", "not-applicable"}
                else stored
            )
            if stored.suggestion_status == "pending":
                suggestions.append(effective)
            elif stored.suggestion_status != "dismissed":
                tasks.append(effective)
        tasks.sort(
            key=lambda row: (
                GROUPS.index(row.group),
                row.state in {"complete", "not-applicable", "cancelled"},
                row.id,
            )
        )
        next_task = next(
            (
                row.id
                for row in tasks
                if row.state
                not in {"complete", "not-applicable", "cancelled", "pending-applicability"}
                and row.action is not None
            ),
            None,
        )
        return tasks, suggestions, progress_for(tasks), next_task

    async def _record(
        self,
        ctx: RequestContext,
        task: WorkTask,
        decision: str,
        previous: str,
        note: str | None = None,
    ) -> None:
        await self._repo.append_history(
            WorkHistory(
                id=new_id("workhist"),
                task_id=task.id,
                user_id=ctx.actor_id,
                matter_id=task.matter_id,
                decision=decision,
                actor_id=ctx.actor_id,
                created_at=datetime.now(UTC),
                previous_state=previous,
                state=task.state,
                version=task.version,
                note=note,
                evidence=task.evidence,
            )
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=task.matter_id,
                actor=ctx.actor_id,
                action="work-task.decision-recorded",
                target_type="workflow-step",
                target_id=task.id,
                before_ref=previous,
                after_ref=f"{task.state}/{task.version}",
                correlation_id=ctx.correlation_id,
            )
        )
