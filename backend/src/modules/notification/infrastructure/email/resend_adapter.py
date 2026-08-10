"""Resend email adapter skeleton — enabled only when RESEND_API_KEY is set."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
import structlog

from src.modules.notification.domain.models import DeliveryResult

log = structlog.get_logger(__name__)


class ResendEmailAdapter:
    """Maps EmailPort to Resend POST /emails (notification-service.md §7.1)."""

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        template_resolver: object | None = None,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._template_resolver = template_resolver

    async def send(
        self,
        *,
        recipient_address: str,
        template_key: str,
        template_version: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
    ) -> DeliveryResult:
        template_id = template_key
        if self._template_resolver is not None and hasattr(self._template_resolver, "resolve"):
            template_id = self._template_resolver.resolve(template_key, locale, template_version)

        payload = {
            "from": self._from_email,
            "to": [recipient_address],
            "template": {"id": template_id, "variables": dict(variables)},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        message_id = str(data.get("id", idempotency_key))
        log.info("notification.resend.sent", provider_message_id=message_id)
        return DeliveryResult(provider_message_id=message_id)
