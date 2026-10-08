"""ORM models for evidence references, facts, and review decisions.

None of these tables has a destructive update path. A fact row's ``value`` is
written once; correcting it inserts a new row and sets the old row's
``superseded_by_fact_id``. That is what keeps the original extraction result
recoverable after an approval (§6.5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class EvidenceReferenceRow(Base):
    __tablename__ = "evidence_references"
    __table_args__ = (
        Index("ix_evidence_references_user_matter", "user_id", "matter_id"),
        Index("ix_evidence_references_source", "source_file_id", "page_number"),
        # Page numbers are 1-based throughout the pipeline; a 0 would silently
        # point one page off in the viewer.
        CheckConstraint("page_number >= 1", name="ck_evidence_page_number_one_based"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Pinning the hash on the reference is what proves the evidence still points
    # at the bytes that were reviewed.
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    text_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    region_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extraction_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExtractedFactRow(Base):
    """One immutable fact version."""

    __tablename__ = "extracted_facts"
    __table_args__ = (
        Index("ix_extracted_facts_user_matter", "user_id", "matter_id"),
        Index("ix_extracted_facts_matter_type", "matter_id", "fact_type_id"),
        Index("ix_extracted_facts_live", "matter_id", "fact_type_id", "superseded_by_fact_id"),
        # A confirmed fact names its reviewer and the time. Nothing reaches that
        # status anonymously, including a direct SQL write (§6.4).
        CheckConstraint(
            "status NOT IN ('LAWYER_CONFIRMED', 'LOCKED_FOR_FORM') OR "
            "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_extracted_fact_confirmation_requires_reviewer",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fact_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="legacy-unassigned", server_default="legacy-unassigned"
    )
    evidence_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    normalized_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    model_reported_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    derivation_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    derivation_input_fact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    derivation_formula_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_fact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    superseded_by_fact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_by_form_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReviewDecisionRow(Base):
    """Append-only human decisions across every reviewable target type."""

    __tablename__ = "review_decisions"
    __table_args__ = (
        Index("ix_review_decisions_user_matter", "user_id", "matter_id"),
        Index("ix_review_decisions_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(40), nullable=False)
    # True when the decision was made by a human. There is no code path that
    # sets this false and also confirms a critical fact.
    human_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
