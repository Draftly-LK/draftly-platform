"""SQLAlchemy ORM models for the matter module.

Enum-valued columns are stored as their string ``value`` rather than a
PostgreSQL enum type: the RTA vocabularies are governed content that gains
members between releases, and a migration per added member would make a rule
change a schema change.

Every row carries ``user_id``. It is the first predicate of every query, before
membership or ownership (plan §5.3 invariant 10).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
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


class MatterRow(Base):
    """The RTA matter root. ``version`` drives ``If-Match`` concurrency."""

    __tablename__ = "matters"
    __table_args__ = (
        UniqueConstraint("user_id", "reference", name="uq_matters_user_reference"),
        Index("ix_matters_user_state", "user_id", "rta_state"),
        Index("ix_matters_user_lifecycle", "user_id", "lifecycle_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str] = mapped_column(String(128), nullable=False)
    client_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    responsible_lawyer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    regime_id: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtype_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subtype_decision_status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Kept verbatim so a migrated M2 record stays readable and auditable.
    legacy_matter_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    rta_state: Mapped[str] = mapped_column(String(32), nullable=False)
    automation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    title_status: Mapped[str] = mapped_column(String(32), nullable=False)
    parcel_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    disposition_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    dispute_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    instrument_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    declared_legal_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_authority_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_checklist_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    party_contexts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    activated_conditional_module_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suppressed_conditional_module_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    automation_exclusion_reason_keys: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MatterClassificationRow(Base):
    """Append-only classification history.

    Reclassification writes version N+1; version N is never updated, because
    the checklist snapshot, checks, and templates a matter was worked under
    have to stay reconstructible (matter-service.md §10).
    """

    __tablename__ = "matter_classifications"
    __table_args__ = (
        UniqueConstraint("matter_id", "version", name="uq_matter_classification_version"),
        Index("ix_matter_classifications_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("matters.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    regime_id: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subtype_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subtype_decision_status: Mapped[str] = mapped_column(String(32), nullable=False)
    title_status: Mapped[str] = mapped_column(String(32), nullable=False)
    parcel_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    disposition_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    property_characteristics: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    execution_circumstances: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    rule_pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntakeAnswerRow(Base):
    """One answer version. Superseding writes a new row and marks the old one.

    There is no UPDATE path for ``value``: a later conflicting extraction
    creates a review task rather than replacing a lawyer's answer (§4.4).
    """

    __tablename__ = "matter_intake_answers"
    __table_args__ = (
        Index("ix_intake_answers_user_matter", "user_id", "matter_id"),
        Index("ix_intake_answers_matter_question", "matter_id", "question_definition_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("matters.id", ondelete="CASCADE"), nullable=False
    )
    question_definition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    inferred_from_fact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lawyer_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
