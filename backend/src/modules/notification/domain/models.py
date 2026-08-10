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
    obligation_id: str
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
    version: int = 1
    next_attempt_at: datetime | None = None
    attempted_at: datetime | None = None
    delivered_at: datetime | None = None
    provider_message_id: str | None = None
    failure_code: str | None = None
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


# Placeholder synthetic template catalogue (not legal copy).
SYNTHETIC_TEMPLATE_PREVIEW: dict[str, tuple[str, str]] = {
    "obligation.reminder.due_in_24_hours": (
        "Draftly deadline reminder (synthetic)",
        "A synthetic obligation is due soon. Log in to Draftly to review it.",
    ),
    "restricted.action_required": (
        "Draftly action required (synthetic)",
        "A restricted workflow needs your attention in Draftly.",
    ),
}

DEFAULT_PREVIEW = (
    "Draftly notification (synthetic)",
    "You have a synthetic notification in Draftly.",
)


def preview_for_template(template_key: str) -> tuple[str, str]:
    return SYNTHETIC_TEMPLATE_PREVIEW.get(template_key, DEFAULT_PREVIEW)
