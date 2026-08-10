"""Worker runner — `python -m src.workers.runner` (jobs-and-workers.md §1).

One claim per batch, one transaction per message: the handler's effect and the
outbox state change commit together, so a crash costs one lease interval rather
than a lost or duplicated effect.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import structlog

from src.platform.db.session import get_session_maker
from src.platform.messaging.dispatcher import MessageDispatcher, MessageResult
from src.platform.messaging.outbox import ClaimedMessage, SqlOutboxRepository
from src.platform.observability.logging import configure_logging

log = structlog.get_logger(__name__)

DEFAULT_BATCH = 10
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_LEASE_SECONDS = 120


async def process_message(
    dispatcher: MessageDispatcher, message: ClaimedMessage, *, worker_id: str
) -> MessageResult:
    """Run one claimed message in its own transaction."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        outbox = SqlOutboxRepository(session)
        try:
            result = await dispatcher.dispatch(session, message)
        except Exception as exc:  # noqa: BLE001 - a handler crash must not kill the worker
            await session.rollback()
            log.warning(
                "worker.handler_error",
                name=message.name,
                outbox_id=message.id,
                error=type(exc).__name__,
            )
            async with session_maker() as retry_session:
                await SqlOutboxRepository(retry_session).mark_retry(
                    message.id, failure_code="handler_error"
                )
                await retry_session.commit()
            return MessageResult.RETRY

        if result is MessageResult.DONE:
            await outbox.mark_done(message.id)
        elif result is MessageResult.RETRY:
            await outbox.mark_retry(message.id, failure_code="handler_retry")
        elif result is MessageResult.FAILED:
            await outbox.mark_failed(message.id, failure_code="handler_permanent_failure")
        else:
            await outbox.mark_dead_letter(message.id, failure_code="handler_dead_letter")
        await session.commit()
        log.info("worker.message_processed", name=message.name, result=result.value)
        return result


async def run_once(
    dispatcher: MessageDispatcher, *, worker_id: str, batch: int = DEFAULT_BATCH
) -> int:
    """Claim and process one batch. Returns the number of messages handled."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        outbox = SqlOutboxRepository(session)
        await outbox.reap_leases(lease_seconds=DEFAULT_LEASE_SECONDS)
        claimed = list(await outbox.claim_batch(worker_id=worker_id, batch=batch))
        await session.commit()

    for message in claimed:
        await process_message(dispatcher, message, worker_id=worker_id)
    return len(claimed)


async def run_forever(poll_seconds: float = DEFAULT_POLL_SECONDS) -> None:  # pragma: no cover
    from src.bootstrap import build_dispatcher

    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    dispatcher = build_dispatcher()
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    log.info("worker.started", worker_id=worker_id, handlers=len(dispatcher.registered()))
    while True:
        handled = await run_once(dispatcher, worker_id=worker_id)
        if handled == 0:
            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_forever())
