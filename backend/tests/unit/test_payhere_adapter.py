"""PayHere webhook verification (F12): the signature is the only credential.

POST /billing/webhooks/payhere takes no bearer token, so this adapter is the
whole defence. Every forged, tampered or malformed request must be refused
as InvalidWebhookError (a 401), never let through and never a 500.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from src.modules.billing.domain.errors import InvalidWebhookError
from src.modules.billing.infrastructure.payhere_adapter import (
    SIGNATURE_HEADER,
    PayHereBillingAdapter,
)
from src.modules.billing.ports import RawWebhook

SECRET = "synthetic-merchant-secret"
PAYLOAD: dict[str, Any] = {
    "event_id": "evt_synthetic_1",
    "event_type": "subscription.activated",
    "status": "active",
    "subscription_id": "sub_synthetic_1",
    "customer_id": "cus_synthetic_1",
    "payment_id": "pay_synthetic_1",
}


def _adapter(secret: str = SECRET) -> PayHereBillingAdapter:
    return PayHereBillingAdapter(merchant_secret=secret)


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _checksummed(payload: dict[str, Any], field: str = "checksum", secret: str = SECRET) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return json.dumps({**payload, field: _sign(canonical, secret)}).encode()


def _webhook(body: bytes, headers: dict[str, str] | None = None) -> RawWebhook:
    return RawWebhook(headers=headers or {}, body=body, provider="payhere")


async def _refused(webhook: RawWebhook) -> None:
    with pytest.raises(InvalidWebhookError) as caught:
        await _adapter().verify_webhook(webhook)
    assert caught.value.http_status == 401


# ── Header signature over the raw body ──────────────────────────────────────


async def test_a_correct_header_signature_is_accepted() -> None:
    body = json.dumps(PAYLOAD).encode()

    event = await _adapter().verify_webhook(_webhook(body, {SIGNATURE_HEADER: _sign(body)}))

    assert event.provider_event_id == "evt_synthetic_1"
    assert event.provider_subscription_id == "sub_synthetic_1"
    assert event.payload_hash == hashlib.sha256(body).hexdigest()


async def test_the_header_signature_is_case_insensitive_hex() -> None:
    body = json.dumps(PAYLOAD).encode()

    event = await _adapter().verify_webhook(
        _webhook(body, {SIGNATURE_HEADER: f" {_sign(body).upper()} "})
    )

    assert event.provider_event_id == "evt_synthetic_1"


async def test_a_signature_made_with_another_secret_is_refused() -> None:
    body = json.dumps(PAYLOAD).encode()

    await _refused(_webhook(body, {SIGNATURE_HEADER: _sign(body, "attacker-secret")}))


async def test_a_body_changed_after_signing_is_refused() -> None:
    body = json.dumps(PAYLOAD).encode()
    signature = _sign(body)
    tampered = body.replace(b"active", b"cancel")

    await _refused(_webhook(tampered, {SIGNATURE_HEADER: signature}))


async def test_a_bad_header_is_not_rescued_by_a_good_checksum() -> None:
    """A present header is authoritative; a failed one is not retried another way."""
    body = _checksummed(PAYLOAD)

    await _refused(_webhook(body, {SIGNATURE_HEADER: "0" * 64}))


@pytest.mark.parametrize(
    "signature",
    [
        pytest.param("é" * 64, id="non-ascii"),
        pytest.param("not-hex", id="short"),
        pytest.param("", id="empty-but-present"),
    ],
)
async def test_a_malformed_header_signature_is_refused_not_a_500(signature: str) -> None:
    body = json.dumps(PAYLOAD).encode()
    headers = {SIGNATURE_HEADER: signature} if signature else {SIGNATURE_HEADER: " "}

    await _refused(_webhook(body, headers))


# ── In-payload checksum ─────────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["checksum", "md5sig"])
async def test_a_correct_payload_checksum_is_accepted(field: str) -> None:
    event = await _adapter().verify_webhook(_webhook(_checksummed(PAYLOAD, field)))

    assert event.provider_event_id == "evt_synthetic_1"


async def test_a_payload_without_a_checksum_is_refused() -> None:
    await _refused(_webhook(json.dumps(PAYLOAD).encode()))


async def test_a_checksum_made_with_another_secret_is_refused() -> None:
    await _refused(_webhook(_checksummed(PAYLOAD, secret="attacker-secret")))


async def test_a_field_changed_after_the_checksum_is_refused() -> None:
    signed = json.loads(_checksummed(PAYLOAD))
    signed["status"] = "cancelled"

    await _refused(_webhook(json.dumps(signed).encode()))


async def test_a_non_ascii_checksum_is_refused_not_a_500() -> None:
    await _refused(_webhook(json.dumps({**PAYLOAD, "checksum": "é" * 64}).encode()))


# ── Malformed bodies ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"status=active&checksum=x", id="form-encoded"),
        pytest.param(b"\xff\xfe not utf-8", id="not-utf8"),
        pytest.param(b"[1, 2, 3]", id="json-list"),
        pytest.param(b"", id="empty"),
    ],
)
async def test_a_body_that_is_not_a_json_object_is_refused(body: bytes) -> None:
    """Even correctly signed: a signature proves origin, not shape."""
    await _refused(_webhook(body, {SIGNATURE_HEADER: _sign(body)}))


# ── Replay detection ────────────────────────────────────────────────────────


async def test_a_retried_event_without_an_id_keeps_the_same_event_id() -> None:
    """The replay key must be stable, or a retry would be applied twice."""
    payload = {k: v for k, v in PAYLOAD.items() if k != "event_id"}
    body = _checksummed(payload)

    first = await _adapter().verify_webhook(_webhook(body))
    again = await _adapter().verify_webhook(_webhook(body))
    other = await _adapter().verify_webhook(
        _webhook(_checksummed({**payload, "payment_id": "pay_synthetic_2"}))
    )

    assert first.provider_event_id == again.provider_event_id
    assert first.provider_event_id.startswith("pay_synthetic_1:")
    assert other.provider_event_id != first.provider_event_id
