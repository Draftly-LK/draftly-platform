"""API schemas for notification preferences and in-app notifications."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.modules.notification.domain.models import NotificationDelivery, NotificationPreference


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


class NotificationListRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[NotificationRead]
    next_cursor: str | None = None


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
    )


class ObligationReminderDueEventFixture(BaseModel):
    """Contract fixture for obligation.reminder-due (identifier-only)."""

    event: str = "obligation.reminder-due"
    event_id: str = Field(alias="eventId")
    occurred_at: str = Field(alias="occurredAt")
    obligation_id: str = Field(alias="obligationId")
    matter_id: str | None = Field(default=None, alias="matterId")
    recipient_user_id: str = Field(alias="recipientUserId")
    due_at: str = Field(alias="dueAt")
    reminder_type: str = Field(alias="reminderType")
    obligation_class: str = Field(alias="obligationClass")
    urgency: str
    confidentiality_level: str = Field(alias="confidentialityLevel")
    template_key: str = Field(alias="templateKey")
    delivery_policy_key: str = Field(alias="deliveryPolicyKey")
    correlation_id: str = Field(alias="correlationId")

    model_config = ConfigDict(populate_by_name=True)
