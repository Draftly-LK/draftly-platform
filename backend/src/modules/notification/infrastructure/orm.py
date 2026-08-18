"""SQLAlchemy ORM models owned by notification_service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class NotificationPreferenceRow(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "user_id", "channel", name="uq_notif_pref_user_channel"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NotificationDeliveryRow(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        # The permanent duplicate-send guard: at most one delivery per subject,
        # recipient, reminder type, and channel (notification-service.md §5.3).
        UniqueConstraint(
            "organisation_id",
            "subject_ref",
            "recipient_user_id",
            "reminder_type",
            "channel",
            name="uq_notif_delivery_idempotent",
        ),
        UniqueConstraint("source_event_id", "channel", name="uq_notif_delivery_source_channel"),
        Index(
            "ix_notif_delivery_recipient_created",
            "organisation_id",
            "recipient_user_id",
            "created_at",
        ),
        Index("ix_notif_delivery_provider_message", "provider_message_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    obligation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matter_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recipient_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(128), nullable=False)
    obligation_class: Mapped[str] = mapped_column(String(64), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(String(64), nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    delivery_policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    preview_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    preview_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationConsumedEventRow(Base):
    """Inbox record: one row per consumed event id, written with the effect."""

    __tablename__ = "notification_consumed_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_notif_consumed_event_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    organisation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationProviderEventRow(Base):
    """Verified provider webhook events, stored idempotently (§9.1).

    `organisation_id` is null until the provider message id is matched to a
    delivery; a provider event can arrive for a message this instance never sent.
    """

    __tablename__ = "notification_provider_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_notif_provider_event"),
        Index("ix_notif_provider_event_message", "provider_message_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivery_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organisation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationTemplateDeploymentRow(Base):
    """Which reviewed template version is published to the provider (§3.2)."""

    __tablename__ = "notification_template_deployments"
    __table_args__ = (
        UniqueConstraint(
            "environment", "template_key", "locale", name="uq_notif_template_deployment"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    source_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    published_by: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
