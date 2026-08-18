"""API schemas for notification preferences and in-app notifications."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.modules.notification.domain.models import (
    NotificationDelivery,
    NotificationPreference,
    PaginatedDeliveries,
)


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    channel: str
    enabled: bool
    locale: str
    timezone: str
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    version: int


class NotificationPreferenceListRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[NotificationPreferenceRead]


class NotificationPreferencePatch(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    channel: str
    enabled: bool | None = None
    locale: str | None = None
    timezone: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    clear_quiet_hours: bool = False


class NotificationRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    status: str
    template_key: str
    preview_title: str
    preview_body: str
    created_at: str
    read_at: str | None = None
    matter_id: str | None = None
    version: int


class PageRead(BaseModel):
    """Pagination envelope shared by every list route (api-conventions.md §2)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class NotificationListRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[NotificationRead]
    page: PageRead


def preference_to_read(pref: NotificationPreference) -> NotificationPreferenceRead:
    return NotificationPreferenceRead(
        channel=pref.channel.value,
        enabled=pref.enabled,
        locale=pref.locale.value,
        timezone=pref.timezone,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        version=pref.version,
    )


def delivery_to_read(delivery: NotificationDelivery) -> NotificationRead:
    return NotificationRead(
        id=delivery.id,
        status=delivery.status.value,
        template_key=delivery.template_key,
        preview_title=delivery.preview_title,
        preview_body=delivery.preview_body,
        created_at=delivery.created_at.isoformat(),
        read_at=delivery.read_at.isoformat() if delivery.read_at else None,
        matter_id=delivery.matter_id,
        version=delivery.version,
    )


def page_to_read(page: PaginatedDeliveries) -> NotificationListRead:
    return NotificationListRead(
        items=[delivery_to_read(item) for item in page.items],
        page=PageRead(next_cursor=page.next_cursor, has_more=page.has_more, limit=page.limit),
    )


class ObligationReminderDueData(BaseModel):
    """`data` fields registered for obligation.reminder-due (events.md §5.9)."""

    model_config = ConfigDict(populate_by_name=True)

    obligation_id: str = Field(alias="obligationId")
    recipient_user_id: str = Field(alias="recipientUserId")
    due_at: str = Field(alias="dueAt")
    reminder_type: str = Field(alias="reminderType")
    obligation_class: str = Field(alias="class")
    urgency: str
    confidentiality_level: str = Field(alias="confidentialityLevel")
    template_key: str = Field(alias="templateKey")
    delivery_policy_key: str = Field(alias="deliveryPolicyKey")


class ObligationReminderDueEventFixture(BaseModel):
    """Contract fixture for obligation.reminder-due (identifier-only, events.md §2)."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_name: str = Field(default="obligation.reminder-due", alias="eventName")
    event_version: int = Field(default=1, alias="eventVersion")
    occurred_at: str = Field(alias="occurredAt")
    organisation_id: str = Field(alias="organisationId")
    matter_id: str | None = Field(default=None, alias="matterId")
    actor_id: str | None = Field(default=None, alias="actorId")
    correlation_id: str = Field(alias="correlationId")
    causation_id: str | None = Field(default=None, alias="causationId")
    idempotency_key: str = Field(alias="idempotencyKey")
    data: ObligationReminderDueData


ObligationReminderDueEventFixture.model_rebuild()
