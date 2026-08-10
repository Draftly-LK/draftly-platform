"""Local `EventPort` adapter — structured log, no broker yet.

The transport is a platform decision that is still open, so this adapter only
records that an event was published. It re-checks the privacy denylist before
emitting, because an event payload is the easiest place for a name or an
identifier to escape the protected identity tier (events.md §2).
"""

from __future__ import annotations

import structlog

from src.modules.party.ports import DomainEvent
from src.platform.privacy import assert_no_private_content

log = structlog.get_logger(__name__)


class LoggingEventAdapter:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        assert_no_private_content(event.payload, context=f"event:{event.name}")
        self.published.append(event)
        log.info(
            "domain_event_published",
            event=event.name,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            correlation_id=event.correlation_id,
        )
