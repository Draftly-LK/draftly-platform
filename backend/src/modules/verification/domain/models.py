"""Evidence references, extracted facts, and review decisions.

A fact is never edited. Confirming it creates a new version whose status is
``LAWYER_CONFIRMED``; correcting it creates another whose ``supersedes_fact_id``
points back, and the prior version is marked ``SUPERSEDED`` and kept. The
original model output therefore stays in the record permanently, which is what
makes an approved form auditable after the fact (§6.5, §10.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.content_governance.contracts import (
    EvidenceRegionType,
    FactStatus,
    ReviewTargetType,
)


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    #: Which coordinate space the numbers are in, so a box rendered at a
    #: different DPI than it was measured at still lands in the right place.
    coordinate_space: str


@dataclass(frozen=True)
class EvidenceReference:
    """Exactly where a value was read from.

    ``source_sha256`` is stored on the reference, not only on the source file:
    it is what proves the evidence still points at the same bytes that were
    reviewed (§7.1, plan §5.3 invariant 1).
    """

    id: str
    user_id: str
    matter_id: str
    source_file_id: str
    page_number: int
    source_sha256: str
    created_at: datetime
    bounding_box: BoundingBox | None = None
    text_span: str | None = None
    region_type: EvidenceRegionType | None = None
    extraction_run_id: str | None = None
    detected_document_id: str | None = None


@dataclass(frozen=True)
class ExtractedFact:
    """One version of one fact about one matter."""

    id: str
    user_id: str
    matter_id: str
    fact_type_id: str
    value: Any
    status: FactStatus
    created_at: datetime
    version: int = 1
    normalized_value: Any = None
    subject_id: str | None = None
    #: The provider's own estimate. It routes work to a human; it never
    #: verifies anything (§6.4).
    model_reported_confidence: float | None = None
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    derivation_kind: str | None = None
    derivation_input_fact_ids: tuple[str, ...] = field(default_factory=tuple)
    derivation_formula_version: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_decision_id: str | None = None
    supersedes_fact_id: str | None = None
    superseded_by_fact_id: str | None = None
    #: Set when the fact is bound into an approved form, so a later correction
    #: can be detected as making that form stale rather than silently changing
    #: what was approved (§10.5, §10.7).
    locked_by_form_id: str | None = None

    @property
    def is_confirmed(self) -> bool:
        return self.status in {FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM}

    @property
    def is_live(self) -> bool:
        return self.status is not FactStatus.SUPERSEDED and self.superseded_by_fact_id is None


@dataclass(frozen=True)
class ReviewDecision:
    """An immutable record of one human decision.

    Corrections never overwrite the OCR or model event; they produce one of
    these alongside a new fact version (§6.5).
    """

    id: str
    user_id: str
    matter_id: str
    target_type: ReviewTargetType
    target_id: str
    decision: str
    reviewer_id: str
    reviewer_role: str
    created_at: datetime
    previous_value: Any = None
    new_value: Any = None
    reason: str | None = None
