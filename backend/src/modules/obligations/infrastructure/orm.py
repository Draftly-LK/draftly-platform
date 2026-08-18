"""SQLAlchemy ORM for obligations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class ObligationRow(Base):
    __tablename__ = "obligations"
    __table_args__ = (
        Index("ix_obligations_org_assignee", "organisation_id", "assignee_user_id"),
        Index("ix_obligations_org_matter", "organisation_id", "matter_id"),
        Index("ix_obligations_org_due", "organisation_id", "due_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    obligation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    obligation_class: Mapped[str] = mapped_column(String(64), nullable=False)
    label_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    legal_authority_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calculation_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    calculation_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    hardness: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assignee_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_assignee_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reminder_policy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    escalation_policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidentiality_level: Mapped[str] = mapped_column(String(32), nullable=False)
    completion_evidence_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LawyerConfirmationRow(Base):
    __tablename__ = "lawyer_confirmations"

    obligation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReminderOccurrenceRow(Base):
    __tablename__ = "reminder_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "obligation_id",
            "recipient_user_id",
            "reminder_type",
            name="uq_reminder_occurrence",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    obligation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("obligations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    emitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutboxEventRow(Base):
    """Transactional outbox stub for obligation domain events."""

    __tablename__ = "obligation_outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
