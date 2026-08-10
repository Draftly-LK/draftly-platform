"""Unit tests for NotificationService."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.auth.domain.models import Role
from src.modules.auth.ports import AuditEventInput
from src.modules.notification.application.notification_service import NotificationService
from src.modules.notification.domain.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
)
from src.modules.notification.infrastructure.email.console_adapter import ConsoleEmailAdapter
from src.platform.request_context import RequestContext

SYNTHETIC_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return SYNTHETIC_NOW


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


class FakePreferences:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, NotificationChannel], NotificationPreference] = {}

    async def list_for_user(
        self, *, organisation_id: str, user_id: str
    ) -> list[NotificationPreference]:
        return [p for p in self.rows.values() if p.user_id == user_id]

    async def get(
        self, *, organisation_id: str, user_id: str, channel: NotificationChannel
    ) -> NotificationPreference | None:
        return self.rows.get((organisation_id, user_id, channel))

    async def upsert(self, preference: NotificationPreference) -> NotificationPreference:
        self.rows[(preference.organisation_id, preference.user_id, preference.channel)] = preference
        return preference


class FakeDeliveries:
    def __init__(self) -> None:
        self.by_id: dict[str, NotificationDelivery] = {}

    async def get_by_id(
        self, *, organisation_id: str, delivery_id: str
    ) -> NotificationDelivery | None:
        row = self.by_id.get(delivery_id)
        if row and row.organisation_id == organisation_id:
            return row
        return None

    async def get_idempotent(
        self,
        *,
        organisation_id: str,
        obligation_id: str,
        recipient_user_id: str,
        reminder_type: str,
        channel: NotificationChannel,
    ) -> NotificationDelivery | None:
        for row in self.by_id.values():
            if (
                row.organisation_id == organisation_id
                and row.obligation_id == obligation_id
                and row.recipient_user_id == recipient_user_id
                and row.reminder_type == reminder_type
                and row.channel == channel
            ):
                return row
        return None

    async def create(self, delivery: NotificationDelivery) -> NotificationDelivery:
        self.by_id[delivery.id] = delivery
        return delivery

    async def update(self, delivery: NotificationDelivery) -> NotificationDelivery:
        self.by_id[delivery.id] = delivery
        return delivery

    async def list_in_app_for_user(
        self,
        *,
        organisation_id: str,
        user_id: str,
        limit: int,
        cursor: str | None,
    ) -> PaginatedDeliveries:
        items = [
            d
            for d in self.by_id.values()
            if d.organisation_id == organisation_id
            and d.recipient_user_id == user_id
            and d.channel == NotificationChannel.IN_APP
        ]
        return PaginatedDeliveries(items=items[:limit])

    async def find_by_provider_message_id(
        self, *, provider_message_id: str
    ) -> NotificationDelivery | None:
        for row in self.by_id.values():
            if row.provider_message_id == provider_message_id:
                return row
        return None


class FakeRecipientResolver:
    def __init__(self, email: str | None = "solo@example.com") -> None:
        self._email = email

    async def resolve_email(self, user_id: str) -> str | None:
        return self._email


class FailingEmailPort:
    async def send(self, **kwargs: object) -> object:
        raise RuntimeError("provider_down")


def make_ctx(user_id: str = "usr_synthetic_001") -> RequestContext:
    return RequestContext(actor_id=user_id, account_role=Role.APPROVER, correlation_id="corr-1")


def make_service(
    *,
    prefs: FakePreferences | None = None,
    deliveries: FakeDeliveries | None = None,
    email: object | None = None,
    audit: FakeAudit | None = None,
    resolver: FakeRecipientResolver | None = None,
) -> NotificationService:
    return NotificationService(
        preferences=prefs or FakePreferences(),
        deliveries=deliveries or FakeDeliveries(),
        email_port=email or ConsoleEmailAdapter(),
        audit_port=audit or FakeAudit(),
        clock=FakeClock(),
        recipient_resolver=resolver or FakeRecipientResolver(),
    )


class TestNotificationPreferences:
    @pytest.mark.asyncio
    async def test_get_preferences_returns_defaults_for_both_channels(self):
        svc = make_service()
        ctx = make_ctx()
        prefs = await svc.get_preferences(ctx)
        assert len(prefs) == 2
        assert {p.channel for p in prefs} == {
            NotificationChannel.EMAIL,
            NotificationChannel.IN_APP,
        }

    @pytest.mark.asyncio
    async def test_patch_preferences_audits_change(self):
        audit = FakeAudit()
        svc = make_service(audit=audit)
        ctx = make_ctx()
        saved = await svc.patch_preferences(
            ctx,
            channel=NotificationChannel.EMAIL,
            enabled=False,
            locale=NotificationLocale.SI,
        )
        assert saved.enabled is False
        assert saved.locale == NotificationLocale.SI
        assert any(e.action == "notification.preference-changed" for e in audit.events)


class TestDeliveryIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_create_returns_existing_row(self):
        deliveries = FakeDeliveries()
        svc = make_service(deliveries=deliveries)
        delivery_args = {
            "organisation_id": "usr_synthetic_001",
            "source_event_id": "evt-01",
            "obligation_id": "obl-001",
            "matter_id": "matter-synthetic-001",
            "recipient_user_id": "usr_synthetic_001",
            "channel": NotificationChannel.EMAIL,
            "reminder_type": "due-in-24-hours",
            "obligation_class": "legal-deadline",
            "urgency": "critical",
            "confidentiality_level": "private-matter",
            "template_key": "obligation.reminder.due_in_24_hours",
            "delivery_policy_key": "legal-deadline.standard",
            "locale": NotificationLocale.EN,
        }
        first = await svc.create_delivery_idempotent(**delivery_args)
        second = await svc.create_delivery_idempotent(**delivery_args)
        assert first.id == second.id
        assert len(deliveries.by_id) == 1

    @pytest.mark.asyncio
    async def test_disabled_preference_suppresses_delivery(self):
        prefs = FakePreferences()
        await prefs.upsert(
            NotificationPreference(
                id="np_1",
                organisation_id="usr_synthetic_001",
                user_id="usr_synthetic_001",
                channel=NotificationChannel.EMAIL,
                enabled=False,
                locale=NotificationLocale.EN,
                timezone="Asia/Colombo",
            )
        )
        deliveries = FakeDeliveries()
        svc = make_service(prefs=prefs, deliveries=deliveries)
        saved = await svc.create_delivery_idempotent(
            organisation_id="usr_synthetic_001",
            source_event_id="evt-02",
            obligation_id="obl-002",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key="obligation.reminder.due_in_24_hours",
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
        )
        assert saved.status == DeliveryStatus.SUPPRESSED


class TestDeliverJob:
    @pytest.mark.asyncio
    async def test_deliver_marks_email_delivered(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_1",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-1",
            obligation_id="obl-1",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key="obligation.reminder.due_in_24_hours",
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
            status=DeliveryStatus.QUEUED,
            attempt_count=0,
            created_at=SYNTHETIC_NOW,
        )
        deliveries.by_id[delivery.id] = delivery
        email = ConsoleEmailAdapter()
        audit = FakeAudit()
        svc = make_service(deliveries=deliveries, email=email, audit=audit)
        await svc.deliver(delivery_id=delivery.id, organisation_id="usr_synthetic_001")
        updated = deliveries.by_id[delivery.id]
        assert updated.status == DeliveryStatus.DELIVERED
        assert updated.provider_message_id is not None
        assert len(email.sent) == 1
        assert email.sent[0]["idempotency_key"] == delivery.id

    @pytest.mark.asyncio
    async def test_deliver_failure_does_not_raise(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_2",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-2",
            obligation_id="obl-2",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key="obligation.reminder.due_in_24_hours",
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
            status=DeliveryStatus.QUEUED,
            attempt_count=0,
            created_at=SYNTHETIC_NOW,
        )
        deliveries.by_id[delivery.id] = delivery
        svc = make_service(deliveries=deliveries, email=FailingEmailPort())
        await svc.deliver(delivery_id=delivery.id, organisation_id="usr_synthetic_001")
        assert deliveries.by_id[delivery.id].status == DeliveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_deliver_is_idempotent_when_already_delivered(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_3",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-3",
            obligation_id="obl-3",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key="obligation.reminder.due_in_24_hours",
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
            status=DeliveryStatus.DELIVERED,
            attempt_count=1,
            created_at=SYNTHETIC_NOW,
            provider_message_id="console_existing",
        )
        deliveries.by_id[delivery.id] = delivery
        email = ConsoleEmailAdapter()
        svc = make_service(deliveries=deliveries, email=email)
        await svc.deliver(delivery_id=delivery.id, organisation_id="usr_synthetic_001")
        assert len(email.sent) == 0
