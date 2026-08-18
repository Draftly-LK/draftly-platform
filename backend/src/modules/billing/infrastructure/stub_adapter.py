"""Stub billing provider for CI and local development."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from src.modules.billing.domain.errors import InvalidWebhookError
from src.modules.billing.ports import (
    Checkout,
    CheckoutCommand,
    Portal,
    ProviderEvent,
    ProviderSubscription,
    RawWebhook,
)


def _occurred_at(value: Any) -> datetime:
    """Honour a fixture-supplied timestamp so out-of-order tests stay deterministic."""
    if value is None:
        return datetime.now(tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(tz=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class StubBillingAdapter:
    """Deterministic PayHere-shaped stub — never used for real payments."""

    async def create_checkout(self, command: CheckoutCommand) -> Checkout:
        session_id = f"stub_sess_{uuid.uuid4().hex[:12]}"
        return Checkout(
            checkout_url=f"https://stub.payhere.local/checkout/{session_id}",
            provider_session_id=session_id,
        )

    async def create_customer_portal(self, customer_id: str) -> Portal:
        return Portal(portal_url=f"https://stub.payhere.local/portal/{customer_id}")

    async def cancel_subscription(self, subscription_id: str) -> None:
        _ = subscription_id

    async def reactivate_subscription(self, subscription_id: str) -> None:
        _ = subscription_id

    async def verify_webhook(self, request: RawWebhook) -> ProviderEvent:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InvalidWebhookError()
        if not isinstance(payload, dict):
            raise InvalidWebhookError()

        provided = payload.get("checksum")
        if not provided:
            raise InvalidWebhookError()

        body_for_hash = {k: v for k, v in payload.items() if k != "checksum"}
        canonical = json.dumps(body_for_hash, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(str(provided), digest):
            raise InvalidWebhookError()

        provider_event_id = str(payload.get("event_id") or payload.get("payment_id") or digest)
        return ProviderEvent(
            provider_event_id=provider_event_id,
            event_type=str(payload.get("event_type") or "unknown"),
            provider_subscription_id=payload.get("subscription_id"),
            provider_customer_id=payload.get("customer_id"),
            occurred_at=_occurred_at(payload.get("occurred_at")),
            normalized_status=payload.get("status"),
            payload_hash=digest,
        )

    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription:
        return ProviderSubscription(
            provider_subscription_id=subscription_id,
            provider_customer_id=f"cust_{subscription_id}",
            status="active",
        )
