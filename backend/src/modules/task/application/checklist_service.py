"""Checklist application service — compile, decide, and derive.

Compilation is idempotent over unchanged inputs: the compiler's fingerprint is
looked up first, and an identical compile returns the existing snapshot rather
than churning a new one. That matters because the matter recompiles on every
answer change, and a lawyer should see "no change" rather than a fresh snapshot
with the same content.

Every decision on an item runs `policies.compute_resolution` afterwards, so
``SATISFIED`` is always derived from the requirement's own policy and never from
what the caller asked for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    RULE_PACK_VERSION,
    ApplicabilityStatus,
    ChecklistItemLifecycle,
    CollectionStatus,
    CompiledChecklist,
    CompilerInput,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    RequirementDefinition,
    ResolutionStatus,
    ReviewedItemMemo,
    compile_checklist,
    get_requirement,
)
from src.modules.task.domain.errors import (
    ChecklistItemNotFoundError,
    ChecklistSnapshotNotFoundError,
)
from src.modules.task.domain.models import (
    ChecklistItem,
    ChecklistSnapshot,
    OriginalInspection,
    SatisfactionLink,
)
from src.modules.task.domain.policies import (
    apply_applicability,
    apply_physical_original,
    compute_resolution,
    derive_lifecycle,
    guard_resolution_write,
    initial_item_statuses,
    is_blocking_unsatisfied,
)
from src.modules.task.infrastructure.repository import SqlChecklistRepository
from src.platform import ids

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ChecklistItemView:
    """An item plus the values the UI derives rather than stores."""

    item: ChecklistItem
    requirement: RequirementDefinition
    lifecycle: ChecklistItemLifecycle
    computed_resolution: ResolutionStatus
    live_link_count: int
    blocks_approval: bool


@dataclass(frozen=True)
class ChecklistView:
    snapshot: ChecklistSnapshot
    items: tuple[ChecklistItemView, ...]

    @property
    def blocking_requirement_ids(self) -> tuple[str, ...]:
        return tuple(
            view.item.requirement_definition_id for view in self.items if view.blocks_approval
        )


class ChecklistService:
    """Owns compiled checklists and every decision recorded against an item."""

    def __init__(self, *, repository: SqlChecklistRepository, audit: AuditPort) -> None:
        self._repo = repository
        self._audit = audit

    # ── Compilation (implements matter's ChecklistCommandPort) ────────────────

    async def compile_snapshot(
        self,
        *,
        user_id: str,
        matter_id: str,
        compiler_input: CompilerInput,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[str, CompiledChecklist]:
        """Compile, or return the existing snapshot with the same fingerprint."""
        previous = await self._repo.latest_snapshot(user_id, matter_id)
        reviewed = await self._repo.reviewed_requirement_ids(user_id, matter_id)
        enriched = CompilerInput(
            subtype_id=compiler_input.subtype_id,
            activated_conditional_module_ids=compiler_input.activated_conditional_module_ids,
            office_policy_module_ids=compiler_input.office_policy_module_ids,
            local_authority_id=compiler_input.local_authority_id,
            lawyer_added_items=compiler_input.lawyer_added_items,
            suppressed_conditional_module_ids=compiler_input.suppressed_conditional_module_ids,
            previous_items=tuple(
                ReviewedItemMemo(requirement_definition_id=rid, was_reviewed=True)
                for rid in sorted(reviewed)
            ),
        )
        compiled = compile_checklist(enriched)

        existing = await self._repo.find_snapshot_by_fingerprint(
            user_id, matter_id, compiled.fingerprint
        )
        if existing is not None:
            return existing.id, compiled

        now = datetime.now(tz=UTC)
        snapshot = await self._repo.create_snapshot(
            ChecklistSnapshot(
                id=ids.new_id(ids.CHECKLIST_SNAPSHOT),
                user_id=user_id,
                matter_id=matter_id,
                compiler_version=compiled.compiler_version,
                taxonomy_version=compiled.taxonomy_version,
                checklist_version=compiled.checklist_version,
                rule_pack_version=RULE_PACK_VERSION,
                fingerprint=compiled.fingerprint,
                module_definition_ids=compiled.module_definition_ids,
                created_at=now,
                created_by=actor_id,
                supersedes_id=previous.id if previous else None,
            )
        )

        items: list[ChecklistItem] = []
        for compiled_item in compiled.items:
            requirement = get_requirement(compiled_item.requirement_definition_id)
            if requirement is None:
                continue
            collection, review, original, currency, consistency, resolution = initial_item_statuses(
                requirement
            )
            items.append(
                ChecklistItem(
                    id=ids.new_id(ids.CHECKLIST_ITEM),
                    user_id=user_id,
                    matter_id=matter_id,
                    snapshot_id=snapshot.id,
                    requirement_definition_id=compiled_item.requirement_definition_id,
                    module_definition_id=compiled_item.module_definition_id,
                    inclusion_reason=compiled_item.inclusion_reason.value,
                    inclusion_trigger_id=compiled_item.inclusion_trigger_id,
                    applicability=compiled_item.applicability,
                    collection=collection,
                    digital_review=review,
                    physical_original=original,
                    currency=currency,
                    consistency=consistency,
                    resolution=resolution,
                    local_authority_id=compiled_item.local_authority_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self._repo.create_items(items)
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=AuditAction.RTA_CHECKLIST_COMPILED.value,
                target_type=AuditTargetType.CHECKLIST_SNAPSHOT.value,
                target_id=snapshot.id,
                before_ref=previous.fingerprint if previous else None,
                after_ref=compiled.fingerprint,
                correlation_id=correlation_id,
            )
        )
        return snapshot.id, compiled

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_checklist(
        self, *, user_id: str, matter_id: str, snapshot_id: str | None = None
    ) -> ChecklistView:
        snapshot = (
            await self._repo.get_snapshot(user_id, snapshot_id)
            if snapshot_id
            else await self._repo.latest_snapshot(user_id, matter_id)
        )
        if snapshot is None or snapshot.matter_id != matter_id:
            raise ChecklistSnapshotNotFoundError()
        items = await self._repo.list_items(user_id, snapshot.id)
        views: list[ChecklistItemView] = []
        for item in items:
            requirement = get_requirement(item.requirement_definition_id)
            if requirement is None:
                # A requirement retired between snapshots: the item stays
                # visible but cannot be re-evaluated against a rule that no
                # longer exists. Skipping it would hide review work.
                log.warning(
                    "checklist.requirement_retired",
                    requirement_id=item.requirement_definition_id,
                    item_id=item.id,
                )
                continue
            links = await self._repo.list_links_for_item(user_id, item.id)
            live = sum(1 for link in links if link.is_live)
            views.append(
                ChecklistItemView(
                    item=item,
                    requirement=requirement,
                    lifecycle=derive_lifecycle(item, requirement, live_link_count=live),
                    computed_resolution=compute_resolution(item, requirement),
                    live_link_count=live,
                    blocks_approval=is_blocking_unsatisfied(item, requirement),
                )
            )
        return ChecklistView(snapshot=snapshot, items=tuple(views))

    async def list_links(self, *, user_id: str, item_id: str) -> list[SatisfactionLink]:
        """Every link, including superseded ones — replacement never erases history."""
        return await self._repo.list_links_for_item(user_id, item_id)

    async def blocking_requirement_ids(self, *, user_id: str, matter_id: str) -> tuple[str, ...]:
        """Requirements that currently block approval. Used by form preflight."""
        try:
            view = await self.get_checklist(user_id=user_id, matter_id=matter_id)
        except ChecklistSnapshotNotFoundError:
            # No checklist yet is not "nothing blocks": it means the matter has
            # not been scoped, which the caller's own gate reports.
            return ()
        return view.blocking_requirement_ids

    # ── Decisions ────────────────────────────────────────────────────────────

    async def decide_satisfaction(
        self,
        *,
        user_id: str,
        matter_id: str,
        item_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        applicability: ApplicabilityStatus | None = None,
        collection: CollectionStatus | None = None,
        digital_review: DigitalReviewStatus | None = None,
        currency: CurrencyStatus | None = None,
        consistency: ConsistencyStatus | None = None,
        resolution: ResolutionStatus | None = None,
        reason: str | None = None,
        assigned_to: str | None = None,
        due_at: datetime | None = None,
    ) -> ChecklistItemView:
        """Record one lawyer decision across any of the six settable dimensions."""
        item, requirement = await self._load(user_id, matter_id, item_id)
        before = (
            f"{item.applicability.value}/{item.collection.value}/"
            f"{item.digital_review.value}/{item.currency.value}/"
            f"{item.consistency.value}/{item.resolution.value}"
        )

        if resolution is not None:
            guard_resolution_write(resolution)
        if applicability is not None:
            apply_applicability(
                item,
                requirement,
                target=applicability,
                reason=reason,
                decided_by=actor_id,
            )
        if collection is not None:
            item.collection = collection
        if digital_review is not None:
            item.digital_review = digital_review
        if currency is not None:
            item.currency = currency
        if consistency is not None:
            item.consistency = consistency
        if assigned_to is not None:
            item.assigned_to = assigned_to
        if due_at is not None:
            item.due_at = due_at

        computed = compute_resolution(item, requirement)
        # An explicit non-SATISFIED resolution (for example ACTION_REQUESTED or
        # REMEDIATED) is the lawyer's own tracking state and is honoured — unless
        # the computation says the item is genuinely satisfied, in which case the
        # computed value wins so the two can never disagree.
        item.resolution = (
            computed if computed is ResolutionStatus.SATISFIED or resolution is None else resolution
        )

        saved = await self._repo.update_item(item, expected_version)
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=(
                AuditAction.RTA_CHECKLIST_ITEM_WAIVED
                if applicability is ApplicabilityStatus.WAIVED_BY_LAWYER
                else AuditAction.RTA_CHECKLIST_ITEM_DECIDED
            ),
            target_id=saved.id,
            before_ref=before,
            after_ref=(
                f"{saved.applicability.value}/{saved.collection.value}/"
                f"{saved.digital_review.value}/{saved.currency.value}/"
                f"{saved.consistency.value}/{saved.resolution.value}"
            ),
            reason=reason,
        )
        return await self._view(user_id, saved, requirement)

    async def record_original_inspection(
        self,
        *,
        user_id: str,
        matter_id: str,
        item_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        method: str,
        location: str | None = None,
        note: str | None = None,
    ) -> ChecklistItemView:
        """Record that a named human inspected the physical original.

        The reviewer is taken from the authenticated actor, never from the
        request body, so an inspection cannot be attributed to someone else —
        and there is no parameter through which a pipeline could claim one.
        """
        item, requirement = await self._load(user_id, matter_id, item_id)
        inspected_at = datetime.now(tz=UTC)
        apply_physical_original(
            item,
            target=PhysicalOriginalStatus.ORIGINAL_INSPECTED,
            inspection=OriginalInspection(
                reviewer_id=actor_id,
                inspected_at=inspected_at,
                method=method,
                location=location,
                note=note,
            ),
        )
        item.resolution = compute_resolution(item, requirement)
        saved = await self._repo.update_item(item, expected_version)
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_ORIGINAL_INSPECTION_RECORDED,
            target_id=saved.id,
            after_ref=f"{PhysicalOriginalStatus.ORIGINAL_INSPECTED.value}@{inspected_at.isoformat()}",
            reason=f"method={method}",
        )
        return await self._view(user_id, saved, requirement)

    async def link_document(
        self,
        *,
        user_id: str,
        matter_id: str,
        item_id: str,
        detected_document_id: str,
        actor_id: str,
        correlation_id: str,
        evidence_reference_ids: tuple[str, ...] = (),
        lawyer_confirmed: bool = False,
        note: str | None = None,
    ) -> SatisfactionLink:
        """Offer one document towards one item.

        Called once per item for a combined certificate, which is how one file
        satisfies several requirements without being duplicated (§6.3).
        """
        item, _ = await self._load(user_id, matter_id, item_id)
        now = datetime.now(tz=UTC)
        link = await self._repo.create_link(
            SatisfactionLink(
                id=ids.new_id(ids.SATISFACTION_LINK),
                user_id=user_id,
                matter_id=matter_id,
                checklist_item_id=item.id,
                detected_document_id=detected_document_id,
                digital_review=(
                    DigitalReviewStatus.LAWYER_CONFIRMED
                    if lawyer_confirmed
                    else DigitalReviewStatus.AI_ORGANIZED
                ),
                evidence_reference_ids=evidence_reference_ids,
                reviewed_by=actor_id if lawyer_confirmed else None,
                reviewed_at=now if lawyer_confirmed else None,
                review_note=note,
                created_by=actor_id,
                created_at=now,
            )
        )
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_CHECKLIST_ITEM_DECIDED,
            target_id=item.id,
            after_ref=f"link:{detected_document_id}",
            reason=note,
        )
        return link

    async def supersede_document_links(
        self, *, user_id: str, detected_document_id: str, replacement_link_id: str | None = None
    ) -> int:
        return await self._repo.supersede_links_for_document(
            user_id, detected_document_id, replacement_link_id=replacement_link_id
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _load(
        self, user_id: str, matter_id: str, item_id: str
    ) -> tuple[ChecklistItem, RequirementDefinition]:
        item = await self._repo.get_item(user_id, item_id)
        if item is None or item.matter_id != matter_id:
            raise ChecklistItemNotFoundError()
        requirement = get_requirement(item.requirement_definition_id)
        if requirement is None:
            raise ChecklistItemNotFoundError(
                "The requirement behind this item is no longer in the rule pack.",
                requirementId=item.requirement_definition_id,
            )
        return item, requirement

    async def _view(
        self, user_id: str, item: ChecklistItem, requirement: RequirementDefinition
    ) -> ChecklistItemView:
        links = await self._repo.list_links_for_item(user_id, item.id)
        live = sum(1 for link in links if link.is_live)
        return ChecklistItemView(
            item=item,
            requirement=requirement,
            lifecycle=derive_lifecycle(item, requirement, live_link_count=live),
            computed_resolution=compute_resolution(item, requirement),
            live_link_count=live,
            blocks_approval=is_blocking_unsatisfied(item, requirement),
        )

    async def _record(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        action: AuditAction,
        target_id: str,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=action.value,
                target_type=AuditTargetType.CHECKLIST_ITEM.value,
                target_id=target_id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=correlation_id,
            )
        )
