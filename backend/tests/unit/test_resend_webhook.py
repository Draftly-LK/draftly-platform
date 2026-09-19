"""Resend (Svix) webhook verification refuses odd input instead of crashing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from src.modules.notification.domain.errors import WebhookVerificationError
from src.modules.notification.infrastructure.email.resend_webhook import ResendWebhookVerifier

SECRET = b"synthetic-webhook-secret"
VERIFIER = ResendWebhookVerifier(
    "whsec_" + base64.b64encode(SECRET).decode(), tolerance_seconds=600
)


def _headers(body: bytes, msg_id: str = "msg_synthetic") -> dict[str, str]:
    timestamp = str(int(time.time()))
    digest = hmac.new(SECRET, f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return {
        "svix-id": msg_id,
        "svix-timestamp": timestamp,
        "svix-signature": "v1," + base64.b64encode(digest).decode(),
    }


def test_a_correctly_signed_event_is_accepted() -> None:
    body = json.dumps({"type": "email.delivered", "data": {"email_id": "synthetic"}}).encode()

    assert VERIFIER.verify(headers=_headers(body), raw_body=body)["type"] == "email.delivered"


def test_a_signed_body_with_non_ascii_text_is_accepted() -> None:
    body = json.dumps({"type": "email.bounced", "note": "ශ්‍රී ලංකාව (synthetic)"}).encode()

    assert VERIFIER.verify(headers=_headers(body), raw_body=body)["type"] == "email.bounced"


@pytest.mark.parametrize(
    "body",
    [pytest.param(b"\xff\xfe not utf-8", id="not-utf8"), pytest.param(b"[1, 2]", id="json-list")],
)
def test_an_unusable_body_is_refused_not_a_500(body: bytes) -> None:
    """Refused whether or not it is signed: odd bytes must not raise past the guard."""
    unsigned = {**_headers(b"other"), "svix-signature": "v1,AAAA"}

    for headers in (unsigned, _headers(body)):
        with pytest.raises(WebhookVerificationError):
            VERIFIER.verify(headers=headers, raw_body=body)
