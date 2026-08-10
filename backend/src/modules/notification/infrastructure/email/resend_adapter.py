"""Resend email adapter — httpx only, no provider SDK (notification-service.md §7.1)."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
import structlog

from src.modules.notification.domain.errors import (
    EmailSendingDisabledError,
    PermanentDeliveryFailure,
    RetryableDeliveryFailure,
)
from src.modules.notification.domain.models import DeliveryResult

log = structlog.get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _recipient_domain(address: str) -> str:
    _, _, domain = address.partition("@")
    return domain.lower()


class ResendEmailAdapter:
    """Maps EmailPort to Resend POST /emails."""

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        outbound_enabled: bool,
        allowed_recipient_domains: frozenset[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._outbound_enabled = outbound_enabled
        self._allowed_domains = allowed_recipient_domains or frozenset()

    def _assert_recipient_allowed(self, recipient_address: str) -> None:
        if not self._allowed_domains:
            return
        domain = _recipient_domain(recipient_address)
        if domain not in self._allowed_domains:
            raise PermanentDeliveryFailure("recipient_address_suppressed")

    async def send(
        self,
        *,
        recipient_address: str,
        template_key: str,
        template_version: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
        subject: str,
        body: str,
        provider_template_id: str | None = None,
    ) -> DeliveryResult:
        if not self._outbound_enabled:
            raise EmailSendingDisabledError()
        self._assert_recipient_allowed(recipient_address)

        if provider_template_id:
            payload: dict[str, object] = {
                "from": self._from_email,
                "to": [recipient_address],
                "template": {"id": provider_template_id, "variables": dict(variables)},
            }
        else:
            payload = {
                "from": self._from_email,
                "to": [recipient_address],
                "subject": subject,
                "text": body,
            }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }
        _ = template_key, template_version, locale

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(RESEND_API_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise RetryableDeliveryFailure("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise RetryableDeliveryFailure("transient_error") from exc

        if response.status_code == 429:
            raise RetryableDeliveryFailure("provider_rate_limited")
        if response.status_code >= 500:
            raise RetryableDeliveryFailure("provider_server_error")
        if response.status_code >= 400:
            raise PermanentDeliveryFailure("provider_rejected_request")

        data = response.json()
        message_id = str(data.get("id", idempotency_key))
        log.info("notification.resend.sent", provider_message_id=message_id)
        return DeliveryResult(provider_message_id=message_id)
