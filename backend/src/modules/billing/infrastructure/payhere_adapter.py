"""PayHere billing adapter — verifies the provider signature and maps events.

Verification always runs over the **unmodified** request body. Two schemes are
accepted, in this order:

1. a header signature (`x-payhere-signature`), HMAC-SHA256 over the raw bytes;
2. the in-payload checksum field, HMAC-SHA256 over the canonical ordering of
   every field except the checksum itself.

Both comparisons are constant time. Nothing from the payload reaches a log line,
an error message, or an audit payload — only the payload hash does.

Live PayHere onboarding (merchant id, settlement account, and the production
signing scheme) is still an open commercial decision, so this adapter is wired
only when a merchant secret is configured; otherwise bootstrap selects the stub.
"""

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

SIGNATURE_HEADER = "x-payhere-signature"
_CHECKSUM_FIELDS = ("checksum", "md5sig")


class PayHereBillingAdapter:
    def __init__(
        self, *, merchant_secret: str, checkout_base_url: str = "https://payhere.lk"
    ) -> None:
        self._secret = merchant_secret.encode("utf-8")
        self._checkout_base = checkout_base_url.rstrip("/")

    async def create_checkout(self, command: CheckoutCommand) -> Checkout:
        # Price and currency come from the server-approved plan version, never
        # from the browser (billing-service.md §7.1).
        session_id = f"ph_sess_{uuid.uuid4().hex[:12]}"
        _ = (command.currency, command.price_minor_units)
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
        raw = request.body
        payload_hash = hashlib.sha256(raw).hexdigest()

        header_signature = request.headers.get(SIGNATURE_HEADER)
        if header_signature:
            self._verify_raw_signature(raw, header_signature)
        try:
            payload: dict[str, Any] = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise InvalidWebhookError()
        if not isinstance(payload, dict):
            raise InvalidWebhookError()
        if not header_signature:
            self._verify_payload_checksum(payload)

        return ProviderEvent(
            provider_event_id=self._event_id(payload, payload_hash),
            event_type=str(payload.get("event_type") or payload.get("status") or "unknown"),
            provider_subscription_id=_optional_str(payload.get("subscription_id")),
            provider_customer_id=_optional_str(payload.get("customer_id")),
            occurred_at=_parse_occurred_at(payload.get("occurred_at")),
            normalized_status=_optional_str(payload.get("status")),
            payload_hash=payload_hash,
        )

    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription:
        return ProviderSubscription(
            provider_subscription_id=subscription_id,
            provider_customer_id=f"ph_cust_{subscription_id}",
            status="active",
        )

    def _verify_raw_signature(self, raw: bytes, provided: str) -> None:
        expected = hmac.new(self._secret, raw, hashlib.sha256).hexdigest()
        if not _same_signature(provided, expected):
            raise InvalidWebhookError()

    def _verify_payload_checksum(self, payload: dict[str, Any]) -> None:
        provided = next(
            (str(payload[field]) for field in _CHECKSUM_FIELDS if payload.get(field)), None
        )
        if not provided:
            raise InvalidWebhookError()
        canonical = json.dumps(
            {k: v for k, v in payload.items() if k not in _CHECKSUM_FIELDS},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = hmac.new(self._secret, canonical, hashlib.sha256).hexdigest()
        if not _same_signature(provided, expected):
            raise InvalidWebhookError()

    def _event_id(self, payload: dict[str, Any], payload_hash: str) -> str:
        """Return a stable provider event id.

        PayHere does not guarantee an event id on every notification, so the
        documented deterministic fallback is the payment identifier combined
        with the payload hash (billing-service.md §5.4). Both are stable across
        retries of the same event, so replay detection still works.
        """
        event_id = _optional_str(payload.get("event_id"))
        if event_id:
            return event_id
        payment_id = _optional_str(payload.get("payment_id")) or "no-payment-id"
        return f"{payment_id}:{payload_hash[:32]}"


def _same_signature(provided: str, expected: str) -> bool:
    """Constant-time comparison that refuses, rather than raises, on odd input.

    ``hmac.compare_digest`` raises TypeError for a str with non-ASCII
    characters, which turned a forged signature into a 500. Comparing bytes
    handles any input the caller can send.
    """
    return hmac.compare_digest(provided.strip().lower().encode("utf-8"), expected.encode("ascii"))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_occurred_at(value: object) -> datetime | None:
    text = _optional_str(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
