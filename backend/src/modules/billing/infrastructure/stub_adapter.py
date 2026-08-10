"""Stub billing provider for CI and local development."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from src.modules.billing.domain.errors import InvalidWebhookError
from src.modules.billing.ports import (
    Checkout,
    CheckoutCommand,
    Portal,
    ProviderEvent,
    ProviderSubscription,
    RawWebhook,
)


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
            raise InvalidWebhookError("Invalid webhook payload.")

        expected = payload.get("checksum")
        if not expected:
            raise InvalidWebhookError("Missing checksum.")

        body_for_hash = {k: v for k, v in payload.items() if k != "checksum"}
        canonical = json.dumps(body_for_hash, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if digest != expected:
            raise InvalidWebhookError("Checksum mismatch.")

        provider_event_id = str(payload.get("event_id") or payload.get("payment_id") or digest)
        event_type = str(payload.get("event_type") or "unknown")
        return ProviderEvent(
            provider_event_id=provider_event_id,
            event_type=event_type,
            provider_subscription_id=payload.get("subscription_id"),
            provider_customer_id=payload.get("customer_id"),
            occurred_at=datetime.now(tz=UTC),
            normalized_status=payload.get("status"),
            payload_hash=digest,
        )

    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription:
        return ProviderSubscription(
            provider_subscription_id=subscription_id,
            provider_customer_id=f"cust_{subscription_id}",
            status="active",
        )
