"""Billing webhook integration — duplicate delivery and out-of-order events.

Uses BillingService with in-memory repositories so subscription, webhook-event,
audit, and outbox writes stay coupled without a live database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.auth.domain.models import Role
from src.modules.billing.domain.models import SubscriptionStatus, WebhookProcessingState
from src.modules.billing.ports import RawWebhook
from src.platform.request_context import RequestContext
from tests.unit.test_billing_service import (
    FakeClock,
    _subscription,
    make_service,
)

_NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def _signed_body(payload: dict[str, object]) -> bytes:
    unsigned = dict(payload)
    canonical = json.dumps(
        {k: unsigned[k] for k in sorted(unsigned)},
        sort_keys=True,
        separators=(",", ":"),
    )
    unsigned["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
    return json.dumps(unsigned).encode()


def _ctx() -> RequestContext:
    return RequestContext(actor_id="usr_a", account_role=Role.APPROVER, correlation_id="corr")


@pytest.mark.asyncio
async def test_duplicate_webhook_does_not_change_subscription_version() -> None:
    sub = _subscription(status=SubscriptionStatus.ACTIVE)
    svc = make_service(subs={"usr_a": sub})
    raw = RawWebhook(
        headers={},
        body=_signed_body(
            {
                "event_id": "evt_dup_integration",
                "event_type": "payment.failed",
                "status": "past_due",
                "subscription_id": "prov_sub_a",
                "customer_id": "cust_a",
                "occurred_at": _NOW.isoformat(),
            }
        ),
        provider="payhere",
    )
    first = await svc.handle_webhook("payhere", raw)
    version_after_first = (await svc.get_subscription(_ctx())).version

    second = await svc.handle_webhook("payhere", raw)
    version_after_second = (await svc.get_subscription(_ctx())).version

    assert first.processing_state == WebhookProcessingState.PROCESSED
    assert second.duplicate is True
    assert version_after_first == version_after_second == 2
    assert (await svc.get_subscription(_ctx())).status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_out_of_order_webhook_ignored_without_regressing_state() -> None:
    """A stale active event must not undo a newer past_due state."""
    stale_time = _NOW - timedelta(days=2)
    recent_time = _NOW - timedelta(hours=1)
    sub = replace(
        _subscription(status=SubscriptionStatus.PAST_DUE),
        provider_state_updated_at=recent_time,
    )
    svc = make_service(subs={"usr_a": sub}, clock=FakeClock(_NOW))

    raw = RawWebhook(
        headers={},
        body=_signed_body(
            {
                "event_id": "evt_stale_active",
                "event_type": "subscription.activated",
                "status": "active",
                "subscription_id": "prov_sub_a",
                "customer_id": "cust_a",
                "occurred_at": stale_time.isoformat(),
            }
        ),
        provider="payhere",
    )
    receipt = await svc.handle_webhook("payhere", raw)
    assert receipt.processing_state == WebhookProcessingState.IGNORED

    current = await svc.get_subscription(_ctx())
    assert current.status == SubscriptionStatus.PAST_DUE
    assert current.version == 1
