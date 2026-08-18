"""Message dispatch for the worker runtime (jobs-and-workers.md §3–§5).

The dispatcher knows nothing about any service: modules register a handler for
an event name or a job type, and the handler decides the outcome. Unregistered
messages are a permanent failure rather than an endless retry.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.messaging.outbox import KIND_EVENT, KIND_JOB, ClaimedMessage

log = structlog.get_logger(__name__)


class MessageResult(str, Enum):
    DONE = "done"
    RETRY = "retry"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


Handler = Callable[[AsyncSession, ClaimedMessage], Awaitable[MessageResult]]


class MessageDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], Handler] = {}

    def register_job(self, job_type: str, handler: Handler) -> None:
        self._handlers[(KIND_JOB, job_type)] = handler

    def register_event(self, event_name: str, handler: Handler) -> None:
        self._handlers[(KIND_EVENT, event_name)] = handler

    def registered(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._handlers))

    async def dispatch(self, session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        handler = self._handlers.get((message.kind, message.name))
        if handler is None:
            if message.kind == KIND_EVENT:
                # An event with no subscriber is allowed (events.md §5).
                return MessageResult.DONE
            log.warning("worker.no_handler", name=message.name, outbox_id=message.id)
            return MessageResult.FAILED
        return await handler(session, message)


__all__ = ["Handler", "MessageDispatcher", "MessageResult"]
