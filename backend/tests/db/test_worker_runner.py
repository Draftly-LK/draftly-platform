"""The worker runner against real Postgres (jobs-and-workers.md §3–§5, F2).

One claim per batch, one transaction per message: a handler's effect and the
outbox state change commit together, and a handler that raises leaves neither
behind except the retry. These run the real ``process_message`` and
``run_once`` with the app's session factory pointed at the test schema.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import src.platform.db.session as session_module
from src.platform.messaging.dispatcher import MessageDispatcher, MessageResult
from src.platform.messaging.orm import OutboxRow
from src.platform.messaging.outbox import (
    KIND_EVENT,
    STATE_CLAIMED,
    STATE_DEAD_LETTER,
    STATE_DONE,
    STATE_FAILED,
    STATE_PENDING,
    ClaimedMessage,
    SqlOutboxRepository,
)
from src.workers.runner import process_message, run_once

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
Handler = Callable[[AsyncSession, ClaimedMessage], Awaitable[MessageResult]]
JOB = "synthetic.job"


@pytest.fixture
def sessions(db_committing: Sessions, monkeypatch: pytest.MonkeyPatch) -> Sessions:
    """The runner opens its own sessions; point them at the test schema."""
    monkeypatch.setattr(session_module, "_session_maker", db_committing)
    return db_committing


async def _enqueue(sessions: Sessions, key: str, *, name: str = JOB) -> None:
    async with sessions() as session:
        await SqlOutboxRepository(session).enqueue_job(
            job_type=name,
            organisation_id="usr_synthetic",
            idempotency_key=key,
            message={"key": key},
            available_at=datetime.now(tz=UTC) - timedelta(seconds=1),
        )
        await session.commit()


async def _claim(sessions: Sessions, key: str, *, name: str = JOB) -> ClaimedMessage:
    await _enqueue(sessions, key, name=name)
    async with sessions() as session:
        (message,) = await SqlOutboxRepository(session).claim_batch(worker_id="w1")
        await session.commit()
    return message


async def _row(sessions: Sessions, key: str) -> OutboxRow | None:
    async with sessions() as session:
        return (
            await session.execute(select(OutboxRow).where(OutboxRow.idempotency_key == key))
        ).scalar_one_or_none()


def _dispatcher(handler: Handler, name: str = JOB) -> MessageDispatcher:
    dispatcher = MessageDispatcher()
    dispatcher.register_job(name, handler)
    return dispatcher


def _writes_a_side_effect_then(result: MessageResult | Exception) -> Handler:
    """A handler whose effect is a row the test can look for afterwards."""

    async def handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        await SqlOutboxRepository(session).enqueue_job(
            job_type="synthetic.effect",
            organisation_id="usr_synthetic",
            idempotency_key=f"effect-of-{message.idempotency_key}",
            message={},
        )
        if isinstance(result, Exception):
            raise result
        return result

    return handler


# ── One message, one transaction ────────────────────────────────────────────


async def test_a_done_handler_commits_its_effect_with_the_outbox_state(
    sessions: Sessions,
) -> None:
    message = await _claim(sessions, "k1")

    result = await process_message(
        _dispatcher(_writes_a_side_effect_then(MessageResult.DONE)), message, worker_id="w1"
    )

    assert result is MessageResult.DONE
    assert (await _row(sessions, "k1")).state == STATE_DONE  # type: ignore[union-attr]
    assert await _row(sessions, "effect-of-k1") is not None


async def test_a_handler_that_raises_leaves_no_effect_and_is_retried(
    sessions: Sessions,
) -> None:
    """The two-session path: roll back the handler, record the retry apart."""
    message = await _claim(sessions, "k1")

    result = await process_message(
        _dispatcher(_writes_a_side_effect_then(RuntimeError("synthetic crash"))),
        message,
        worker_id="w1",
    )

    row = await _row(sessions, "k1")
    assert result is MessageResult.RETRY
    assert row is not None
    assert (row.state, row.last_error, row.attempts) == (STATE_PENDING, "handler_error", 1)
    assert await _row(sessions, "effect-of-k1") is None


@pytest.mark.parametrize(
    ("result", "state", "failure_code"),
    [
        (MessageResult.RETRY, STATE_PENDING, "handler_retry"),
        (MessageResult.FAILED, STATE_FAILED, "handler_permanent_failure"),
        (MessageResult.DEAD_LETTER, STATE_DEAD_LETTER, "handler_dead_letter"),
    ],
)
async def test_each_handler_outcome_sets_its_outbox_state(
    sessions: Sessions, result: MessageResult, state: str, failure_code: str
) -> None:
    message = await _claim(sessions, "k1")

    returned = await process_message(
        _dispatcher(_writes_a_side_effect_then(result)), message, worker_id="w1"
    )

    row = await _row(sessions, "k1")
    assert returned is result
    assert row is not None
    assert (row.state, row.last_error) == (state, failure_code)


async def test_a_job_with_no_handler_fails_rather_than_retrying_forever(
    sessions: Sessions,
) -> None:
    message = await _claim(sessions, "k1", name="synthetic.unregistered")

    result = await process_message(MessageDispatcher(), message, worker_id="w1")

    assert result is MessageResult.FAILED
    assert (await _row(sessions, "k1")).state == STATE_FAILED  # type: ignore[union-attr]


async def test_an_event_with_no_subscriber_is_done(sessions: Sessions) -> None:
    async with sessions() as session:
        session.add(
            OutboxRow(
                organisation_id="usr_synthetic",
                kind=KIND_EVENT,
                name="synthetic.happened",
                payload={},
                idempotency_key="k1",
                available_at=datetime.now(tz=UTC) - timedelta(seconds=1),
                state=STATE_PENDING,
                attempts=0,
            )
        )
        await session.commit()

    handled = await run_once(MessageDispatcher(), worker_id="w1")

    assert handled == 1
    assert (await _row(sessions, "k1")).state == STATE_DONE  # type: ignore[union-attr]


# ── The polling pass ────────────────────────────────────────────────────────


async def test_an_empty_queue_is_a_quiet_pass(sessions: Sessions) -> None:
    assert await run_once(MessageDispatcher(), worker_id="w1") == 0


async def test_a_pass_reaps_an_expired_lease_before_claiming(sessions: Sessions) -> None:
    """A crashed worker costs one lease interval, not a lost job."""
    await _claim(sessions, "k1")
    await _age_claim(sessions, "k1", seconds=3600)
    seen: list[int] = []

    async def handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        seen.append(message.attempts)
        return MessageResult.DONE

    handled = await run_once(_dispatcher(handler), worker_id="w2")

    assert handled == 1
    assert seen == [2]
    assert (await _row(sessions, "k1")).state == STATE_DONE  # type: ignore[union-attr]


async def _age_claim(sessions: Sessions, key: str, *, seconds: int) -> None:
    async with sessions() as session:
        await session.execute(
            update(OutboxRow)
            .where(OutboxRow.idempotency_key == key)
            .values(claimed_at=datetime.now(tz=UTC) - timedelta(seconds=seconds))
        )
        await session.commit()


# ── Per-type leases (jobs-and-workers.md §5) ────────────────────────────────


@pytest.mark.parametrize(
    ("job_type", "lease", "running_for"),
    [
        ("agent.run-turn", 180, 150),
        ("document.process", 900, 600),
        ("corpus.rebuild-index", 3600, 1800),
    ],
)
async def test_a_long_lease_job_is_not_reaped_while_running(
    sessions: Sessions, job_type: str, lease: int, running_for: int
) -> None:
    """A job still inside its own lease must not be handed to a second worker.

    An agent turn may take its whole 120 s budget; reaping it at a flat 120 s
    would run the turn twice and answer the user twice.
    """
    await _claim(sessions, "k1", name=job_type)
    await _age_claim(sessions, "k1", seconds=running_for)

    handled = await run_once(MessageDispatcher(), worker_id="w2")

    assert running_for < lease
    assert handled == 0
    assert (await _row(sessions, "k1")).state == STATE_CLAIMED  # type: ignore[union-attr]


async def test_a_short_lease_job_is_reaped_once_its_lease_passes(sessions: Sessions) -> None:
    await _claim(sessions, "k1", name="notification.deliver")
    await _age_claim(sessions, "k1", seconds=150)

    handled = await run_once(MessageDispatcher(), worker_id="w2")

    assert handled == 1
