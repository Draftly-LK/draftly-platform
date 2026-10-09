"""Ingestion entities — the immutable source and what was detected inside it.

Separate from ``domain/models.py`` on purpose: that module describes one run of
the extraction pipeline over bytes held in memory, while these entities are the
persisted record of what was uploaded, where it is stored, and which documents
a run proposed. The two meet only in `application/processing_job.py`.

Three invariants shape these shapes (§6.2, §10.2, §12.2):

- The source is immutable. There is no "edited" state and no field a correction
  writes to; a cleaned file is a new `SourceFile` carrying
  ``derived_from_source_file_id``.
- A document is a set of fragments, not a file. That is what lets one PDF hold
  several documents and one document span two files (§6.3).
- Nothing here is verified. A `DocumentCandidate` is what a provider proposed;
  the class status and boundary status record how far that proposal may travel
  without a lawyer (§6.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.content_governance.contracts import (
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
)

if TYPE_CHECKING:
    from src.modules.document.domain.v1 import V1PipelineReport

#: Retention class recorded on every uploaded source until a retention policy
#: module exists to assign a narrower one. Stored rather than assumed so the
#: retention decision is visible on the row (§12.2).
DEFAULT_RETENTION_CLASS = "rta.client-evidence"


@dataclass(frozen=True)
class ProcessingPageOutcome:
    """Retained page diagnostics; excludes OCR text and storage references."""

    page_no: int
    quality_status: str
    rotation_status: str


@dataclass
class SourceFile:
    """Uploaded bytes plus the metadata that makes them attributable.

    ``storage_object_key`` is empty exactly when the file was rejected during
    quarantine: bytes that failed the type, size, or password checks are never
    written to storage, but the rejection itself is a record the lawyer needs to
    see with a reason they can act on (§6.2 stage 1, §10.2).
    """

    id: str
    user_id: str
    matter_id: str
    original_filename: str
    media_type: str
    byte_length: int
    sha256: str
    storage_object_key: str
    storage_object_version: str
    upload_actor_id: str
    state: SourceFileState
    retention_class: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    page_count: int | None = None
    detected_languages: tuple[str, ...] = ()
    failure_reason: ProcessingFailureReason | None = None
    #: Translation key telling the lawyer what to do next. A failure without one
    #: is a dead end, which §6.2 forbids ("recoverable reason").
    failure_explanation_key: str | None = None
    superseded_by_source_file_id: str | None = None
    derived_from_source_file_id: str | None = None

    @property
    def has_stored_bytes(self) -> bool:
        return bool(self.storage_object_key)


@dataclass
class DetectedDocument:
    """One logical document proposed inside or across source files."""

    id: str
    user_id: str
    matter_id: str
    class_status: DocumentClassStatus
    boundary_status: BoundaryStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1
    class_id: str | None = None
    class_confidence: float | None = None
    language_codes: tuple[str, ...] = ()
    issuer: str | None = None
    #: Points at the confirmed fact rather than storing a date, so the document's
    #: issue date is verified once and read everywhere (§12.2).
    issue_or_execution_date_fact_id: str | None = None
    version_relationship: DocumentVersionRelationship | None = None
    duplicate_of_detected_document_id: str | None = None
    interpretation_generation: int = 1
    extraction_state: str = "current"
    latest_refresh_run_id: str | None = None
    refresh_failure_reason: str | None = None


@dataclass(frozen=True)
class FragmentRange:
    """A page range a lawyer asks for, before anything is written.

    Separate from `DocumentFragment` because a requested range has no id, no
    confidence, and no status yet — it is an instruction, and validating it
    against the source's real page count happens before it becomes a fragment.
    """

    source_file_id: str
    page_start: int
    page_end: int
    order_in_document: int


@dataclass(frozen=True)
class DocumentFragment:
    """A page range of one source file, in its position within a document.

    Frozen because a fragment is never edited: a boundary decision replaces the
    document's fragment set so the old ranges stay reconstructible from the
    audit trail rather than being mutated in place (§6.5).

    ``boundary_confidence`` is ``None`` for a range a human drew. A lawyer's
    decision is not a model score of 1.0, and writing one would let a later
    calibration read a human act as an unusually confident machine (§6.4).
    """

    id: str
    user_id: str
    matter_id: str
    detected_document_id: str
    source_file_id: str
    page_start: int
    page_end: int
    order_in_document: int
    boundary_confidence: float | None
    boundary_status: BoundaryStatus
    created_at: datetime

    @property
    def page_count(self) -> int:
        return self.page_end - self.page_start + 1


@dataclass(frozen=True)
class CandidateFieldRef:
    """One extracted particular with the page it was read from.

    Deliberately not persisted by this module: an evidence-linked candidate fact
    belongs to verification, which owns the evidence table (§6.2 stage 8). These
    travel out through the processing response so verification can create the
    `EvidenceReference` and `ExtractedFact` rows itself.
    """

    key: str
    value: str | None
    page_no: int
    source_file_id: str
    model_reported_confidence: float
    provider: str
    format_valid: bool | None = None


@dataclass(frozen=True)
class DocumentCandidate:
    """A document a run proposes, before anything is written.

    ``class_top_two_margin`` is carried even when a provider cannot report it:
    §6.4 makes the margin half of the auto-organize decision, so a provider that
    cannot supply one scores 0.0 and the class goes to review rather than being
    filed on the strength of the top score alone.
    """

    page_start: int
    page_end: int
    source_file_id: str
    #: ``None`` when no boundary detector ran at all — which is the current
    #: pipeline, where the proposed range is simply the whole file. A whole-file
    #: range is not a confident split, and scoring it as one would put an
    #: undetected boundary into the auto-organize band.
    boundary_confidence: float | None
    continuity_anomaly: bool
    class_id: str | None = None
    class_confidence: float = 0.0
    class_top_two_margin: float = 0.0
    language_codes: tuple[str, ...] = ()
    issuer: str | None = None
    candidate_fields: tuple[CandidateFieldRef, ...] = ()


@dataclass
class ProcessingRun:
    """One attempt to process one source file.

    A run always terminates in a real outcome. There is no "in progress" that
    quietly never finishes and no fabricated progress: if nothing processed the
    file, the run says ``PROCESSING_FAILED`` with the reason why.
    """

    id: str
    user_id: str
    matter_id: str
    source_file_id: str
    provider: str
    outcome: SourceFileState
    started_at: datetime
    correlation_id: str
    reasons: tuple[str, ...] = ()
    pages_processed: int = 0
    ai_extraction_calls: int = 0
    finished_at: datetime | None = None
    failure_reason: ProcessingFailureReason | None = None
    failure_explanation_key: str | None = None
    #: Not persisted with the run — materialised into detected documents and
    #: fragments by the ingestion service, and returned to the caller so
    #: verification can consume the page-level candidates.
    candidates: tuple[DocumentCandidate, ...] = field(default_factory=tuple)
    #: Full V1 page/group result. Repository adapters persist it into owned
    #: child tables; it is not placed in logs or event payloads.
    v1_report: V1PipelineReport | None = None
    kind: str = "source"

    @property
    def succeeded(self) -> bool:
        return self.outcome is SourceFileState.PROCESSED
