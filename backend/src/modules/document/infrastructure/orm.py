"""ORM models for immutable source files and what was detected inside them.

``source_files`` has no unique constraint on the hash. A second upload of the
same bytes is a *detectable* event, not a rejected one (§6.3): the lawyer is
shown the pair and decides. The composite index is what makes that detection a
lookup instead of a scan.

The check constraints mirror `domain/ingestion_policies` so the two cannot
drift: a rejected source always says why, a file that never reached storage can
never be marked processed, and a fragment can never claim page 0.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base

#: States that can only be reached after bytes were written to object storage.
#: Kept as a SQL literal list so the constraint text is identical in the ORM and
#: in the migration.
_STORED_STATES = "'STORED', 'PROCESSING', 'PROCESSED', 'PROCESSING_FAILED', 'SUPERSEDED'"


class SourceFileRow(Base):
    __tablename__ = "source_files"
    __table_args__ = (
        Index("ix_source_files_user_matter", "user_id", "matter_id"),
        # Duplicate detection (§6.3), deliberately NOT unique.
        Index("ix_source_files_user_matter_sha256", "user_id", "matter_id", "sha256"),
        CheckConstraint("byte_length >= 0", name="ck_source_file_byte_length_nonnegative"),
        CheckConstraint(
            "page_count IS NULL OR page_count >= 1", name="ck_source_file_page_count_positive"
        ),
        # §6.2 stage 1: a rejection the lawyer cannot act on is a dead end.
        CheckConstraint(
            "(state <> 'REJECTED') OR "
            "(failure_reason IS NOT NULL AND failure_explanation_key IS NOT NULL)",
            name="ck_source_file_rejection_states_reason",
        ),
        # §10.2: PROCESSED is reachable only through storage. Without this a
        # direct SQL write could claim a processed file that holds no bytes.
        CheckConstraint(
            f"(state NOT IN ({_STORED_STATES})) OR storage_object_key <> ''",
            name="ck_source_file_stored_states_have_object",
        ),
        CheckConstraint(
            "(state <> 'SUPERSEDED') OR superseded_by_source_file_id IS NOT NULL",
            name="ck_source_file_superseded_names_successor",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Empty exactly when the bytes were refused in quarantine and never stored.
    storage_object_key: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    storage_object_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    upload_actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    retention_class: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_explanation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    superseded_by_source_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: A cleaned or rotated copy is a new row pointing back here; the source
    #: bytes themselves are never rewritten (§10.2).
    derived_from_source_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DetectedDocumentRow(Base):
    """One logical document. Its pages live in ``document_fragments``.

    There is no ``source_file_id`` here on purpose: a document is a set of
    fragments, which is what lets one document span two files (§6.3).
    """

    __tablename__ = "detected_documents"
    __table_args__ = (
        Index("ix_detected_documents_user_matter", "user_id", "matter_id"),
        Index("ix_detected_documents_class", "user_id", "matter_id", "class_status"),
        CheckConstraint(
            "class_confidence IS NULL OR (class_confidence >= 0 AND class_confidence <= 1)",
            name="ck_detected_document_class_confidence_range",
        ),
        # §6.3: UNIDENTIFIED and REJECTED are the only classless states. A filed
        # document always names the controlled class it was filed under.
        CheckConstraint(
            "(class_status NOT IN ('AI_ORGANIZED', 'REVIEW_REQUIRED', 'LAWYER_CONFIRMED')) OR "
            "class_id IS NOT NULL",
            name="ck_detected_document_filed_has_class",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    class_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_status: Mapped[str] = mapped_column(String(32), nullable=False)
    language_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Points at the confirmed fact rather than storing a date: the issue date
    #: is verified once, in verification, and read from there (§12.2).
    issue_or_execution_date_fact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version_relationship: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_of_detected_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    boundary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interpretation_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    extraction_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="current", server_default="current"
    )
    latest_refresh_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refresh_failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DocumentInterpretationRow(Base):
    """Append-only class and ordered source ranges for one interpretation."""

    __tablename__ = "document_interpretations"
    __table_args__ = (
        UniqueConstraint(
            "detected_document_id", "generation", name="uq_document_interpretation_generation"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("detected_documents.id"), nullable=False
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    class_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fragments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PageDispositionRow(Base):
    __tablename__ = "document_page_dispositions"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id",
            "page_number",
            "source_version",
            name="uq_document_page_disposition_version",
        ),
        CheckConstraint("page_number >= 1", name="ck_page_disposition_page"),
        CheckConstraint(
            "disposition IN ('blank', 'unsupported', 'review_required')",
            name="ck_page_disposition_status",
        ),
        Index("ix_document_page_dispositions_scope", "user_id", "matter_id", "source_file_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_files.id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentFragmentRow(Base):
    """One page range of one source file in its position within a document."""

    __tablename__ = "document_fragments"
    __table_args__ = (
        Index("ix_document_fragments_user_matter", "user_id", "matter_id"),
        Index("ix_document_fragments_document", "detected_document_id"),
        Index("ix_document_fragments_source", "source_file_id"),
        # Pages are 1-based throughout the pipeline and a range never runs
        # backwards; either would point the page viewer at nothing.
        CheckConstraint(
            "page_start >= 1 AND page_end >= page_start", name="ck_document_fragment_page_range"
        ),
        CheckConstraint(
            "boundary_confidence IS NULL OR "
            "(boundary_confidence >= 0 AND boundary_confidence <= 1)",
            name="ck_document_fragment_confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("detected_documents.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_files.id"), nullable=False
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    order_in_document: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: NULL for a range a human drew — a lawyer's decision is not a model score.
    boundary_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    boundary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceFileProcessingRunRow(Base):
    detected_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interpretation_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """One attempt to process one source file — including the ones that did nothing.

    A run that failed because no provider is configured is recorded exactly like
    one that succeeded. That row is the evidence that the document is genuinely
    unprocessed rather than quietly forgotten (§6.2 stage 10).
    """

    __tablename__ = "source_file_processing_runs"
    __table_args__ = (
        Index("ix_processing_runs_user_matter", "user_id", "matter_id"),
        Index("ix_processing_runs_source", "source_file_id"),
        CheckConstraint(
            "pages_processed >= 0 AND ai_extraction_calls >= 0",
            name="ck_processing_run_meters_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_files.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pages_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_extraction_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="source", server_default="source"
    )


class DocumentProcessingPageRow(Base):
    """Review metadata and immutable GCS references for one retained page."""

    __tablename__ = "document_processing_pages"
    __table_args__ = (
        Index("ix_processing_pages_user_run", "user_id", "processing_run_id"),
        Index("ix_processing_pages_source", "user_id", "source_file_id", "page_no"),
        CheckConstraint("page_no >= 1", name="ck_processing_page_number_positive"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_file_processing_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_files.id"))
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    original_width: Mapped[int] = mapped_column(Integer, nullable=False)
    original_height: Mapped[int] = mapped_column(Integer, nullable=False)
    corrected_width: Mapped[int] = mapped_column(Integer, nullable=False)
    corrected_height: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_orientation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correction_degrees: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    rotation_vote_share: Mapped[float] = mapped_column(Float, nullable=False)
    usable_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_languages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    classification_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    suggested_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_new_document: Mapped[bool] = mapped_column(nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    corrected_webp_key: Mapped[str] = mapped_column(String(768), nullable=False)
    corrected_webp_version: Mapped[str] = mapped_column(String(128), nullable=False)
    corrected_ocr_key: Mapped[str] = mapped_column(String(768), nullable=False)
    corrected_ocr_version: Mapped[str] = mapped_column(String(128), nullable=False)
    plain_text_key: Mapped[str] = mapped_column(String(768), nullable=False)
    plain_text_version: Mapped[str] = mapped_column(String(128), nullable=False)


class ProcessingLogicalDocumentRow(Base):
    __tablename__ = "processing_logical_documents"
    __table_args__ = (Index("ix_logical_documents_user_run", "user_id", "processing_run_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_file_processing_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_files.id"))
    detected_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    suggested_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_numbers: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    interpretation_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    page_sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)


class ProcessingCandidateFieldRow(Base):
    """AI output stays unverified until the explicit approve transition."""

    __tablename__ = "processing_candidate_fields"
    __table_args__ = (
        Index("ix_candidate_fields_user_document", "user_id", "logical_document_id"),
        CheckConstraint(
            "(review_state = 'unverified' AND approved_by IS NULL AND approved_at IS NULL "
            "AND approved_fact_id IS NULL) OR (review_state = 'approved' "
            "AND approved_by IS NOT NULL AND approved_at IS NOT NULL "
            "AND approved_fact_id IS NOT NULL)",
            name="ck_candidate_review_state_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("processing_logical_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_value: Mapped[str] = mapped_column(Text, nullable=False)
    edited_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    model_reported_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_fact_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("extracted_facts.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
