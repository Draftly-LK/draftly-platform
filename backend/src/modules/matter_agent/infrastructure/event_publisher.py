"""Publishes the registered ``agent.*`` events through the existing outbox.

Every event is written in the caller's transaction, so a mutation and its event
commit together and a rollback leaves neither (``jobs-and-workers.md`` §2).

Payloads carry identifiers, counts and closed enums only. No message text, no
tool arguments, no prompt content — a consumer that needs the wording re-reads
it from Neon by id (``events.md`` §2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.platform import ids
from src.platform.messaging.envelope import EventEnvelope
from src.platform.messaging.outbox import SqlOutboxRepository

#: Every name here is registered in `events.md` §5.13. Publishing an
#: unregistered name is rejected by the envelope validator, which is what stops
#: a service quietly inventing an event.
SESSION_CREATED = "agent.session-created"
MESSAGE_APPENDED = "agent.message-appended"
TURN_COMPLETED = "agent.turn-completed"
TURN_FAILED = "agent.turn-failed"
TOOL_EXECUTED = "agent.tool-executed"
TOOL_DENIED = "agent.tool-denied"
ACTION_PROPOSED = "agent.action-proposed"
ACTION_CONFIRMED = "agent.action-confirmed"
ACTION_REJECTED = "agent.action-rejected"
SUGGESTION_CREATED = "agent.suggestion-created"


class AgentEventPublisher:
    """Writes ``agent.*`` envelopes to the outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self._outbox = SqlOutboxRepository(session)

    async def publish(
        self,
        event_name: str,
        *,
        user_id: str,
        matter_id: str | None,
        actor_id: str | None,
        correlation_id: str,
        idempotency_key: str,
        data: dict[str, Any],
    ) -> bool:
        """Publish one event. Returns False when the key was already used.

        The idempotency key is derived from the aggregate and its version by
        the caller, so a redelivered turn produces one event rather than two.
        """
        envelope = EventEnvelope(
            event_id=ids.new_id("evt"),
            event_name=event_name,
            event_version=1,
            occurred_at=datetime.now(tz=UTC),
            # V0 has no organisation aggregate; the tenant column carries the
            # owning user id, as billing_service already does
            # (`security-model.md` §2.1).
            organisation_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            data=data,
        )
        return await self._outbox.publish_event(envelope)


class NullAgentEventPublisher:
    """No-op publisher for unit tests that are not about events."""

    async def publish(
        self,
        event_name: str,
        *,
        user_id: str,
        matter_id: str | None,
        actor_id: str | None,
        correlation_id: str,
        idempotency_key: str,
        data: dict[str, Any],
    ) -> bool:
        return True
