"""Contract tests for console and Resend email adapters."""

from __future__ import annotations

import pytest

from src.modules.notification.infrastructure.email.console_adapter import ConsoleEmailAdapter


class TestEmailPortContract:
    @pytest.mark.asyncio
    async def test_console_adapter_uses_idempotency_key(self):
        adapter = ConsoleEmailAdapter()
        result = await adapter.send(
            recipient_address="synthetic@example.com",
            template_key="obligation.reminder.due",
            template_version="1.0.0-synthetic",
            locale="en",
            variables={"actionUrl": "https://draftly.local/synthetic"},
            idempotency_key="nd_idempotent_1",
        )
        assert result.provider_message_id.startswith("console_")
        assert adapter.sent[0]["idempotency_key"] == "nd_idempotent_1"
