"""Billing domain models — plans, subscriptions, usage, webhook events."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class PlanState(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class BillingInterval(str, enum.Enum):
    TRIAL = "trial"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
    RESTRICTED = "restricted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class UsageLedgerState(str, enum.Enum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


class WebhookProcessingState(str, enum.Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


@dataclass
class PlanVersion:
    id: str
    code: str
    family: str
    name: str
    version: int
    billing_interval: BillingInterval
    currency: str
    price_minor_units: int
    state: PlanState
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class PlanEntitlement:
    plan_version_id: str
    feature_key: str
    limit_value: int | None
    enabled: bool


@dataclass
class Subscription:
    id: str
    user_id: str
    plan_version_id: str
    provider: str
    provider_customer_id: str | None
    provider_subscription_id: str | None
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: datetime | None
    cancel_at_period_end: bool
    grace_period_ends_at: datetime | None
    provider_state_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass
class UsageLedgerEntry:
    id: str
    user_id: str
    metric: str
    quantity: int
    period_start: datetime
    period_end: datetime
    operation_id: str
    state: UsageLedgerState
    created_at: datetime


@dataclass
class UsageAggregate:
    user_id: str
    metric: str
    quantity: int
    period_start: datetime
    period_end: datetime
    updated_at: datetime
    version: int


@dataclass
class BillingWebhookEvent:
    id: str
    provider: str
    provider_event_id: str
    event_type: str
    received_at: datetime
    provider_occurred_at: datetime | None
    processed_at: datetime | None
    processing_state: WebhookProcessingState
    payload_hash: str
    failure_code: str | None


@dataclass(frozen=True)
class EntitlementRequest:
    """One entitlement line supplied when an operator drafts a plan version."""

    feature_key: str
    limit_value: int | None
    enabled: bool


@dataclass(frozen=True)
class PlanVersionDraft:
    """Operator input for a new plan version.

    Prices, allowances, and intervals are product data carried here, never
    hardcoded in an application service (billing-service.md §8).
    """

    code: str
    family: str
    name: str
    billing_interval: BillingInterval
    currency: str
    price_minor_units: int
    entitlements: list[EntitlementRequest]


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    feature_key: str
    limit_value: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Reservation:
    id: str
    user_id: str
    metric: str
    quantity: int
    operation_id: str


@dataclass(frozen=True)
class UsageRead:
    metric: str
    quantity: int
    period_start: datetime
    period_end: datetime
    limit_value: int | None = None
