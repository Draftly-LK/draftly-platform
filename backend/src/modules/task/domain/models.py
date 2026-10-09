"""Checklist snapshot, item, and satisfaction-link entities.

The item carries seven statuses that a single ``verified``/``missing`` enum would
destroy (§5.4). An item can legitimately be ``RECEIVED``, ``LAWYER_CONFIRMED``,
and still ``MISMATCH`` or ``EXPIRED`` — three facts a one-dimensional status
cannot express, and each of which changes what the lawyer must do next.

``resolution`` is never set to ``SATISFIED`` by a caller. It is computed by
`policies.compute_resolution` from the requirement's policy and the other six
dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.document.contracts import OriginalSourcePin


@dataclass(frozen=True)
class ChecklistSnapshot:
    """One compiled checklist, pinned to the rule versions that produced it.

    Snapshots are immutable and superseded rather than edited: a matter that was
    worked under one rule set must stay reconstructible after the rules change
    (§5.1, §13.2.7).
    """

    id: str
    user_id: str
    matter_id: str
    compiler_version: str
    taxonomy_version: str
    checklist_version: str
    rule_pack_version: str
    fingerprint: str
    module_definition_ids: tuple[str, ...]
    created_at: datetime
    created_by: str
    supersedes_id: str | None = None


@dataclass
class ChecklistItem:
    """One requirement placed on one matter, with its seven statuses."""

    id: str
    user_id: str
    matter_id: str
    snapshot_id: str
    requirement_definition_id: str
    module_definition_id: str
    inclusion_reason: str
    inclusion_trigger_id: str | None
    applicability: ApplicabilityStatus
    collection: CollectionStatus
    digital_review: DigitalReviewStatus
    physical_original: PhysicalOriginalStatus
    currency: CurrencyStatus
    consistency: ConsistencyStatus
    resolution: ResolutionStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1
    assigned_to: str | None = None
    due_at: datetime | None = None
    #: Reason recorded for NOT_APPLICABLE or WAIVED_BY_LAWYER (§5.4).
    applicability_reason: str | None = None
    applicability_decided_by: str | None = None
    local_authority_id: str | None = None
    #: Present only once an authorised human records it. Never model-derived.
    original_inspection: OriginalInspection | None = None
    inspection_history: tuple[OriginalInspection, ...] = ()


@dataclass(frozen=True)
class OriginalInspection:
    """A human's recorded inspection of a physical original (§5.4).

    Every field is required. An inspection without a named reviewer, a time, and
    a stated method is not an inspection — it is an assumption.
    """

    reviewer_id: str
    inspected_at: datetime
    method: str
    location: str | None = None
    note: str | None = None
    originals: tuple[OriginalSourcePin, ...] = ()


@dataclass
class SatisfactionLink:
    """One document offered towards one checklist item.

    Many-to-many on purpose: a combined local-authority certificate may satisfy
    several items, and each link carries its own reviewer decision (§5.4, §6.3).
    Superseding a document supersedes the link and keeps the history.
    """

    id: str
    user_id: str
    matter_id: str
    checklist_item_id: str
    detected_document_id: str
    digital_review: DigitalReviewStatus
    created_at: datetime
    created_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    superseded_by_link_id: str | None = None
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    document_version: int | None = None
    interpretation_generation: int | None = None
    originals: tuple[OriginalSourcePin, ...] = ()

    @property
    def is_live(self) -> bool:
        return (
            self.superseded_by_link_id is None
            and self.document_version is not None
            and self.interpretation_generation is not None
            and bool(self.originals)
            and self.digital_review is not DigitalReviewStatus.SUPERSEDED
            and self.digital_review is not DigitalReviewStatus.REJECTED
        )
