"""Notification domain models — no FastAPI or SQLAlchemy imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NotificationChannel(str, Enum):
    EMAIL = "email"
    IN_APP = "in-app"


class NotificationLocale(str, Enum):
    EN = "en"
    SI = "si"


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class ProviderDeliveryState(str, Enum):
    """Provider-reported states from Resend webhooks (notification-service.md §9.1)."""

    SENT = "sent"
    DELIVERED = "delivered"
    DELAYED = "delivery_delayed"
    FAILED = "failed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    SUPPRESSED = "suppressed"


PROVIDER_EVENT_STATES: dict[str, ProviderDeliveryState] = {
    "email.sent": ProviderDeliveryState.SENT,
    "email.delivered": ProviderDeliveryState.DELIVERED,
    "email.delivery_delayed": ProviderDeliveryState.DELAYED,
    "email.failed": ProviderDeliveryState.FAILED,
    "email.bounced": ProviderDeliveryState.BOUNCED,
    "email.complained": ProviderDeliveryState.COMPLAINED,
    "email.suppressed": ProviderDeliveryState.SUPPRESSED,
}


@dataclass
class NotificationPreference:
    """Per-user channel preferences (notification-service.md §5.2)."""

    id: str
    organisation_id: str
    user_id: str
    channel: NotificationChannel
    enabled: bool
    locale: NotificationLocale
    timezone: str
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    version: int = 1


@dataclass
class NotificationDelivery:
    """Channel delivery attempt — independent of obligation state (§5.3)."""

    id: str
    organisation_id: str
    source_event_id: str
    subject_ref: str
    matter_id: str | None
    recipient_user_id: str
    channel: NotificationChannel
    reminder_type: str
    obligation_class: str
    urgency: str
    confidentiality_level: str
    template_key: str
    delivery_policy_key: str
    locale: NotificationLocale
    status: DeliveryStatus
    attempt_count: int
    created_at: datetime
    obligation_id: str | None = None
    correlation_id: str = ""
    version: int = 1
    next_attempt_at: datetime | None = None
    attempted_at: datetime | None = None
    delivered_at: datetime | None = None
    provider_message_id: str | None = None
    failure_code: str | None = None
    failure_class: str | None = None
    provider_state: str | None = None
    read_at: datetime | None = None
    preview_title: str = ""
    preview_body: str = ""


@dataclass(frozen=True)
class DeliveryResult:
    provider_message_id: str


@dataclass(frozen=True)
class PaginatedDeliveries:
    items: list[NotificationDelivery]
    next_cursor: str | None = None
    has_more: bool = False
    limit: int = 50


@dataclass(frozen=True)
class TemplateDeployment:
    """A published template version for one environment (§3.2)."""

    id: str
    environment: str
    template_key: str
    locale: NotificationLocale
    source_version: str
    provider_template_id: str
    published_by: str
    published_at: datetime


@dataclass(frozen=True)
class ProviderEvent:
    """One verified provider webhook event, stored idempotently (§9.1)."""

    id: str
    provider: str
    provider_event_id: str
    event_type: str
    provider_message_id: str | None
    delivery_id: str | None
    received_at: datetime


__all__ = [
    "PROVIDER_EVENT_STATES",
    "DeliveryResult",
    "DeliveryStatus",
    "NotificationChannel",
    "NotificationDelivery",
    "NotificationLocale",
    "NotificationPreference",
    "PaginatedDeliveries",
    "ProviderDeliveryState",
    "ProviderEvent",
    "TemplateDeployment",
]
