"""ChecklistService: idempotent compilation, item decisions, inspections, and links."""

from __future__ import annotations

from typing import Any, cast

import pytest

from src.modules.audit.domain.models import AuditAction
from src.modules.content_governance.contracts import (
    RULE_PACK_VERSION,
    TRANSFER_SALE_SUBTYPE_ID,
    ApplicabilityStatus,
    ChecklistItemLifecycle,
    CollectionStatus,
    CompilerInput,
    ConsistencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.task.application.checklist_service import ChecklistService
from src.modules.task.domain.errors import (
    ChecklistItemNotFoundError,
    ChecklistItemStaleError,
    ChecklistSnapshotNotFoundError,
    OriginalInspectionRequiresHumanError,
    SatisfactionIsComputedError,
    StatutoryRequirementNotWaivableError,
)
from src.modules.task.domain.models import ChecklistItem
from src.modules.task.tests.fakes import (
    CORRELATION,
    MATTER_ID,
    USER_ID,
    InMemoryChecklistRepository,
    RecordingAudit,
)

SIMPLE_ID = "R_C00_MATTER_AND_CLIENT_REFERENCE"
STATUTORY_ID = "R_C00_RESPONSIBLE_LAWYER_ASSIGNED"
WHO: dict[str, Any] = {
    "user_id": USER_ID,
    "matter_id": MATTER_ID,
    "actor_id": USER_ID,
    "correlation_id": CORRELATION,
}


class Harness:
    def __init__(self) -> None:
        self.repo = InMemoryChecklistRepository()
        self.audit = RecordingAudit()
        self.service = ChecklistService(repository=cast(Any, self.repo), audit=self.audit)

    async def compile(self, **overrides: Any) -> str:
        compiler_input = CompilerInput(**{"subtype_id": TRANSFER_SALE_SUBTYPE_ID, **overrides})
        snapshot_id, _ = await self.service.compile_snapshot(compiler_input=compiler_input, **WHO)
        return snapshot_id

    def item_for(self, requirement_id: str) -> ChecklistItem:
        latest = self.repo.snapshots[-1].id
        return next(
            i
            for i in self.repo.items.values()
            if i.requirement_definition_id == requirement_id and i.snapshot_id == latest
        )


@pytest.fixture
async def h() -> Harness:
    harness = Harness()
    await harness.compile()
    return harness


# ── Compilation ─────────────────────────────────────────────────────────────


async def test_compiling_creates_a_pinned_snapshot_with_honest_initial_items(h: Harness) -> None:
    snapshot = h.repo.snapshots[0]
    assert snapshot.rule_pack_version == RULE_PACK_VERSION
    assert snapshot.created_by == USER_ID
    assert snapshot.supersedes_id is None
    items = list(h.repo.items.values())
    assert items
    assert all(i.snapshot_id == snapshot.id for i in items)
    assert all(i.collection is CollectionStatus.NOT_REQUESTED for i in items)
    assert all(i.digital_review is DigitalReviewStatus.UNREVIEWED for i in items)
    assert all(i.resolution is ResolutionStatus.OPEN for i in items)
    assert not any(i.physical_original is PhysicalOriginalStatus.COPY_ONLY for i in items)
    event = h.audit.events[0]
    assert event.action == AuditAction.RTA_CHECKLIST_COMPILED.value
    assert (event.target_id, event.before_ref, event.after_ref) == (
        snapshot.id,
        None,
        snapshot.fingerprint,
    )


async def test_recompiling_unchanged_inputs_returns_the_same_snapshot(h: Harness) -> None:
    first = h.repo.snapshots[0].id
    items_before = len(h.repo.items)

    again = await h.compile()

    assert again == first
    assert len(h.repo.snapshots) == 1
    assert len(h.repo.items) == items_before
    assert len(h.audit.events) == 1


async def test_changed_inputs_supersede_the_previous_snapshot(h: Harness) -> None:
    first = h.repo.snapshots[0]

    second_id = await h.compile(
        activated_conditional_module_ids=frozenset({"lk.rta.module.mortgage_present"})
    )

    second = h.repo.snapshots[-1]
    assert second_id == second.id != first.id
    assert second.supersedes_id == first.id
    assert second.fingerprint != first.fingerprint
    assert h.audit.events[-1].before_ref == first.fingerprint
    # The earlier snapshot and its items are still there.
    assert any(i.snapshot_id == first.id for i in h.repo.items.values())


# ── Reads ───────────────────────────────────────────────────────────────────


async def test_checklist_view_reports_blocking_requirements(h: Harness) -> None:
    view = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)

    assert view.snapshot.id == h.repo.snapshots[0].id
    assert len(view.items) == len(h.repo.items)
    assert STATUTORY_ID in view.blocking_requirement_ids
    assert SIMPLE_ID not in view.blocking_requirement_ids
    assert all(v.lifecycle is ChecklistItemLifecycle.OPEN for v in view.items)
    assert (
        await h.service.blocking_requirement_ids(user_id=USER_ID, matter_id=MATTER_ID)
        == view.blocking_requirement_ids
    )


async def test_a_snapshot_is_not_readable_from_another_matter_or_user(h: Harness) -> None:
    snapshot_id = h.repo.snapshots[0].id
    with pytest.raises(ChecklistSnapshotNotFoundError):
        await h.service.get_checklist(
            user_id=USER_ID, matter_id="mat_other", snapshot_id=snapshot_id
        )
    with pytest.raises(ChecklistSnapshotNotFoundError):
        await h.service.get_checklist(user_id="usr_other", matter_id=MATTER_ID)


async def test_no_checklist_yet_reports_no_blockers_rather_than_failing() -> None:
    fresh = Harness()
    assert await fresh.service.blocking_requirement_ids(user_id=USER_ID, matter_id=MATTER_ID) == ()


async def test_an_item_whose_requirement_was_retired_is_left_out_of_the_view(h: Harness) -> None:
    retired = h.item_for(SIMPLE_ID)
    h.repo.items[retired.id].requirement_definition_id = "R_RETIRED_SYNTHETIC"

    view = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)

    assert len(view.items) == len(h.repo.items) - 1
    with pytest.raises(ChecklistItemNotFoundError) as excinfo:
        await h.service.decide_satisfaction(item_id=retired.id, expected_version=1, **WHO)
    assert excinfo.value.details == {"requirementId": "R_RETIRED_SYNTHETIC"}


# ── Decisions ───────────────────────────────────────────────────────────────


async def test_a_full_lawyer_review_computes_satisfied(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)

    view = await h.service.decide_satisfaction(
        item_id=item.id,
        expected_version=1,
        collection=CollectionStatus.RECEIVED,
        digital_review=DigitalReviewStatus.LAWYER_CONFIRMED,
        consistency=ConsistencyStatus.MATCHED,
        assigned_to="usr_clerk",
        **WHO,
    )

    assert view.item.resolution is ResolutionStatus.SATISFIED
    assert view.computed_resolution is ResolutionStatus.SATISFIED
    assert view.lifecycle is ChecklistItemLifecycle.SATISFIED
    assert view.blocks_approval is False
    assert view.item.version == 2
    assert view.item.assigned_to == "usr_clerk"
    event = h.audit.events[-1]
    assert event.action == AuditAction.RTA_CHECKLIST_ITEM_DECIDED.value
    assert event.before_ref == "REQUIRED/NOT_REQUESTED/UNREVIEWED/NOT_APPLICABLE/NOT_CHECKED/OPEN"
    assert event.after_ref == "REQUIRED/RECEIVED/LAWYER_CONFIRMED/NOT_APPLICABLE/MATCHED/SATISFIED"
    blocking = await h.service.blocking_requirement_ids(user_id=USER_ID, matter_id=MATTER_ID)
    assert STATUTORY_ID not in blocking


async def test_a_caller_cannot_declare_an_item_satisfied(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    with pytest.raises(SatisfactionIsComputedError):
        await h.service.decide_satisfaction(
            item_id=item.id, expected_version=1, resolution=ResolutionStatus.SATISFIED, **WHO
        )
    assert h.repo.items[item.id].resolution is ResolutionStatus.OPEN
    assert h.repo.items[item.id].version == 1


async def test_a_tracking_resolution_is_kept_until_the_item_is_genuinely_satisfied(
    h: Harness,
) -> None:
    item = h.item_for(STATUTORY_ID)

    tracked = await h.service.decide_satisfaction(
        item_id=item.id, expected_version=1, resolution=ResolutionStatus.REMEDIATED, **WHO
    )
    overridden = await h.service.decide_satisfaction(
        item_id=item.id,
        expected_version=2,
        resolution=ResolutionStatus.ACTION_REQUESTED,
        collection=CollectionStatus.RECEIVED,
        digital_review=DigitalReviewStatus.LAWYER_CONFIRMED,
        consistency=ConsistencyStatus.MATCHED,
        **WHO,
    )

    assert tracked.item.resolution is ResolutionStatus.REMEDIATED
    assert tracked.computed_resolution is ResolutionStatus.OPEN
    assert overridden.item.resolution is ResolutionStatus.SATISFIED


async def test_waiving_a_statutory_item_is_refused_and_nothing_is_saved(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    events_before = len(h.audit.events)

    with pytest.raises(StatutoryRequirementNotWaivableError):
        await h.service.decide_satisfaction(
            item_id=item.id,
            expected_version=1,
            applicability=ApplicabilityStatus.WAIVED_BY_LAWYER,
            reason="Not needed",
            **WHO,
        )

    assert h.repo.items[item.id].applicability is not ApplicabilityStatus.WAIVED_BY_LAWYER
    assert len(h.audit.events) == events_before


async def test_a_permitted_waiver_is_audited_as_a_waiver_with_its_reason(h: Harness) -> None:
    item = h.item_for(SIMPLE_ID)

    view = await h.service.decide_satisfaction(
        item_id=item.id,
        expected_version=1,
        applicability=ApplicabilityStatus.WAIVED_BY_LAWYER,
        reason="Reference held on the paper file.",
        **WHO,
    )

    assert view.item.resolution is ResolutionStatus.EXCEPTION_ACCEPTED
    assert view.item.applicability_decided_by == USER_ID
    assert view.lifecycle is ChecklistItemLifecycle.NOT_TRIGGERED
    event = h.audit.events[-1]
    assert event.action == AuditAction.RTA_CHECKLIST_ITEM_WAIVED.value
    assert event.reason == "Reference held on the paper file."


async def test_a_stale_version_is_a_conflict(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    with pytest.raises(ChecklistItemStaleError) as excinfo:
        await h.service.decide_satisfaction(
            item_id=item.id, expected_version=5, collection=CollectionStatus.REQUESTED, **WHO
        )
    assert excinfo.value.http_status == 409
    assert h.repo.items[item.id].collection is CollectionStatus.NOT_REQUESTED


async def test_items_of_another_matter_or_user_are_not_found(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    with pytest.raises(ChecklistItemNotFoundError):
        await h.service.decide_satisfaction(
            item_id=item.id, expected_version=1, **{**WHO, "matter_id": "mat_other"}
        )
    with pytest.raises(ChecklistItemNotFoundError):
        await h.service.decide_satisfaction(
            item_id=item.id, expected_version=1, **{**WHO, "user_id": "usr_other"}
        )


# ── Original inspection ─────────────────────────────────────────────────────


async def test_inspection_is_attributed_to_the_authenticated_actor(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)

    view = await h.service.record_original_inspection(
        item_id=item.id,
        expected_version=1,
        method="Sighted at the office",
        location="Colombo (synthetic)",
        **WHO,
    )

    inspection = view.item.original_inspection
    assert inspection is not None
    assert inspection.reviewer_id == USER_ID
    assert inspection.method == "Sighted at the office"
    assert view.item.physical_original is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    event = h.audit.events[-1]
    assert event.action == AuditAction.RTA_ORIGINAL_INSPECTION_RECORDED.value
    assert event.after_ref is not None and event.after_ref.startswith("ORIGINAL_INSPECTED@")
    assert event.reason == "method=Sighted at the office"


async def test_inspection_without_a_method_is_refused(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    with pytest.raises(OriginalInspectionRequiresHumanError):
        await h.service.record_original_inspection(
            item_id=item.id, expected_version=1, method="  ", **WHO
        )
    assert h.repo.items[item.id].original_inspection is None


# ── Document links ──────────────────────────────────────────────────────────


async def test_a_pipeline_link_is_ai_organized_and_a_lawyers_link_is_confirmed(
    h: Harness,
) -> None:
    item = h.item_for(STATUTORY_ID)

    machine = await h.service.link_document(item_id=item.id, detected_document_id="doc_1", **WHO)
    human = await h.service.link_document(
        item_id=item.id,
        detected_document_id="doc_2",
        lawyer_confirmed=True,
        evidence_reference_ids=("evr_1",),
        note="Checked against the register.",
        **WHO,
    )

    assert machine.digital_review is DigitalReviewStatus.AI_ORGANIZED
    assert machine.reviewed_by is None and machine.reviewed_at is None
    assert human.digital_review is DigitalReviewStatus.LAWYER_CONFIRMED
    assert human.reviewed_by == USER_ID and human.reviewed_at is not None
    assert human.evidence_reference_ids == ("evr_1",)
    assert h.audit.events[-1].after_ref == "link:doc_2"
    # Filing a document does not satisfy the item.
    assert h.repo.items[item.id].resolution is ResolutionStatus.OPEN


async def test_one_document_can_be_offered_towards_several_items(h: Harness) -> None:
    first, second = h.item_for(STATUTORY_ID), h.item_for(SIMPLE_ID)
    await h.service.link_document(item_id=first.id, detected_document_id="doc_combined", **WHO)
    await h.service.link_document(item_id=second.id, detected_document_id="doc_combined", **WHO)

    view = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)

    linked = {v.item.id: v for v in view.items if v.live_link_count}
    assert set(linked) == {first.id, second.id}
    assert all(v.lifecycle is ChecklistItemLifecycle.PARTIALLY_SATISFIED for v in linked.values())


async def test_replacing_a_document_supersedes_its_links_and_keeps_history(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    await h.service.link_document(item_id=item.id, detected_document_id="doc_1", **WHO)

    count = await h.service.supersede_document_links(
        user_id=USER_ID, detected_document_id="doc_1", replacement_link_id="lnk_new"
    )

    assert count == 1
    links = await h.service.list_links(user_id=USER_ID, item_id=item.id)
    assert len(links) == 1
    assert links[0].is_live is False
    assert links[0].superseded_by_link_id == "lnk_new"
    view = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)
    assert all(v.live_link_count == 0 for v in view.items)
    assert (
        await h.service.supersede_document_links(user_id=USER_ID, detected_document_id="doc_1") == 0
    )


async def test_linking_to_another_users_item_is_not_found(h: Harness) -> None:
    item = h.item_for(STATUTORY_ID)
    with pytest.raises(ChecklistItemNotFoundError):
        await h.service.link_document(
            item_id=item.id, detected_document_id="doc_1", **{**WHO, "user_id": "usr_other"}
        )
    assert h.repo.links == []
