"""Domain models for a processing run's output.

Everything here is a *candidate* derivative — non-authoritative, rebuildable,
and lawyer-gated. No value in this module ever becomes a verified particular;
that promotion belongs to verification_service (document-processing.md §1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from src.modules.document.ports import CandidateField


class ProcessingOutcome(StrEnum):
    """Terminal state of one processing attempt.

    ``MANUAL_REVIEW`` is a legitimate, expected state (§5 Level 3, §10A) —
    the pipeline routing a document to a human is success, not failure.
    """

    EXTRACTED = "extracted"
    MANUAL_REVIEW = "manual_review"
    UNSUPPORTED = "unsupported"


@dataclass
class ProcessingReport:
    """What one run of the pipeline produced for one document."""

    outcome: ProcessingOutcome
    kind: str
    kind_model_confidence: float
    page_count: int
    provider: str
    fields: list[CandidateField] = field(default_factory=list)
    transcripts: dict[int, str] = field(default_factory=dict)  # page_no → text
    #: Machine-readable reasons for a manual_review/unsupported outcome.
    reasons: list[str] = field(default_factory=list)
    #: Logged meters (v1 interim for §10A until billing exists).
    ai_extraction_calls: int = 0
    pages_processed: int = 0
