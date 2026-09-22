"""Checklist item policies: the three rules policies.py says carry legal safety.

1. A scan cannot inspect an original.
2. A waiver cannot reach a statutory requirement.
3. SATISFIED is computed, not chosen, and only when every dimension the
   requirement cares about is met.

Rule 3 is checked across every combination of the five status axes, so no
corner of the truth table can round an unresolved item up to satisfied.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

import pytest

from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    ChecklistItemLifecycle,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    RequirementDefinition,
    ResolutionStatus,
    require_requirement,
)
from src.modules.task.domain.errors import (
    CollectionTransitionNotAdministrativeError,
    OriginalInspectionRequiresHumanError,
    SatisfactionIsComputedError,
    StatutoryRequirementNotWaivableError,
    WaiverReasonRequiredError,
)
from src.modules.task.domain.models import ChecklistItem, OriginalInspection
from src.modules.task.domain.policies import (
    apply_applicability,
    apply_physical_original,
    compute_resolution,
    derive_lifecycle,
    guard_administrative_collection,
    guard_resolution_write,
    initial_item_statuses,
    is_blocking_unsatisfied,
)
from tests.factories.checklist import checklist_item
from tests.factories.constants import NOW, USER_A

WAIVABLE = require_requirement("R_C00_MATTER_AND_CLIENT_REFERENCE")
STATUTORY = require_requirement("R_C00_RESPONSIBLE_LAWYER_ASSIGNED")
#: A requirement that wants an inspected original and a current document.
STRICT = replace(
    WAIVABLE,
    physical_original_policy=PhysicalOriginalStatus.ORIGINAL_INSPECTED,
    currency_max_age_days=30,
)
#: One that wants neither.
LENIENT = replace(
    WAIVABLE,
    physical_original_policy=PhysicalOriginalStatus.NOT_REQUIRED,
    currency_max_age_days=None,
)
INSPECTION = OriginalInspection(reviewer_id=USER_A, inspected_at=NOW, method="in person")


def _satisfied_item(**overrides: object) -> ChecklistItem:
    """An item that meets STRICT on every dimension."""
    item = checklist_item(
        collection=CollectionStatus.RECEIVED,
        digital_review=DigitalReviewStatus.LAWYER_CONFIRMED,
        physical_original=PhysicalOriginalStatus.ORIGINAL_INSPECTED,
        currency=CurrencyStatus.CURRENT,
        consistency=ConsistencyStatus.MATCHED,
    )
    return replace(item, **overrides)  # type: ignore[arg-type]


# ── Rule 3: SATISFIED is computed ───────────────────────────────────────────


def test_an_item_meeting_every_dimension_is_satisfied() -> None:
    assert compute_resolution(_satisfied_item(), STRICT) is ResolutionStatus.SATISFIED


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"collection": CollectionStatus.REQUESTED}, ResolutionStatus.ACTION_REQUESTED),
        ({"collection": CollectionStatus.MISSING}, ResolutionStatus.ACTION_REQUESTED),
        ({"collection": CollectionStatus.PARTIAL}, ResolutionStatus.OPEN),
        ({"digital_review": DigitalReviewStatus.AI_ORGANIZED}, ResolutionStatus.OPEN),
        (
            {"physical_original": PhysicalOriginalStatus.ORIGINAL_REPORTED},
            ResolutionStatus.ACTION_REQUESTED,
        ),
        (
            {"physical_original": PhysicalOriginalStatus.COPY_ONLY},
            ResolutionStatus.ACTION_REQUESTED,
        ),
        ({"currency": CurrencyStatus.EXPIRED}, ResolutionStatus.ACTION_REQUESTED),
        ({"currency": CurrencyStatus.UNKNOWN}, ResolutionStatus.ACTION_REQUESTED),
        ({"consistency": ConsistencyStatus.MISMATCH}, ResolutionStatus.ACTION_REQUESTED),
        ({"consistency": ConsistencyStatus.NOT_CHECKED}, ResolutionStatus.OPEN),
    ],
    ids=lambda v: next(iter(v.values())).name if isinstance(v, dict) else v.name,
)
def test_one_unmet_dimension_keeps_the_item_open(
    change: dict[str, object], expected: ResolutionStatus
) -> None:
    assert compute_resolution(_satisfied_item(**change), STRICT) is expected


def test_the_pipeline_filing_a_document_is_not_a_lawyer_confirming_it() -> None:
    """AI_ORGANIZED is explicitly not enough (§6.4)."""
    item = _satisfied_item(digital_review=DigitalReviewStatus.AI_ORGANIZED)

    assert compute_resolution(item, LENIENT) is not ResolutionStatus.SATISFIED


AXES = list(
    itertools.product(
        CollectionStatus,
        DigitalReviewStatus,
        PhysicalOriginalStatus,
        CurrencyStatus,
        ConsistencyStatus,
    )
)


@pytest.mark.parametrize("requirement", [STRICT, LENIENT], ids=["strict", "lenient"])
def test_no_combination_is_satisfied_unless_every_rule_holds(
    requirement: RequirementDefinition,
) -> None:
    """Every combination of the five axes, for a requirement of each kind."""
    wants_original = requirement.physical_original_policy is not PhysicalOriginalStatus.NOT_REQUIRED
    wants_current = requirement.currency_max_age_days is not None
    wrongly_satisfied = []
    for collection, review, original, currency, consistency in AXES:
        item = checklist_item(
            collection=collection,
            digital_review=review,
            physical_original=original,
            currency=currency,
            consistency=consistency,
        )
        if compute_resolution(item, requirement) is not ResolutionStatus.SATISFIED:
            continue
        rules_hold = (
            collection is CollectionStatus.RECEIVED
            and review is DigitalReviewStatus.LAWYER_CONFIRMED
            and (not wants_original or original is PhysicalOriginalStatus.ORIGINAL_INSPECTED)
            and currency not in {CurrencyStatus.STALE, CurrencyStatus.EXPIRED}
            and (not wants_current or currency is CurrencyStatus.CURRENT)
            and consistency is ConsistencyStatus.MATCHED
        )
        if not rules_hold:
            wrongly_satisfied.append((collection, review, original, currency, consistency))

    assert len(AXES) == 5 * 5 * 5 * 5 * 4
    assert wrongly_satisfied == []


@pytest.mark.parametrize("target", list(ResolutionStatus))
def test_satisfied_cannot_be_written_by_hand(target: ResolutionStatus) -> None:
    if target is ResolutionStatus.SATISFIED:
        with pytest.raises(SatisfactionIsComputedError):
            guard_resolution_write(target)
    else:
        guard_resolution_write(target)


# ── Rule 2: statutory requirements cannot be waived ─────────────────────────


@pytest.mark.parametrize(
    "target", [ApplicabilityStatus.NOT_APPLICABLE, ApplicabilityStatus.WAIVED_BY_LAWYER]
)
def test_a_statutory_requirement_cannot_be_waived_even_with_a_reason(
    target: ApplicabilityStatus,
) -> None:
    assert not STATUTORY.waivable

    with pytest.raises(StatutoryRequirementNotWaivableError):
        apply_applicability(
            checklist_item(), STATUTORY, target=target, reason="synthetic reason", decided_by=USER_A
        )


@pytest.mark.parametrize(
    "target", [ApplicabilityStatus.NOT_APPLICABLE, ApplicabilityStatus.WAIVED_BY_LAWYER]
)
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_a_waiver_needs_a_reason(target: ApplicabilityStatus, reason: str | None) -> None:
    with pytest.raises(WaiverReasonRequiredError):
        apply_applicability(
            checklist_item(), WAIVABLE, target=target, reason=reason, decided_by=USER_A
        )


def test_a_waiver_with_a_reason_records_who_decided() -> None:
    item = apply_applicability(
        checklist_item(),
        WAIVABLE,
        target=ApplicabilityStatus.WAIVED_BY_LAWYER,
        reason="Synthetic reason",
        decided_by=USER_A,
    )

    assert (item.applicability, item.applicability_decided_by) == (
        ApplicabilityStatus.WAIVED_BY_LAWYER,
        USER_A,
    )
    assert compute_resolution(item, WAIVABLE) is ResolutionStatus.EXCEPTION_ACCEPTED


def test_marking_a_statutory_requirement_required_needs_no_reason() -> None:
    item = apply_applicability(
        checklist_item(),
        STATUTORY,
        target=ApplicabilityStatus.REQUIRED,
        reason=None,
        decided_by=USER_A,
    )

    assert item.applicability is ApplicabilityStatus.REQUIRED


# ── Rule 1: a scan cannot inspect an original ───────────────────────────────


@pytest.mark.parametrize(
    "inspection",
    [
        None,
        replace(INSPECTION, reviewer_id=""),
        replace(INSPECTION, method="   "),
    ],
    ids=["none", "no-reviewer", "no-method"],
)
def test_an_inspected_original_needs_a_named_reviewer_and_method(
    inspection: OriginalInspection | None,
) -> None:
    with pytest.raises(OriginalInspectionRequiresHumanError):
        apply_physical_original(
            checklist_item(),
            target=PhysicalOriginalStatus.ORIGINAL_INSPECTED,
            inspection=inspection,
        )


def test_an_inspection_by_a_reviewer_is_recorded() -> None:
    item = apply_physical_original(
        checklist_item(), target=PhysicalOriginalStatus.ORIGINAL_INSPECTED, inspection=INSPECTION
    )

    assert item.physical_original is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    assert item.original_inspection == INSPECTION


def test_a_client_reporting_the_original_needs_no_inspection() -> None:
    item = apply_physical_original(
        checklist_item(), target=PhysicalOriginalStatus.ORIGINAL_REPORTED, inspection=None
    )

    assert item.physical_original is PhysicalOriginalStatus.ORIGINAL_REPORTED


# ── Starting state, administration, lifecycle ───────────────────────────────


@pytest.mark.parametrize(
    ("requirement", "original", "currency"),
    [
        (STRICT, PhysicalOriginalStatus.UNKNOWN, CurrencyStatus.UNKNOWN),
        (LENIENT, PhysicalOriginalStatus.NOT_REQUIRED, CurrencyStatus.NOT_APPLICABLE),
    ],
    ids=["strict", "lenient"],
)
def test_a_new_item_starts_honestly(
    requirement: RequirementDefinition,
    original: PhysicalOriginalStatus,
    currency: CurrencyStatus,
) -> None:
    """Never COPY_ONLY: that would assert something nobody has looked at."""
    collection, review, physical, current, consistency, resolution = initial_item_statuses(
        requirement
    )

    assert (collection, review, consistency, resolution) == (
        CollectionStatus.NOT_REQUESTED,
        DigitalReviewStatus.UNREVIEWED,
        ConsistencyStatus.NOT_CHECKED,
        ResolutionStatus.OPEN,
    )
    assert (physical, current) == (original, currency)


@pytest.mark.parametrize("target", [CollectionStatus.REQUESTED, CollectionStatus.RECEIVED])
def test_requested_and_received_are_administrative(target: CollectionStatus) -> None:
    guard_administrative_collection(current=CollectionStatus.NOT_REQUESTED, target=target)


@pytest.mark.parametrize(
    "target", [CollectionStatus.MISSING, CollectionStatus.PARTIAL, CollectionStatus.NOT_REQUESTED]
)
def test_other_collection_changes_are_a_lawyers_decision(target: CollectionStatus) -> None:
    with pytest.raises(CollectionTransitionNotAdministrativeError):
        guard_administrative_collection(current=CollectionStatus.REQUESTED, target=target)


@pytest.mark.parametrize("current", [CollectionStatus.PARTIAL, CollectionStatus.RECEIVED])
def test_received_evidence_is_never_requested_again(current: CollectionStatus) -> None:
    """Requesting it again would quietly erase the record that it arrived."""
    with pytest.raises(CollectionTransitionNotAdministrativeError):
        guard_administrative_collection(current=current, target=CollectionStatus.REQUESTED)


@pytest.mark.parametrize(
    ("item", "links", "lifecycle"),
    [
        (
            checklist_item(applicability=ApplicabilityStatus.NOT_APPLICABLE),
            0,
            ChecklistItemLifecycle.NOT_TRIGGERED,
        ),
        (_satisfied_item(), 1, ChecklistItemLifecycle.SATISFIED),
        (checklist_item(collection=CollectionStatus.MISSING), 0, ChecklistItemLifecycle.MISSING),
        (
            checklist_item(collection=CollectionStatus.REQUESTED),
            0,
            ChecklistItemLifecycle.REQUESTED,
        ),
        (
            _satisfied_item(consistency=ConsistencyStatus.NOT_CHECKED),
            1,
            ChecklistItemLifecycle.REVIEW_READY,
        ),
        (
            _satisfied_item(digital_review=DigitalReviewStatus.AI_ORGANIZED),
            1,
            ChecklistItemLifecycle.PARTIALLY_SATISFIED,
        ),
        (checklist_item(collection=CollectionStatus.NOT_REQUESTED), 0, ChecklistItemLifecycle.OPEN),
    ],
    ids=["waived", "satisfied", "missing", "requested", "review-ready", "partial", "open"],
)
def test_the_lifecycle_the_ui_groups_by(
    item: ChecklistItem, links: int, lifecycle: ChecklistItemLifecycle
) -> None:
    assert derive_lifecycle(item, STRICT, live_link_count=links) is lifecycle


def test_an_unsatisfied_blocking_item_blocks_and_a_waived_one_does_not() -> None:
    blocking = replace(STRICT, unsatisfied_severity=type(STRICT.unsatisfied_severity)("BLOCKING"))

    assert is_blocking_unsatisfied(checklist_item(), blocking) is True
    assert is_blocking_unsatisfied(_satisfied_item(), blocking) is False
    assert (
        is_blocking_unsatisfied(
            checklist_item(applicability=ApplicabilityStatus.WAIVED_BY_LAWYER), blocking
        )
        is False
    )
