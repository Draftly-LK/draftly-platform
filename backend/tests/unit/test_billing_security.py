"""Security-focused billing tests."""

from __future__ import annotations

import json

import pytest

from src.modules.auth.domain.models import Role
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.errors import InvalidWebhookError
from src.modules.billing.domain.models import SubscriptionStatus
from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter
from src.modules.billing.ports import RawWebhook
from tests.unit.test_billing_service import (
    DenyPlatformAdminPort,
    FakeAudit,
    FakeClock,
    FakeEventPort,
    FakePlanRepo,
    FakeSubscriptionRepo,
    FakeUsageRepo,
    FakeUserReadPort,
    FakeWebhookRepo,
    _plan,
    _solo_entitlements,
    _subscription,
    ctx,
    make_service,
)


class TestCrossUserIsolation:
    @pytest.mark.asyncio
    async def test_subscription_scoped_to_actor(self):
        svc = make_service(
            subs={
                "usr_a": _subscription(user_id="usr_a"),
                "usr_b": _subscription(user_id="usr_b", status=SubscriptionStatus.ACTIVE),
            }
        )
        sub = await svc.get_subscription(ctx(actor_id="usr_a"))
        assert sub.user_id == "usr_a"

    @pytest.mark.asyncio
    async def test_other_user_has_own_subscription_record(self):
        other = _subscription(user_id="usr_b")
        other.id = "sub_b"
        other.provider_subscription_id = "prov_sub_b"
        svc = make_service(
            subs={
                "usr_a": _subscription(user_id="usr_a"),
                "usr_b": other,
            }
        )
        sub_b = await svc.get_subscription(ctx(actor_id="usr_b", role=Role.APPROVER))
        assert sub_b.id == "sub_b"


class TestForgedUserIgnored:
    @pytest.mark.asyncio
    async def test_checkout_uses_actor_not_body_user(self):
        """Checkout command is built from RequestContext.actor_id in the service."""
        captured: list[str] = []

        class RecordingStub(StubBillingAdapter):
            async def create_checkout(self, command):  # type: ignore[no-untyped-def]
                captured.append(command.user_id)
                return await super().create_checkout(command)

        svc = BillingService(
            plan_repo=FakePlanRepo([_plan()], {"plan_solo_v1": _solo_entitlements()}),
            subscription_repo=FakeSubscriptionRepo({"usr_a": _subscription()}),
            usage_repo=FakeUsageRepo(),
            webhook_repo=FakeWebhookRepo(),
            billing_provider=RecordingStub(),
            user_read_port=FakeUserReadPort(),
            platform_admin_port=DenyPlatformAdminPort(),
            audit_port=FakeAudit(),
            event_port=FakeEventPort(),
            clock=FakeClock(),
            grace_period_days=14,
        )
        await svc.create_checkout(ctx(actor_id="usr_a"), "plan_solo_v1", "/billing")
        assert captured == ["usr_a"]


class TestInvalidWebhook:
    @pytest.mark.asyncio
    async def test_bad_checksum_rejected(self):
        svc = make_service()
        body = json.dumps(
            {
                "event_id": "evt_bad",
                "event_type": "payment.failed",
                "subscription_id": "prov_sub_a",
                "checksum": "not-valid",
            }
        ).encode()
        with pytest.raises(InvalidWebhookError):
            await svc.handle_webhook(
                "payhere",
                RawWebhook(headers={}, body=body, provider="payhere"),
            )

    @pytest.mark.asyncio
    async def test_unmapped_subscription_ignored_without_leak(self):
        svc = make_service()
        payload = {
            "event_id": "evt_unknown_sub",
            "event_type": "payment.failed",
            "status": "past_due",
            "subscription_id": "unknown_provider_sub",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        import hashlib

        payload["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
        receipt = await svc.handle_webhook(
            "payhere",
            RawWebhook(headers={}, body=json.dumps(payload).encode(), provider="payhere"),
        )
        assert receipt.processing_state.value == "ignored"
