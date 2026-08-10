"""Security tests — notification preferences and in-app list are self-scoped."""

from __future__ import annotations

import pytest

from src.modules.notification.application.notification_service import NotificationService
from src.modules.notification.domain.errors import NotificationNotFoundError
from src.modules.notification.domain.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
)
from src.modules.notification.infrastructure.email.console_adapter import ConsoleEmailAdapter
from tests.unit.test_notification_service import (
    SYNTHETIC_NOW,
    FakeAudit,
    FakeClock,
    FakeDeliveries,
    FakePreferences,
    FakeRecipientResolver,
    make_ctx,
    make_service,
)


class TestNotificationSecurity:
    @pytest.mark.asyncio
    async def test_actor_cannot_read_another_users_notification(self):
        deliveries = FakeDeliveries()
        other_delivery = NotificationDelivery(
            id="nd_other",
            organisation_id="usr_other",
            source_event_id="evt-x",
            obligation_id="obl-x",
            matter_id=None,
            recipient_user_id="usr_other",
            channel=NotificationChannel.IN_APP,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key="obligation.reminder.due_in_24_hours",
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
            status=DeliveryStatus.DELIVERED,
            attempt_count=0,
            created_at=SYNTHETIC_NOW,
        )
        deliveries.by_id[other_delivery.id] = other_delivery
        svc = make_service(deliveries=deliveries)
        ctx = make_ctx("usr_synthetic_001")
        with pytest.raises(NotificationNotFoundError):
            await svc.get_notification_for_actor(ctx, "nd_other")

    @pytest.mark.asyncio
    async def test_preferences_patch_only_affects_actor(self):
        prefs = FakePreferences()
        svc = NotificationService(
            preferences=prefs,
            deliveries=FakeDeliveries(),
            email_port=ConsoleEmailAdapter(),
            audit_port=FakeAudit(),
            clock=FakeClock(),
            recipient_resolver=FakeRecipientResolver(),
        )
        ctx = make_ctx("usr_a")
        saved = await svc.patch_preferences(ctx, channel=NotificationChannel.EMAIL, enabled=False)
        assert saved.user_id == "usr_a"
        assert all(p.user_id == "usr_a" for p in prefs.rows.values())
