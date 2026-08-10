"""SQLAlchemy ORM models for billing."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class PlanVersionRow(Base):
    __tablename__ = "plan_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    price_minor_units: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlanEntitlementRow(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_version_id", "feature_key", name="uq_plan_entitlement_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String(128), nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_subscription_user"),
        Index("ix_subscriptions_provider_sub", "provider_subscription_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("plan_versions.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_state_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class UsageLedgerEntryRow(Base):
    __tablename__ = "usage_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "metric", "operation_id", name="uq_usage_ledger_operation"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UsageAggregateRow(Base):
    __tablename__ = "usage_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "metric", "period_start", "period_end", name="uq_usage_aggregate_period"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BillingWebhookEventRow(Base):
    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_billing_webhook_provider_event"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_state: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
