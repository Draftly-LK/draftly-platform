"""Console email adapter — records synthetic deliveries without external network."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

import structlog

from src.modules.notification.domain.models import DeliveryResult

log = structlog.get_logger(__name__)


class ConsoleEmailAdapter:
    """Default V0 adapter for local development and automated tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(
        self,
        *,
        recipient_address: str,
        template_key: str,
        template_version: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
        subject: str = "",
        body: str = "",
        provider_template_id: str | None = None,
    ) -> DeliveryResult:
        provider_id = f"console_{uuid.uuid4().hex}"
        self.sent.append(
            {
                "recipient": recipient_address,
                "template_key": template_key,
                "template_version": template_version,
                "locale": locale,
                "idempotency_key": idempotency_key,
                "subject": subject,
            }
        )
        log.info(
            "notification.console_email",
            template_key=template_key,
            locale=locale,
            idempotency_key=idempotency_key,
        )
        _ = variables, body, provider_template_id
        return DeliveryResult(provider_message_id=provider_id)
