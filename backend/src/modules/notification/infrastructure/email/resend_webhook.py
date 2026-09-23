"""Resend webhook signature verification (Svix, notification-service.md §9.1)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any

from src.modules.notification.domain.errors import WebhookVerificationError


class ResendWebhookVerifier:
    """Verify Svix-signed Resend delivery webhooks."""

    def __init__(self, webhook_secret: str, *, tolerance_seconds: int = 300) -> None:
        if not webhook_secret.startswith("whsec_"):
            raise ValueError("RESEND_WEBHOOK_SECRET must start with whsec_")
        self._secret = base64.b64decode(webhook_secret.split("_", 1)[1])
        self._tolerance = tolerance_seconds

    def verify(self, *, headers: Mapping[str, str], raw_body: bytes) -> dict[str, Any]:
        normalized = {key.lower(): value for key, value in headers.items()}
        msg_id = normalized.get("svix-id")
        timestamp = normalized.get("svix-timestamp")
        signature_header = normalized.get("svix-signature")
        if not msg_id or not timestamp or not signature_header:
            raise WebhookVerificationError()

        try:
            ts_int = int(timestamp)
        except ValueError as exc:
            raise WebhookVerificationError() from exc
        if abs(time.time() - ts_int) > self._tolerance:
            raise WebhookVerificationError()

        # Signed over the raw bytes, and decoded only once verified: decoding
        # first let a non-UTF-8 body raise before the signature was checked.
        signed_content = f"{msg_id}.{timestamp}.".encode() + raw_body
        expected = hmac.new(self._secret, signed_content, hashlib.sha256).digest()

        for part in signature_header.split():
            if not part.startswith("v1,"):
                continue
            try:
                supplied = base64.b64decode(part[3:])
            except (ValueError, binascii.Error):
                continue
            if hmac.compare_digest(expected, supplied):
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise WebhookVerificationError() from exc
                if not isinstance(payload, dict):
                    raise WebhookVerificationError()
                return payload

        raise WebhookVerificationError()
