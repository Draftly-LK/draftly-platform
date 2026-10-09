"""Checklist item policies (§5.4): inspection needs a human, statutory items cannot
be waived, and SATISFIED is computed rather than chosen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    ChecklistItemLifecycle,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
    require_requirement,
)
from src.modules.task.domain.errors import (
    OriginalInspectionRequiresHumanError,
    SatisfactionIsComputedError,
    StatutoryRequirementNotWaivableError,
    WaiverReasonRequiredError,
)
from src.modules.task.domain.models import ChecklistItem, OriginalInspection, SatisfactionLink
from src.modules.task.domain.policies import (
    apply_applicability,
    apply_physical_original,
    compute_resolution,
    derive_lifecycle,
    guard_resolution_write,
    initial_item_statuses,
    is_blocking_unsatisfied,
    touch,
)

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)

#: Waivable, WARNING severity, no original, no currency window.
SIMPLE = require_requirement("R_C00_MATTER_AND_CLIENT_REFERENCE")
#: Not waivable, BLOCKING.
STATUTORY = require_requirement("R_C00_RESPONSIBLE_LAWYER_ASSIGNED")
#: Requires the physical original to be inspected; HIGH_RISK.
ORIGINAL = require_requirement("R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED")
#: 90-day currency window; HIGH_RISK.
CURRENCY = require_requirement("R_C00_SOURCE_CURRENCY_VERIFIED")


def test_fixture_requirements_have_the_policies_the_tests_assume() -> None:
    assert SIMPLE.waivable and SIMPLE.unsatisfied_severity.value == "WARNING"
    assert not STATUTORY.waivable and STATUTORY.unsatisfied_severity.value == "BLOCKING"
    assert ORIGINAL.physical_original_policy is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    assert CURRENCY.currency_max_age_days == 90


def item(requirement: Any = SIMPLE, **overrides: Any) -> ChecklistItem:
    collection, review, original, currency, consistency, resolution = initial_item_statuses(
        requirement
    )
    values: dict[str, Any] = {
        "id": "cli_1",
        "user_id": "usr_1",
        "matter_id": "mat_1",
        "snapshot_id": "snp_1",
        "requirement_definition_id": requirement.id,
        "module_definition_id": requirement.module_id,
        "inclusion_reason": "CORE",
        "inclusion_trigger_id": None,
        "applicability": ApplicabilityStatus.REQUIRED,
        "collection": collection,
        "digital_review": review,
        "physical_original": original,
        "currency": currency,
        "consistency": consistency,
        "resolution": resolution,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return ChecklistItem(**values)


def reviewed(requirement: Any = SIMPLE, **overrides: Any) -> ChecklistItem:
    """Received, lawyer-confirmed, and consistent — satisfied unless a policy objects."""
    values: dict[str, Any] = {
        "collection": CollectionStatus.RECEIVED,
        "digital_review": DigitalReviewStatus.LAWYER_CONFIRMED,
        "consistency": ConsistencyStatus.MATCHED,
    }
    values.update(overrides)
    return item(requirement, **values)


INSPECTION = OriginalInspection(reviewer_id="usr_1", inspected_at=NOW, method="Sighted at office")


# ── Initial statuses ────────────────────────────────────────────────────────


def test_a_new_item_asserts_nothing_nobody_has_looked_at() -> None:
    assert initial_item_statuses(SIMPLE) == (
        CollectionStatus.NOT_REQUESTED,
        DigitalReviewStatus.UNREVIEWED,
        PhysicalOriginalStatus.NOT_REQUIRED,
        CurrencyStatus.NOT_APPLICABLE,
        ConsistencyStatus.NOT_CHECKED,
        ResolutionStatus.OPEN,
    )


def test_an_original_requirement_starts_unknown_never_copy_only() -> None:
    assert initial_item_statuses(ORIGINAL)[2] is PhysicalOriginalStatus.UNKNOWN


def test_a_dated_requirement_starts_with_unknown_currency() -> None:
    assert initial_item_statuses(CURRENCY)[3] is CurrencyStatus.UNKNOWN


# ── Applicability and waivers ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "target", [ApplicabilityStatus.WAIVED_BY_LAWYER, ApplicabilityStatus.NOT_APPLICABLE]
)
def test_a_statutory_requirement_cannot_be_waived_or_declared_inapplicable(
    target: ApplicabilityStatus,
) -> None:
    subject = item(STATUTORY)
    with pytest.raises(StatutoryRequirementNotWaivableError) as excinfo:
        apply_applicability(
            subject, STATUTORY, target=target, reason="Partner said so", decided_by="usr_1"
        )
    assert excinfo.value.code == "rta_requirement_not_waivable"
    assert excinfo.value.details["requirementId"] == STATUTORY.id
    assert subject.applicability is ApplicabilityStatus.REQUIRED


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_a_waiver_needs_a_recorded_reason(reason: str | None) -> None:
    subject = item(SIMPLE)
    with pytest.raises(WaiverReasonRequiredError):
        apply_applicability(
            subject,
            SIMPLE,
            target=ApplicabilityStatus.WAIVED_BY_LAWYER,
            reason=reason,
            decided_by="usr_1",
        )
    assert subject.applicability is ApplicabilityStatus.REQUIRED


def test_a_reasoned_waiver_records_who_decided_and_why() -> None:
    subject = apply_applicability(
        item(SIMPLE),
        SIMPLE,
        target=ApplicabilityStatus.WAIVED_BY_LAWYER,
        reason="Reference held on the paper file.",
        decided_by="usr_1",
    )
    assert subject.applicability is ApplicabilityStatus.WAIVED_BY_LAWYER
    assert subject.applicability_reason == "Reference held on the paper file."
    assert subject.applicability_decided_by == "usr_1"


def test_marking_a_statutory_item_required_needs_no_reason() -> None:
    subject = apply_applicability(
        item(STATUTORY, applicability=ApplicabilityStatus.PROVISIONAL_REQUIRED),
        STATUTORY,
        target=ApplicabilityStatus.REQUIRED,
        reason=None,
        decided_by="usr_1",
    )
    assert subject.applicability is ApplicabilityStatus.REQUIRED


# ── Physical originals ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "inspection",
    [
        None,
        OriginalInspection(reviewer_id="", inspected_at=NOW, method="Sighted"),
        OriginalInspection(reviewer_id="usr_1", inspected_at=NOW, method="   "),
    ],
)
def test_a_scan_cannot_inspect_an_original(inspection: OriginalInspection | None) -> None:
    subject = item(ORIGINAL)
    with pytest.raises(OriginalInspectionRequiresHumanError) as excinfo:
        apply_physical_original(
            subject, target=PhysicalOriginalStatus.ORIGINAL_INSPECTED, inspection=inspection
        )
    assert excinfo.value.code == "rta_original_inspection_requires_human"
    assert subject.physical_original is PhysicalOriginalStatus.UNKNOWN
    assert subject.original_inspection is None


def test_a_named_human_inspection_is_recorded_on_the_item() -> None:
    subject = apply_physical_original(
        item(ORIGINAL), target=PhysicalOriginalStatus.ORIGINAL_INSPECTED, inspection=INSPECTION
    )
    assert subject.physical_original is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    assert subject.original_inspection == INSPECTION


def test_a_client_report_needs_no_inspection_and_records_none() -> None:
    subject = apply_physical_original(
        item(ORIGINAL), target=PhysicalOriginalStatus.ORIGINAL_REPORTED, inspection=None
    )
    assert subject.physical_original is PhysicalOriginalStatus.ORIGINAL_REPORTED
    assert subject.original_inspection is None


# ── Computed resolution ─────────────────────────────────────────────────────


def test_received_confirmed_and_matched_is_satisfied() -> None:
    assert compute_resolution(reviewed(), SIMPLE) is ResolutionStatus.SATISFIED


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"applicability": ApplicabilityStatus.NOT_APPLICABLE}, ResolutionStatus.CLOSED),
        (
            {"applicability": ApplicabilityStatus.WAIVED_BY_LAWYER},
            ResolutionStatus.EXCEPTION_ACCEPTED,
        ),
        ({"collection": CollectionStatus.REQUESTED}, ResolutionStatus.ACTION_REQUESTED),
        ({"collection": CollectionStatus.MISSING}, ResolutionStatus.ACTION_REQUESTED),
        ({"collection": CollectionStatus.PARTIAL}, ResolutionStatus.OPEN),
        ({"collection": CollectionStatus.NOT_REQUESTED}, ResolutionStatus.OPEN),
        # The pipeline can file a document; it cannot confirm it.
        ({"digital_review": DigitalReviewStatus.AI_ORGANIZED}, ResolutionStatus.OPEN),
        ({"digital_review": DigitalReviewStatus.UNREVIEWED}, ResolutionStatus.OPEN),
        ({"consistency": ConsistencyStatus.MISMATCH}, ResolutionStatus.ACTION_REQUESTED),
        ({"consistency": ConsistencyStatus.INCONCLUSIVE}, ResolutionStatus.ACTION_REQUESTED),
        ({"consistency": ConsistencyStatus.NOT_CHECKED}, ResolutionStatus.OPEN),
        ({"currency": CurrencyStatus.STALE}, ResolutionStatus.ACTION_REQUESTED),
        ({"currency": CurrencyStatus.EXPIRED}, ResolutionStatus.ACTION_REQUESTED),
    ],
)
def test_any_unmet_dimension_keeps_the_item_unsatisfied(
    overrides: dict[str, Any], expected: ResolutionStatus
) -> None:
    assert compute_resolution(reviewed(**overrides), SIMPLE) is expected


@pytest.mark.parametrize(
    "status",
    [
        PhysicalOriginalStatus.UNKNOWN,
        PhysicalOriginalStatus.COPY_ONLY,
        PhysicalOriginalStatus.ORIGINAL_REPORTED,
    ],
)
def test_an_original_requirement_is_not_satisfied_by_a_copy_or_a_report(
    status: PhysicalOriginalStatus,
) -> None:
    subject = reviewed(ORIGINAL, physical_original=status)
    assert compute_resolution(subject, ORIGINAL) is ResolutionStatus.ACTION_REQUESTED


def test_an_inspected_original_satisfies_the_requirement() -> None:
    subject = reviewed(ORIGINAL, physical_original=PhysicalOriginalStatus.ORIGINAL_INSPECTED)
    assert compute_resolution(subject, ORIGINAL) is ResolutionStatus.SATISFIED


def test_a_dated_requirement_needs_current_evidence_not_merely_non_stale() -> None:
    unknown = reviewed(CURRENCY, currency=CurrencyStatus.UNKNOWN)
    current = reviewed(CURRENCY, currency=CurrencyStatus.CURRENT)
    assert compute_resolution(unknown, CURRENCY) is ResolutionStatus.ACTION_REQUESTED
    assert compute_resolution(current, CURRENCY) is ResolutionStatus.SATISFIED


def test_satisfied_cannot_be_written_by_hand() -> None:
    with pytest.raises(SatisfactionIsComputedError) as excinfo:
        guard_resolution_write(ResolutionStatus.SATISFIED)
    assert excinfo.value.code == "rta_satisfaction_is_computed"
    for status in set(ResolutionStatus) - {ResolutionStatus.SATISFIED}:
        guard_resolution_write(status)


# ── Lifecycle and blocking ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("subject", "links", "expected"),
    [
        (item(), 0, ChecklistItemLifecycle.OPEN),
        (item(), 1, ChecklistItemLifecycle.PARTIALLY_SATISFIED),
        (item(collection=CollectionStatus.REQUESTED), 0, ChecklistItemLifecycle.REQUESTED),
        (item(collection=CollectionStatus.MISSING), 3, ChecklistItemLifecycle.MISSING),
        (
            item(
                collection=CollectionStatus.RECEIVED,
                digital_review=DigitalReviewStatus.AI_ORGANIZED,
            ),
            1,
            ChecklistItemLifecycle.PARTIALLY_SATISFIED,
        ),
        (
            reviewed(consistency=ConsistencyStatus.NOT_CHECKED),
            1,
            ChecklistItemLifecycle.REVIEW_READY,
        ),
        (item(collection=CollectionStatus.RECEIVED), 0, ChecklistItemLifecycle.OPEN),
        (reviewed(), 0, ChecklistItemLifecycle.SATISFIED),
        (
            reviewed(applicability=ApplicabilityStatus.WAIVED_BY_LAWYER),
            1,
            ChecklistItemLifecycle.NOT_TRIGGERED,
        ),
        (
            item(applicability=ApplicabilityStatus.NOT_APPLICABLE),
            0,
            ChecklistItemLifecycle.NOT_TRIGGERED,
        ),
    ],
)
def test_lifecycle_is_derived_from_the_dimensions(
    subject: ChecklistItem, links: int, expected: ChecklistItemLifecycle
) -> None:
    assert derive_lifecycle(subject, SIMPLE, live_link_count=links) is expected


def test_only_unsatisfied_blocking_or_high_risk_items_block_approval() -> None:
    assert is_blocking_unsatisfied(item(STATUTORY), STATUTORY) is True
    assert is_blocking_unsatisfied(item(ORIGINAL), ORIGINAL) is True
    assert is_blocking_unsatisfied(reviewed(STATUTORY), STATUTORY) is False
    # A warning-level item never blocks, satisfied or not.
    assert is_blocking_unsatisfied(item(SIMPLE), SIMPLE) is False


def test_a_waived_item_does_not_block() -> None:
    waived = item(ORIGINAL, applicability=ApplicabilityStatus.WAIVED_BY_LAWYER)
    assert is_blocking_unsatisfied(waived, ORIGINAL) is False


def test_touch_updates_only_the_timestamp() -> None:
    subject = item()
    later = NOW + timedelta(hours=1)
    assert touch(subject, now=later).updated_at == later
    assert subject.created_at == NOW


# ── Satisfaction links ──────────────────────────────────────────────────────


def _link(**overrides: Any) -> SatisfactionLink:
    from src.modules.document.contracts import OriginalSourcePin

    values: dict[str, Any] = {
        "id": "lnk_1",
        "user_id": "usr_1",
        "matter_id": "mat_1",
        "checklist_item_id": "cli_1",
        "detected_document_id": "doc_1",
        "document_version": 1,
        "interpretation_generation": 1,
        "originals": (OriginalSourcePin("src_1", "a" * 64, "1"),),
        "digital_review": DigitalReviewStatus.AI_ORGANIZED,
        "created_at": NOW,
        "created_by": "usr_1",
    }
    values.update(overrides)
    return SatisfactionLink(**values)


def test_rejected_and_superseded_links_do_not_count_as_live() -> None:
    assert _link().is_live
    assert _link(digital_review=DigitalReviewStatus.LAWYER_CONFIRMED).is_live
    assert not _link(digital_review=DigitalReviewStatus.REJECTED).is_live
    assert not _link(digital_review=DigitalReviewStatus.SUPERSEDED).is_live
    assert not _link(superseded_by_link_id="lnk_2").is_live


def test_legacy_unbound_link_is_history_only():
    assert not _link(document_version=None, interpretation_generation=None, originals=()).is_live
