"""Unit tests for NotificationService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.modules.auth.domain.models import Role
from src.modules.notification.application.notification_service import (
    ConsumeOutcome,
    DeliveryOutcome,
    NotificationService,
)
from src.modules.notification.domain.errors import (
    PermanentDeliveryFailure,
    WebhookVerificationError,
)
from src.modules.notification.domain.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
    ProviderEvent,
)
from src.modules.notification.infrastructure.email.console_adapter import ConsoleEmailAdapter
from src.modules.notification.infrastructure.email.resend_webhook import ResendWebhookVerifier
from src.platform.messaging.envelope import EventEnvelope
from src.platform.request_context import RequestContext
from tests.factories.audit import FakeAudit

SYNTHETIC_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
TEMPLATE_KEY = "obligation.reminder.due"


class FakeClock:
    def now(self) -> datetime:
        return SYNTHETIC_NOW


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
        subject_ref: str,
        recipient_user_id: str,
        reminder_type: str,
        channel: NotificationChannel,
    ) -> NotificationDelivery | None:
        for row in self.by_id.values():
            if (
                row.organisation_id == organisation_id
                and row.subject_ref == subject_ref
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
        return PaginatedDeliveries(items=items[:limit], limit=limit)

    async def find_by_provider_message_id(
        self, *, provider_message_id: str
    ) -> NotificationDelivery | None:
        for row in self.by_id.values():
            if row.provider_message_id == provider_message_id:
                return row
        return None


class FakeConsumed:
    def __init__(self) -> None:
        self.ids: set[str] = set()

    async def already_consumed(self, *, event_id: str) -> bool:
        return event_id in self.ids

    async def record(
        self,
        *,
        event_id: str,
        event_name: str,
        organisation_id: str,
        outcome: str,
        correlation_id: str,
    ) -> bool:
        if event_id in self.ids:
            return False
        self.ids.add(event_id)
        return True


class FakeProviderEvents:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], ProviderEvent] = {}

    async def find(self, *, provider: str, provider_event_id: str) -> ProviderEvent | None:
        return self.rows.get((provider, provider_event_id))

    async def record(self, event: ProviderEvent) -> ProviderEvent:
        self.rows[(event.provider, event.provider_event_id)] = event
        return event


class FakeDeployments:
    async def resolve(self, *, environment: str, template_key: str, locale: NotificationLocale):
        return None


class FakeOutbox:
    def __init__(self) -> None:
        self.jobs: list[dict[str, Any]] = []
        self.events: list[EventEnvelope] = []

    async def publish_event(self, envelope: EventEnvelope) -> bool:
        self.events.append(envelope)
        return True

    async def enqueue_job(self, **kwargs: Any) -> bool:
        self.jobs.append(kwargs)
        return True


class FakeCompliance:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    async def is_allowlisted(self, user_id: str) -> bool:
        return self._allowed


class FakeRecipientResolver:
    def __init__(self, email: str | None = "solo@example.com") -> None:
        self._email = email

    async def resolve_email(self, user_id: str) -> str | None:
        return self._email


class FailingEmailPort:
    async def send(self, **kwargs: object) -> object:
        raise PermanentDeliveryFailure("provider_rejected_request")


def make_ctx(user_id: str = "usr_synthetic_001") -> RequestContext:
    return RequestContext(actor_id=user_id, account_role=Role.APPROVER, correlation_id="corr-1")


def reminder_envelope(
    *, event_id: str = "evt-01", obligation_id: str = "obl-001"
) -> dict[str, Any]:
    return {
        "eventId": event_id,
        "eventName": "obligation.reminder-due",
        "eventVersion": 1,
        "occurredAt": "2026-08-05T12:00:00+00:00",
        "organisationId": "usr_synthetic_001",
        "matterId": "matter-synthetic-001",
        "correlationId": "corr-1",
        "idempotencyKey": f"obligation.reminder-due:{event_id}",
        "data": {
            "obligationId": obligation_id,
            "recipientUserId": "usr_synthetic_001",
            "dueAt": "2026-08-06T12:00:00+00:00",
            "reminderType": "due-in-24-hours",
            "class": "legal-deadline",
            "urgency": "critical",
            "confidentialityLevel": "private-matter",
            "templateKey": TEMPLATE_KEY,
            "deliveryPolicyKey": "legal-deadline.standard",
        },
    }


def make_service(
    *,
    prefs: FakePreferences | None = None,
    deliveries: FakeDeliveries | None = None,
    email: object | None = None,
    audit: FakeAudit | None = None,
    resolver: FakeRecipientResolver | None = None,
    outbox: FakeOutbox | None = None,
    consumed: FakeConsumed | None = None,
    compliance: FakeCompliance | None = None,
    webhook_verifier: object | None = None,
) -> NotificationService:
    return NotificationService(
        preferences=prefs or FakePreferences(),
        deliveries=deliveries or FakeDeliveries(),
        consumed_events=consumed or FakeConsumed(),
        provider_events=FakeProviderEvents(),
        template_deployments=FakeDeployments(),
        email_port=email or ConsoleEmailAdapter(),
        audit_port=audit or FakeAudit(),
        outbox=outbox or FakeOutbox(),
        clock=FakeClock(),
        recipient_resolver=resolver or FakeRecipientResolver(),
        compliance_recipients=compliance or FakeCompliance(),
        webhook_verifier=webhook_verifier,
    )


class TestNotificationPreferences:
    @pytest.mark.asyncio
    async def test_get_preferences_returns_defaults_for_both_channels(self):
        svc = make_service()
        ctx = make_ctx()
        prefs = await svc.get_preferences(ctx)
        assert len(prefs) == 2

    @pytest.mark.asyncio
    async def test_patch_preferences_audits_change(self):
        audit = FakeAudit()
        outbox = FakeOutbox()
        svc = make_service(audit=audit, outbox=outbox)
        ctx = make_ctx()
        saved = await svc.patch_preferences(
            ctx,
            channel=NotificationChannel.EMAIL,
            enabled=False,
            locale=NotificationLocale.SI,
        )
        assert saved.enabled is False
        assert any(e.action == "notification.preference-changed" for e in audit.events)
        assert any(e.event_name == "notification.preference-changed" for e in outbox.events)


class TestEventConsumption:
    @pytest.mark.asyncio
    async def test_handle_event_creates_two_channel_deliveries(self):
        deliveries = FakeDeliveries()
        outbox = FakeOutbox()
        svc = make_service(deliveries=deliveries, outbox=outbox)
        result = await svc.handle_event(reminder_envelope())
        assert result.outcome is ConsumeOutcome.PROCESSED
        assert len(deliveries.by_id) == 2
        assert len(outbox.jobs) == 2

    @pytest.mark.asyncio
    async def test_duplicate_event_is_idempotent(self):
        deliveries = FakeDeliveries()
        outbox = FakeOutbox()
        svc = make_service(deliveries=deliveries, outbox=outbox)
        first = await svc.handle_event(reminder_envelope(event_id="evt-dup"))
        second = await svc.handle_event(reminder_envelope(event_id="evt-dup"))
        assert first.outcome is ConsumeOutcome.PROCESSED
        assert second.outcome is ConsumeOutcome.DUPLICATE
        assert len(deliveries.by_id) == 2
        assert len(outbox.jobs) == 2

    @pytest.mark.asyncio
    async def test_disabled_preference_suppresses_email_channel(self):
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
        await svc.handle_event(reminder_envelope(event_id="evt-sup"))
        statuses = {row.status for row in deliveries.by_id.values()}
        assert DeliveryStatus.SUPPRESSED in statuses


class TestDeliverJob:
    @pytest.mark.asyncio
    async def test_deliver_marks_email_delivered(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_1",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-1",
            subject_ref="obl-1",
            obligation_id="obl-1",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key=TEMPLATE_KEY,
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
        outcome = await svc.deliver(delivery_id=delivery.id, organisation_id="usr_synthetic_001")
        assert outcome is DeliveryOutcome.DELIVERED
        updated = deliveries.by_id[delivery.id]
        assert updated.status == DeliveryStatus.DELIVERED
        assert len(email.sent) == 1

    @pytest.mark.asyncio
    async def test_deliver_failure_does_not_raise(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_2",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-2",
            subject_ref="obl-2",
            obligation_id="obl-2",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key=TEMPLATE_KEY,
            delivery_policy_key="legal-deadline.standard",
            locale=NotificationLocale.EN,
            status=DeliveryStatus.QUEUED,
            attempt_count=0,
            created_at=SYNTHETIC_NOW,
        )
        deliveries.by_id[delivery.id] = delivery
        svc = make_service(deliveries=deliveries, email=FailingEmailPort())
        outcome = await svc.deliver(delivery_id=delivery.id, organisation_id="usr_synthetic_001")
        assert outcome is DeliveryOutcome.PERMANENT_FAILURE
        assert deliveries.by_id[delivery.id].status == DeliveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_deliver_is_idempotent_when_already_delivered(self):
        deliveries = FakeDeliveries()
        delivery = NotificationDelivery(
            id="nd_test_3",
            organisation_id="usr_synthetic_001",
            source_event_id="evt-3",
            subject_ref="obl-3",
            obligation_id="obl-3",
            matter_id=None,
            recipient_user_id="usr_synthetic_001",
            channel=NotificationChannel.EMAIL,
            reminder_type="due-today",
            obligation_class="legal-deadline",
            urgency="normal",
            confidentiality_level="private-matter",
            template_key=TEMPLATE_KEY,
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


class TestWebhookVerification:
    def test_unsigned_webhook_rejected(self):
        verifier = ResendWebhookVerifier(
            "whsec_" + __import__("base64").b64encode(b"secret").decode()
        )
        with pytest.raises(WebhookVerificationError):
            verifier.verify(headers={}, raw_body=b"{}")

    def test_signed_fixture_accepted(self):
        import base64
        import hashlib
        import hmac
        import json
        import time

        secret_bytes = b"test-webhook-secret"
        secret = "whsec_" + base64.b64encode(secret_bytes).decode()
        verifier = ResendWebhookVerifier(secret, tolerance_seconds=600)
        body = json.dumps({"type": "email.delivered", "data": {"email_id": "msg-1"}})
        msg_id = "msg_test"
        timestamp = str(int(time.time()))
        signed = f"{msg_id}.{timestamp}.{body}".encode()
        signature = base64.b64encode(
            hmac.new(secret_bytes, signed, hashlib.sha256).digest()
        ).decode()
        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": f"v1,{signature}",
        }
        payload = verifier.verify(headers=headers, raw_body=body.encode())
        assert payload["type"] == "email.delivered"
