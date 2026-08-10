"""Contract tests for notification API schemas and reminder event."""

from __future__ import annotations

from src.modules.notification.api.schemas import (
    NotificationPreferenceListRead,
    NotificationPreferenceRead,
    ObligationReminderDueEventFixture,
)


class TestNotificationContract:
    def test_preference_list_serialises_camel_case(self):
        read = NotificationPreferenceListRead(
            items=[
                NotificationPreferenceRead(
                    channel="email",
                    enabled=True,
                    locale="en",
                    timezone="Asia/Colombo",
                    version=1,
                )
            ]
        )
        data = read.model_dump(by_alias=True)
        assert data["items"][0]["quietHoursStart"] is None
        assert "quiet_hours_start" not in data["items"][0]

    def test_obligation_reminder_due_fixture_has_no_private_fields(self):
        event = ObligationReminderDueEventFixture(
            eventId="evt-01K2DRAFTLY000000000001",
            occurredAt="2026-08-05T17:00:00+05:30",
            obligationId="obl-001",
            matterId="matter-synthetic-001",
            recipientUserId="user-synthetic-123",
            dueAt="2026-08-06T17:00:00+05:30",
            reminderType="due-in-24-hours",
            obligationClass="legal-deadline",
            urgency="critical",
            confidentialityLevel="private-matter",
            templateKey="obligation.reminder.due_in_24_hours",
            deliveryPolicyKey="legal-deadline.standard",
            correlationId="corr-01K2DRAFTLY00000000001",
        )
        payload = event.model_dump(by_alias=True)
        forbidden = ("client", "name", "address", "deed", "nic")
        for key in payload:
            lowered = key.lower()
            for word in forbidden:
                assert word not in lowered
