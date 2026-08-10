"""PayHere billing adapter skeleton — verifies checksum and maps events."""

from __future__ import annotations

import hashlib
import hmac
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


class PayHereBillingAdapter:
    """Thin PayHere adapter; production checkout URLs are configured separately."""

    def __init__(self, *, merchant_secret: str, checkout_base_url: str = "https://payhere.lk") -> None:
        self._secret = merchant_secret
        self._checkout_base = checkout_base_url.rstrip("/")

    async def create_checkout(self, command: CheckoutCommand) -> Checkout:
        session_id = f"ph_sess_{uuid.uuid4().hex[:12]}"
        return Checkout(
            checkout_url=f"{self._checkout_base}/pay/{session_id}",
            provider_session_id=session_id,
        )

    async def create_customer_portal(self, customer_id: str) -> Portal:
        return Portal(portal_url=f"{self._checkout_base}/customer/{customer_id}")

    async def cancel_subscription(self, subscription_id: str) -> None:
        _ = subscription_id

    async def reactivate_subscription(self, subscription_id: str) -> None:
        _ = subscription_id

    async def verify_webhook(self, request: RawWebhook) -> ProviderEvent:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InvalidWebhookError("Invalid webhook payload.")

        checksum = payload.get("checksum") or payload.get("md5sig")
        if not checksum:
            raise InvalidWebhookError("Missing checksum.")

        canonical = json.dumps(
            {k: v for k, v in payload.items() if k not in {"checksum", "md5sig"}},
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = hmac.new(
            self._secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if checksum != expected:
            raise InvalidWebhookError("Checksum mismatch.")

        provider_event_id = str(
            payload.get("event_id") or payload.get("payment_id") or expected
        )
        event_type = str(payload.get("event_type") or payload.get("status") or "unknown")
        return ProviderEvent(
            provider_event_id=provider_event_id,
            event_type=event_type,
            provider_subscription_id=payload.get("subscription_id"),
            provider_customer_id=payload.get("customer_id"),
            occurred_at=datetime.now(tz=UTC),
            normalized_status=payload.get("status"),
            payload_hash=expected,
        )

    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription:
        return ProviderSubscription(
            provider_subscription_id=subscription_id,
            provider_customer_id=f"ph_cust_{subscription_id}",
            status="active",
        )
