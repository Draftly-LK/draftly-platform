"""Billing adapters and pure policies: webhook authenticity, event identity, gates.

No network: the adapter's checkout and portal methods only build URLs, and
webhook verification is pure HMAC over the raw request body. All secrets and
identifiers are synthetic.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from src.modules.auth.domain.models import AccountStatus
from src.modules.billing.domain import policies
from src.modules.billing.domain.errors import InvalidWebhookError
from src.modules.billing.domain.models import PlanState, SubscriptionStatus
from src.modules.billing.infrastructure.payhere_adapter import (
    SIGNATURE_HEADER,
    PayHereBillingAdapter,
)
from src.modules.billing.infrastructure.user_read import AuthUserReadAdapter
from src.modules.billing.ports import CheckoutCommand, RawWebhook

SECRET = "synthetic-merchant-secret"


@pytest.fixture
def adapter() -> PayHereBillingAdapter:
    return PayHereBillingAdapter(
        merchant_secret=SECRET, checkout_base_url="https://payhere.example.test/"
    )


def _sign(raw: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _signed_by_header(payload: dict[str, Any], secret: str = SECRET) -> RawWebhook:
    raw = json.dumps(payload).encode()
    return RawWebhook(headers={SIGNATURE_HEADER: _sign(raw, secret)}, body=raw, provider="payhere")


def _signed_by_checksum(payload: dict[str, Any], field: str = "checksum") -> RawWebhook:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    body = json.dumps({**payload, field: _sign(canonical)}).encode()
    return RawWebhook(headers={}, body=body, provider="payhere")


PAYLOAD: dict[str, Any] = {
    "event_id": "evt_synthetic_1",
    "event_type": "subscription.renewed",
    "subscription_id": "sub_1",
    "customer_id": "cus_1",
    "status": "active",
    "occurred_at": "2026-04-01T08:00:00",
}


# ── Webhook verification ────────────────────────────────────────────────────


async def test_a_header_signed_webhook_is_accepted_and_mapped(
    adapter: PayHereBillingAdapter,
) -> None:
    request = _signed_by_header(PAYLOAD)

    event = await adapter.verify_webhook(request)

    assert event.provider_event_id == "evt_synthetic_1"
    assert event.event_type == "subscription.renewed"
    assert event.provider_subscription_id == "sub_1"
    assert event.provider_customer_id == "cus_1"
    assert event.normalized_status == "active"
    # A naive provider timestamp is read as UTC, never as local time.
    assert event.occurred_at == datetime(2026, 4, 1, 8, 0, tzinfo=UTC)
    assert event.payload_hash == hashlib.sha256(request.body).hexdigest()


async def test_signature_comparison_ignores_case_and_surrounding_whitespace(
    adapter: PayHereBillingAdapter,
) -> None:
    raw = json.dumps(PAYLOAD).encode()
    request = RawWebhook(
        headers={SIGNATURE_HEADER: f"  {_sign(raw).upper()} "}, body=raw, provider="payhere"
    )
    assert (await adapter.verify_webhook(request)).provider_event_id == "evt_synthetic_1"


async def test_a_webhook_signed_with_another_secret_is_rejected(
    adapter: PayHereBillingAdapter,
) -> None:
    with pytest.raises(InvalidWebhookError):
        await adapter.verify_webhook(_signed_by_header(PAYLOAD, secret="attacker"))


async def test_a_body_altered_after_signing_is_rejected(adapter: PayHereBillingAdapter) -> None:
    signed = _signed_by_header(PAYLOAD)
    tampered = RawWebhook(
        headers=signed.headers,
        body=signed.body.replace(b'"active"', b'"cancelled"'),
        provider="payhere",
    )
    with pytest.raises(InvalidWebhookError):
        await adapter.verify_webhook(tampered)


@pytest.mark.parametrize("field", ["checksum", "md5sig"])
async def test_a_payload_checksum_is_accepted_when_no_header_is_sent(
    adapter: PayHereBillingAdapter, field: str
) -> None:
    event = await adapter.verify_webhook(_signed_by_checksum(PAYLOAD, field))
    assert event.provider_event_id == "evt_synthetic_1"


async def test_an_unsigned_webhook_is_rejected(adapter: PayHereBillingAdapter) -> None:
    request = RawWebhook(headers={}, body=json.dumps(PAYLOAD).encode(), provider="payhere")
    with pytest.raises(InvalidWebhookError):
        await adapter.verify_webhook(request)


async def test_a_checksum_over_different_fields_is_rejected(
    adapter: PayHereBillingAdapter,
) -> None:
    signed = json.loads(_signed_by_checksum(PAYLOAD).body)
    signed["status"] = "cancelled"
    request = RawWebhook(headers={}, body=json.dumps(signed).encode(), provider="payhere")
    with pytest.raises(InvalidWebhookError):
        await adapter.verify_webhook(request)


@pytest.mark.parametrize("body", [b"\xff\xfe not utf-8", b"not json", b'["a", "list"]'])
async def test_a_correctly_signed_but_malformed_body_is_rejected(
    adapter: PayHereBillingAdapter, body: bytes
) -> None:
    request = RawWebhook(headers={SIGNATURE_HEADER: _sign(body)}, body=body, provider="payhere")
    with pytest.raises(InvalidWebhookError):
        await adapter.verify_webhook(request)


async def test_the_rejection_carries_nothing_from_the_payload(
    adapter: PayHereBillingAdapter,
) -> None:
    with pytest.raises(InvalidWebhookError) as excinfo:
        await adapter.verify_webhook(_signed_by_header(PAYLOAD, secret="attacker"))
    assert excinfo.value.details == {}
    assert "cus_1" not in excinfo.value.message


async def test_event_id_falls_back_to_payment_id_plus_payload_hash(
    adapter: PayHereBillingAdapter,
) -> None:
    payload = {"payment_id": 320025, "status": "2", "occurred_at": "not a date"}
    request = _signed_by_header(payload)

    first = await adapter.verify_webhook(request)
    replay = await adapter.verify_webhook(request)

    digest = hashlib.sha256(request.body).hexdigest()
    assert first.provider_event_id == f"320025:{digest[:32]}"
    # Stable across retries, which is what replay detection relies on.
    assert replay.provider_event_id == first.provider_event_id
    assert first.event_type == "2"
    assert first.occurred_at is None
    assert first.provider_subscription_id is None


async def test_an_event_with_no_identifiers_still_gets_a_deterministic_id(
    adapter: PayHereBillingAdapter,
) -> None:
    request = _signed_by_header({"subscription_id": "  "})
    event = await adapter.verify_webhook(request)
    assert event.provider_event_id.startswith("no-payment-id:")
    assert event.event_type == "unknown"
    assert event.provider_subscription_id is None


async def test_an_aware_timestamp_keeps_its_offset(adapter: PayHereBillingAdapter) -> None:
    event = await adapter.verify_webhook(
        _signed_by_header({**PAYLOAD, "occurred_at": "2026-04-01T13:30:00+05:30"})
    )
    assert event.occurred_at is not None
    assert event.occurred_at.utcoffset() == timedelta(hours=5, minutes=30)


# ── Checkout and portal ─────────────────────────────────────────────────────


async def test_checkout_urls_are_built_on_the_configured_base(
    adapter: PayHereBillingAdapter,
) -> None:
    command = CheckoutCommand(
        user_id="usr_1",
        plan_version_id="plv_1",
        return_path="/settings/billing",
        currency="LKR",
        price_minor_units=500000,
    )
    first = await adapter.create_checkout(command)
    second = await adapter.create_checkout(command)

    assert first.provider_session_id.startswith("ph_sess_")
    assert first.checkout_url == f"https://payhere.example.test/pay/{first.provider_session_id}"
    assert first.provider_session_id != second.provider_session_id

    portal = await adapter.create_customer_portal("cus_1")
    assert portal.portal_url == "https://payhere.example.test/customer/cus_1"


async def test_fetch_subscription_echoes_the_requested_id(adapter: PayHereBillingAdapter) -> None:
    subscription = await adapter.fetch_subscription("sub_9")
    assert subscription.provider_subscription_id == "sub_9"
    assert subscription.provider_customer_id == "ph_cust_sub_9"
    assert await adapter.cancel_subscription("sub_9") is None
    assert await adapter.reactivate_subscription("sub_9") is None


# ── User read adapter ───────────────────────────────────────────────────────


class _Users:
    def __init__(self, status: AccountStatus | None) -> None:
        self._status = status

    async def get(self, user_id: str) -> Any:
        if self._status is None:
            return None
        return SimpleNamespace(id=user_id, account_status=self._status)


async def test_only_an_active_account_is_an_active_billing_user() -> None:
    inactive = [status for status in AccountStatus if status is not AccountStatus.ACTIVE]
    assert inactive

    active = await AuthUserReadAdapter(_Users(AccountStatus.ACTIVE)).get_billing_user("usr_1")  # type: ignore[arg-type]
    assert active is not None and active.is_active and active.user_id == "usr_1"
    for status in inactive:
        user = await AuthUserReadAdapter(_Users(status)).get_billing_user("usr_1")  # type: ignore[arg-type]
        assert user is not None and user.is_active is False
    assert await AuthUserReadAdapter(_Users(None)).get_billing_user("usr_1") is None  # type: ignore[arg-type]


# ── Policies ────────────────────────────────────────────────────────────────


def test_restricted_mode_blocks_new_paid_work_only() -> None:
    restricted = SubscriptionStatus.RESTRICTED
    assert not policies.subscription_allows_feature(restricted, "drafting.enabled")
    assert not policies.subscription_allows_feature(restricted, "export.enabled")
    assert policies.subscription_allows_feature(restricted, "storage_bytes.max")
    for status in set(SubscriptionStatus) - {restricted}:
        assert policies.subscription_allows_feature(status, "drafting.enabled")


def test_restricted_mode_blocks_by_entitlement_key() -> None:
    assert policies.restricted_mode_blocks("research.enabled")
    assert policies.restricted_mode_blocks("whatsapp_notifications.enabled")
    assert not policies.restricted_mode_blocks("users.max")


def test_restricted_mode_blocks_creating_new_matters() -> None:
    """Regression: ``matter.create`` is listed as blocked but was never matched.

    The lookup translated the gate to its entitlement key (``active_matters.max``)
    before checking the blocked set, so the ``matter.create`` entry was dead and a
    restricted subscription could still open new matters (billing-service.md §10).
    """
    assert "matter.create" in policies.RESTRICTED_BLOCKED_FEATURES
    assert policies.restricted_mode_blocks("matter.create")
    assert not policies.subscription_allows_feature(SubscriptionStatus.RESTRICTED, "matter.create")
    assert policies.subscription_allows_feature(SubscriptionStatus.ACTIVE, "matter.create")


def test_grace_and_restricted_entry_points() -> None:
    assert policies.should_enter_grace(SubscriptionStatus.PAST_DUE)
    assert policies.should_enter_grace(SubscriptionStatus.ACTIVE)
    assert not policies.should_enter_grace(SubscriptionStatus.CANCELLED)
    assert policies.should_enter_restricted(SubscriptionStatus.GRACE_PERIOD)
    assert policies.should_enter_restricted(SubscriptionStatus.PAST_DUE)
    assert not policies.should_enter_restricted(SubscriptionStatus.ACTIVE)


def test_an_expired_subscription_is_terminal() -> None:
    for status in set(SubscriptionStatus) - {SubscriptionStatus.EXPIRED}:
        assert not policies.can_transition(SubscriptionStatus.EXPIRED, status)
    assert policies.can_transition(SubscriptionStatus.RESTRICTED, SubscriptionStatus.ACTIVE)
    assert not policies.can_transition(SubscriptionStatus.RESTRICTED, SubscriptionStatus.TRIALING)


def test_out_of_order_provider_events_are_stale_only_when_both_times_are_known() -> None:
    now = datetime(2026, 4, 1, tzinfo=UTC)
    earlier = now - timedelta(minutes=5)
    assert policies.is_stale_provider_event(earlier, now)
    assert not policies.is_stale_provider_event(now, earlier)
    assert not policies.is_stale_provider_event(now, now)
    assert not policies.is_stale_provider_event(None, now)
    assert not policies.is_stale_provider_event(earlier, None)


@pytest.mark.parametrize(
    ("path", "safe"),
    [
        ("/settings/billing", True),
        ("/", True),
        ("https://evil.example.test", False),
        ("//evil.example.test", False),
        ("settings", False),
        ("/ok\\evil", False),
        ("/ok\r\nLocation: x", False),
        ("/tab\there", False),
        ("", False),
    ],
)
def test_checkout_return_path_cannot_be_an_open_redirect(path: str, safe: bool) -> None:
    assert policies.is_safe_return_path(path) is safe


@pytest.mark.parametrize(
    ("currency", "amount", "valid"),
    [
        ("LKR", 0, True),
        ("USD", 499900, True),
        ("lkr", 100, False),
        ("LK", 100, False),
        ("LK1", 100, False),
        ("LKR", -1, False),
        ("LKR", True, False),
        ("LKR", 10.5, False),
    ],
)
def test_money_is_integer_minor_units_and_an_iso_shaped_currency(
    currency: str, amount: Any, valid: bool
) -> None:
    assert policies.is_valid_money(currency, amount) is valid


def test_only_a_draft_plan_is_mutable() -> None:
    assert policies.is_plan_mutable(PlanState.DRAFT)
    for state in set(PlanState) - {PlanState.DRAFT}:
        assert not policies.is_plan_mutable(state)
