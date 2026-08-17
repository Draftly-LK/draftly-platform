"""Checklist domain errors."""

from __future__ import annotations

from src.platform.errors import ConflictError, DomainRuleError, NotFoundError


class ChecklistSnapshotNotFoundError(NotFoundError):
    code = "checklist_snapshot_not_found"
    message = "The requested checklist snapshot was not found."


class ChecklistItemNotFoundError(NotFoundError):
    code = "checklist_item_not_found"
    message = "The requested checklist item was not found."


class OriginalInspectionRequiresHumanError(DomainRuleError):
    """No scan, OCR result, or model confidence may set ORIGINAL_INSPECTED.

    The error exists so the rule is a hard failure with a name, not a comment
    someone can quietly step around (§Executive 5, §5.4).
    """

    code = "rta_original_inspection_requires_human"
    message = (
        "Recording inspection of a physical original requires an authorised human "
        "reviewer, a timestamp, and an inspection method. It cannot be derived from "
        "a scan, an extraction result, or a confidence score."
    )


class StatutoryRequirementNotWaivableError(DomainRuleError):
    code = "rta_requirement_not_waivable"
    message = (
        "This requirement cannot be waived. A lawyer waiver cannot set aside a "
        "statutory prohibition or turn absent evidence into a fact."
    )


class WaiverReasonRequiredError(DomainRuleError):
    code = "rta_waiver_reason_required"
    message = "Marking a requirement waived or not applicable requires a recorded reason."


class SatisfactionIsComputedError(DomainRuleError):
    """`SATISFIED` is derived from the requirement policy, not a button (§5.4)."""

    code = "rta_satisfaction_is_computed"
    message = (
        "Resolution cannot be set to SATISFIED directly. It is computed from the "
        "requirement's policy and the item's collection, review, original, "
        "currency, and consistency status."
    )


class ChecklistItemStaleError(ConflictError):
    code = "checklist_item_version_stale"
    message = "The checklist item changed since your last read."
