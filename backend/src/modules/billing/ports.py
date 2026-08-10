"""Billing module port definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.billing.domain.models import (
    BillingWebhookEvent,
    PlanEntitlement,
    PlanVersion,
    Reservation,
    Subscription,
    UsageAggregate,
    UsageLedgerEntry,
    WebhookProcessingState,
)


@dataclass(frozen=True)
class CheckoutCommand:
    user_id: str
    plan_version_id: str
    return_path: str
    customer_email: str | None = None


@dataclass(frozen=True)
class Checkout:
    checkout_url: str
    provider_session_id: str


@dataclass(frozen=True)
class Portal:
    portal_url: str


@dataclass(frozen=True)
class RawWebhook:
    headers: dict[str, str]
    body: bytes
    provider: str


@dataclass(frozen=True)
class ProviderEvent:
    provider_event_id: str
    event_type: str
    provider_subscription_id: str | None
    provider_customer_id: str | None
    occurred_at: datetime | None
    normalized_status: str | None
    payload_hash: str


@dataclass(frozen=True)
class ProviderSubscription:
    provider_subscription_id: str
    provider_customer_id: str
    status: str


@dataclass(frozen=True)
class WebhookReceipt:
    provider_event_id: str
    processing_state: WebhookProcessingState
    duplicate: bool = False


class BillingProviderPort(Protocol):
    async def create_checkout(self, command: CheckoutCommand) -> Checkout: ...

    async def create_customer_portal(self, customer_id: str) -> Portal: ...

    async def cancel_subscription(self, subscription_id: str) -> None: ...

    async def reactivate_subscription(self, subscription_id: str) -> None: ...

    async def verify_webhook(self, request: RawWebhook) -> ProviderEvent: ...

    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription: ...


class PlanRepository(Protocol):
    async def list_active(self) -> list[PlanVersion]: ...

    async def get(self, plan_version_id: str) -> PlanVersion | None: ...

    async def get_entitlements(self, plan_version_id: str) -> list[PlanEntitlement]: ...


class SubscriptionRepository(Protocol):
    async def get_by_user_id(self, user_id: str) -> Subscription | None: ...

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None: ...

    async def create(self, subscription: Subscription) -> Subscription: ...

    async def update(self, subscription: Subscription, expected_version: int) -> Subscription: ...


class UsageRepository(Protocol):
    async def get_aggregates_for_user(self, user_id: str) -> list[UsageAggregate]: ...

    async def get_aggregate(
        self, user_id: str, metric: str, period_start: datetime, period_end: datetime
    ) -> UsageAggregate | None: ...

    async def find_ledger_by_operation(
        self, user_id: str, metric: str, operation_id: str
    ) -> UsageLedgerEntry | None: ...

    async def get_ledger_entry(self, entry_id: str) -> UsageLedgerEntry | None: ...

    async def reserve(
        self,
        *,
        user_id: str,
        metric: str,
        quantity: int,
        operation_id: str,
        period_start: datetime,
        period_end: datetime,
        entry_id: str,
    ) -> Reservation: ...

    async def consume(
        self, entry_id: str, actual_quantity: int
    ) -> UsageLedgerEntry: ...

    async def release(self, entry_id: str) -> UsageLedgerEntry: ...


class BillingWebhookEventRepository(Protocol):
    async def get_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> BillingWebhookEvent | None: ...

    async def claim(
        self,
        *,
        event_id: str,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload_hash: str,
        provider_occurred_at: datetime | None,
    ) -> BillingWebhookEvent: ...

    async def mark_processed(self, event_id: str) -> BillingWebhookEvent: ...

    async def mark_ignored(self, event_id: str, failure_code: str | None = None) -> BillingWebhookEvent: ...

    async def mark_failed(self, event_id: str, failure_code: str) -> BillingWebhookEvent: ...


class EventPort(Protocol):
    async def emit(self, event_name: str, payload: dict[str, Any]) -> None: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


# Re-export audit types for application wiring convenience.
__all__ = [
    "AuditPort",
    "AuditEventInput",
    "BillingProviderPort",
    "PlanRepository",
    "SubscriptionRepository",
    "UsageRepository",
    "BillingWebhookEventRepository",
    "EventPort",
    "ClockPort",
    "CheckoutCommand",
    "Checkout",
    "Portal",
    "RawWebhook",
    "ProviderEvent",
    "ProviderSubscription",
    "WebhookReceipt",
]
