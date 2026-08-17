"""Checklist item policies — what makes an item satisfied, and what may not.

Three rules in this file carry the legal safety of the checklist:

1. **A scan cannot inspect an original.** ``ORIGINAL_INSPECTED`` is reachable
   only by passing an `OriginalInspection` built from a named human reviewer.
   `apply_physical_original` refuses the status otherwise, whatever the caller
   claims (§Executive 5, §5.4).
2. **A waiver cannot reach a statutory requirement**, and cannot turn absent
   evidence into a fact. Non-waivable requirements refuse both
   ``WAIVED_BY_LAWYER`` and ``NOT_APPLICABLE`` (§5.4).
3. **``SATISFIED`` is computed, not chosen.** It requires the requirement's own
   policy to be met on every dimension the requirement cares about, so an item
   cannot be closed while it is still ``MISMATCH`` or ``EXPIRED`` (§5.4).
"""

from __future__ import annotations

from datetime import datetime

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
)
from src.modules.task.domain.errors import (
    OriginalInspectionRequiresHumanError,
    SatisfactionIsComputedError,
    StatutoryRequirementNotWaivableError,
    WaiverReasonRequiredError,
)
from src.modules.task.domain.models import ChecklistItem, OriginalInspection

#: Applicability values that end the item without evidence and therefore need an
#: explicit human decision with a reason (§5.4, §10.4).
_DECISION_REQUIRED_APPLICABILITY = frozenset(
    {ApplicabilityStatus.NOT_APPLICABLE, ApplicabilityStatus.WAIVED_BY_LAWYER}
)


def initial_item_statuses(
    requirement: RequirementDefinition,
) -> tuple[
    CollectionStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    CurrencyStatus,
    ConsistencyStatus,
    ResolutionStatus,
]:
    """The honest starting state for a newly compiled item.

    Physical-original status starts ``UNKNOWN`` where the requirement wants an
    original and ``NOT_REQUIRED`` where it does not — never ``COPY_ONLY``, which
    would assert something nobody has looked at yet.
    """
    wants_original = requirement.physical_original_policy is not PhysicalOriginalStatus.NOT_REQUIRED
    return (
        CollectionStatus.NOT_REQUESTED,
        DigitalReviewStatus.UNREVIEWED,
        PhysicalOriginalStatus.UNKNOWN if wants_original else PhysicalOriginalStatus.NOT_REQUIRED,
        CurrencyStatus.UNKNOWN
        if requirement.currency_max_age_days is not None
        else CurrencyStatus.NOT_APPLICABLE,
        ConsistencyStatus.NOT_CHECKED,
        ResolutionStatus.OPEN,
    )


def apply_applicability(
    item: ChecklistItem,
    requirement: RequirementDefinition,
    *,
    target: ApplicabilityStatus,
    reason: str | None,
    decided_by: str,
) -> ChecklistItem:
    """Change applicability, refusing waivers a lawyer is not permitted to make."""
    if target in _DECISION_REQUIRED_APPLICABILITY:
        if not requirement.waivable:
            raise StatutoryRequirementNotWaivableError(
                requirementId=requirement.id,
                blockerKind=requirement.unsatisfied_blocker_kind.value,
            )
        if not (reason or "").strip():
            raise WaiverReasonRequiredError(requirementId=requirement.id)
    item.applicability = target
    item.applicability_reason = reason
    item.applicability_decided_by = decided_by
    return item


def apply_physical_original(
    item: ChecklistItem,
    *,
    target: PhysicalOriginalStatus,
    inspection: OriginalInspection | None,
) -> ChecklistItem:
    """Set physical-original status.

    ``ORIGINAL_REPORTED`` is what a client saying "I have the original" produces.
    ``ORIGINAL_INSPECTED`` is what a reviewer physically looking at it produces,
    and it is the only status that requires an `OriginalInspection`.
    """
    if target is PhysicalOriginalStatus.ORIGINAL_INSPECTED:
        if inspection is None or not inspection.reviewer_id or not inspection.method.strip():
            raise OriginalInspectionRequiresHumanError()
        item.original_inspection = inspection
    item.physical_original = target
    return item


def compute_resolution(item: ChecklistItem, requirement: RequirementDefinition) -> ResolutionStatus:
    """Derive the resolution status from the requirement policy and the item.

    Returns the *computed* value; the caller stores it. Anything unresolved
    stays ``OPEN`` or ``ACTION_REQUESTED`` rather than being rounded up.
    """
    if item.applicability is ApplicabilityStatus.NOT_APPLICABLE:
        return ResolutionStatus.CLOSED
    if item.applicability is ApplicabilityStatus.WAIVED_BY_LAWYER:
        return ResolutionStatus.EXCEPTION_ACCEPTED

    if item.collection in {CollectionStatus.REQUESTED, CollectionStatus.MISSING}:
        return ResolutionStatus.ACTION_REQUESTED
    if item.collection is not CollectionStatus.RECEIVED:
        return ResolutionStatus.OPEN

    if item.digital_review is not DigitalReviewStatus.LAWYER_CONFIRMED:
        # AI_ORGANIZED is explicitly not enough: the pipeline can file a
        # document, it cannot confirm it (§6.4).
        return ResolutionStatus.OPEN

    wants_original = requirement.physical_original_policy is not PhysicalOriginalStatus.NOT_REQUIRED
    if wants_original and item.physical_original is not PhysicalOriginalStatus.ORIGINAL_INSPECTED:
        return ResolutionStatus.ACTION_REQUESTED

    if item.currency in {CurrencyStatus.STALE, CurrencyStatus.EXPIRED}:
        return ResolutionStatus.ACTION_REQUESTED
    if (
        requirement.currency_max_age_days is not None
        and item.currency is not CurrencyStatus.CURRENT
    ):
        return ResolutionStatus.ACTION_REQUESTED

    if item.consistency in {ConsistencyStatus.MISMATCH, ConsistencyStatus.INCONCLUSIVE}:
        return ResolutionStatus.ACTION_REQUESTED
    if item.consistency is ConsistencyStatus.NOT_CHECKED:
        return ResolutionStatus.OPEN

    return ResolutionStatus.SATISFIED


def guard_resolution_write(target: ResolutionStatus) -> None:
    """Reject a caller trying to set SATISFIED by hand."""
    if target is ResolutionStatus.SATISFIED:
        raise SatisfactionIsComputedError()


def derive_lifecycle(
    item: ChecklistItem, requirement: RequirementDefinition, *, live_link_count: int
) -> ChecklistItemLifecycle:
    """The single derived value the UI groups by (§10.4). Never stored as truth."""
    if item.applicability in {
        ApplicabilityStatus.NOT_APPLICABLE,
        ApplicabilityStatus.WAIVED_BY_LAWYER,
    }:
        return ChecklistItemLifecycle.NOT_TRIGGERED
    if compute_resolution(item, requirement) is ResolutionStatus.SATISFIED:
        return ChecklistItemLifecycle.SATISFIED
    if item.collection is CollectionStatus.MISSING:
        return ChecklistItemLifecycle.MISSING
    if item.collection is CollectionStatus.REQUESTED:
        return ChecklistItemLifecycle.REQUESTED
    if item.collection is CollectionStatus.RECEIVED and live_link_count > 0:
        if item.digital_review is DigitalReviewStatus.LAWYER_CONFIRMED:
            return ChecklistItemLifecycle.REVIEW_READY
        return ChecklistItemLifecycle.PARTIALLY_SATISFIED
    if live_link_count > 0:
        return ChecklistItemLifecycle.PARTIALLY_SATISFIED
    return ChecklistItemLifecycle.OPEN


def is_blocking_unsatisfied(item: ChecklistItem, requirement: RequirementDefinition) -> bool:
    """Whether this item currently blocks approval or registration-ready export."""
    if item.applicability in {
        ApplicabilityStatus.NOT_APPLICABLE,
        ApplicabilityStatus.WAIVED_BY_LAWYER,
    }:
        return False
    if compute_resolution(item, requirement) is ResolutionStatus.SATISFIED:
        return False
    return requirement.unsatisfied_severity.value in {"BLOCKING", "HIGH_RISK"}


def touch(item: ChecklistItem, *, now: datetime) -> ChecklistItem:
    item.updated_at = now
    return item
