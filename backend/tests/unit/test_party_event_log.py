"""The party event adapter publishes through the real structlog logger.

The party suites use an in-memory event double, so this adapter's own logging
call never ran under test until the seed script reached it.
"""

from __future__ import annotations

import pytest
import structlog

from src.modules.party.infrastructure.event_log import LoggingEventAdapter
from src.modules.party.ports import DomainEvent
from src.platform.privacy import PrivateContentLeakError
from tests.factories.constants import USER_A


def _event() -> DomainEvent:
    return DomainEvent(
        name="party.created",
        user_id=USER_A,
        aggregate_type="party",
        aggregate_id="pty_synthetic",
        payload={"partyId": "pty_synthetic", "partyKind": "natural-person"},
        correlation_id="corr_synthetic",
    )


async def test_publish_logs_the_event_name_without_clashing_with_structlog() -> None:
    adapter = LoggingEventAdapter()

    with structlog.testing.capture_logs() as logs:
        await adapter.publish(_event())

    assert adapter.published == [_event()]
    assert logs == [
        {
            "event": "domain_event_published",
            "event_name": "party.created",
            "aggregate_type": "party",
            "aggregate_id": "pty_synthetic",
            "correlation_id": "corr_synthetic",
            "log_level": "info",
        }
    ]


async def test_publish_refuses_a_payload_carrying_private_content() -> None:
    adapter = LoggingEventAdapter()
    leaking = DomainEvent(
        name="party.created",
        user_id=USER_A,
        aggregate_type="party",
        aggregate_id="pty_synthetic",
        payload={"displayName": "N. M. Silva (synthetic)"},
    )

    with pytest.raises(PrivateContentLeakError, match="displayName: denied key"):
        await adapter.publish(leaking)

    assert adapter.published == []
