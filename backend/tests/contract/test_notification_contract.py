"""Contract tests for notification API schemas and reminder event."""

from __future__ import annotations

from pathlib import Path

from src.modules.notification.api.schemas import (
    NotificationPreferenceListRead,
    NotificationPreferenceRead,
    ObligationReminderDueEventFixture,
)
from src.modules.notification.domain.policies import EVENT_TEMPLATE_ROUTES


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
            organisationId="usr_synthetic_001",
            matterId="matter-synthetic-001",
            correlationId="corr-01K2DRAFTLY00000000001",
            idempotencyKey="obligation.reminder-due:evt-01K2DRAFTLY000000000001",
            data={
                "obligationId": "obl-001",
                "recipientUserId": "user-synthetic-123",
                "dueAt": "2026-08-06T17:00:00+05:30",
                "reminderType": "due-in-24-hours",
                "class": "legal-deadline",
                "urgency": "critical",
                "confidentialityLevel": "private-matter",
                "templateKey": "obligation.reminder.due",
                "deliveryPolicyKey": "legal-deadline.standard",
            },
        )
        payload = event.model_dump(by_alias=True)
        forbidden = ("client", "address", "deed", "nic")
        data = payload.get("data", {})
        for key in data:
            lowered = str(key).lower()
            for word in forbidden:
                assert word not in lowered

    def test_every_consumed_event_has_template_route(self):
        services_path = Path(__file__).resolve().parents[2] / "contracts" / "services.yaml"
        text = services_path.read_text(encoding="utf-8")
        for event_name in EVENT_TEMPLATE_ROUTES:
            assert event_name in text
