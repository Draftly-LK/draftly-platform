"""SQLAlchemy ORM model for audit events — insert-only, append-only."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Separate declarative base for the audit module."""


class AuditEventRow(Base):
    """Append-only audit event.

    id, timestamp, and hash are server-assigned on record().
    actor comes from RequestContext, never from the request body.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_timestamp", "organisation_id", "timestamp"),
        Index("ix_audit_events_org_matter", "organisation_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # null for scheduler-originated events
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    causation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
