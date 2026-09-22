"""The outbox claim protocol against real Postgres (jobs-and-workers.md §2–§4).

``FOR UPDATE SKIP LOCKED`` only engages on Postgres, so these would test
nothing on SQLite. They commit for real (``db_committing``): concurrent claims
need two connections that can both see the queued rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.platform.messaging.orm import OutboxRow
from src.platform.messaging.outbox import (
    DEFAULT_MAX_ATTEMPTS,
    STATE_CLAIMED,
    STATE_DEAD_LETTER,
    STATE_DONE,
    STATE_FAILED,
    STATE_PENDING,
    SqlOutboxRepository,
    backoff_seconds,
)

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
T0 = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


async def _enqueue(sessions: Sessions, *keys: str, available_at: datetime = T0) -> None:
    async with sessions() as session:
        outbox = SqlOutboxRepository(session)
        for key in keys:
            await outbox.enqueue_job(
                job_type="synthetic.job",
                organisation_id="usr_synthetic",
                idempotency_key=key,
                message={"key": key},
                available_at=available_at,
            )
        await session.commit()


async def _row(sessions: Sessions, key: str) -> OutboxRow:
    async with sessions() as session:
        row = (
            await session.execute(select(OutboxRow).where(OutboxRow.idempotency_key == key))
        ).scalar_one()
        return row


async def _claim_one(sessions: Sessions, key: str, *, at: datetime = T0) -> int:
    """Enqueue ``key``, claim it and commit; returns the outbox id."""
    await _enqueue(sessions, key)
    async with sessions() as session:
        claimed = await SqlOutboxRepository(session).claim_batch(worker_id="w1", now=at)
        await session.commit()
    (message,) = claimed
    return message.id


# ── Enqueue ─────────────────────────────────────────────────────────────────


async def test_enqueueing_the_same_key_twice_keeps_one_row(db_committing: Sessions) -> None:
    async with db_committing() as session:
        outbox = SqlOutboxRepository(session)
        first = await outbox.enqueue_job(
            job_type="synthetic.job",
            organisation_id="usr_synthetic",
            idempotency_key="k1",
            message={},
        )
        second = await outbox.enqueue_job(
            job_type="synthetic.job",
            organisation_id="usr_synthetic",
            idempotency_key="k1",
            message={"changed": True},
        )
        await session.commit()

    async with db_committing() as session:
        rows = (await session.execute(select(OutboxRow))).scalars().all()
    assert (first, second) == (True, False)
    assert len(rows) == 1
    assert rows[0].payload == {}


# ── Claim ───────────────────────────────────────────────────────────────────


async def test_a_claim_takes_available_rows_oldest_first(db_committing: Sessions) -> None:
    await _enqueue(db_committing, "later", available_at=T0 + timedelta(seconds=1))
    await _enqueue(db_committing, "earlier", available_at=T0)

    async with db_committing() as session:
        claimed = await SqlOutboxRepository(session).claim_batch(
            worker_id="w1", now=T0 + timedelta(seconds=5)
        )
        await session.commit()

    assert [m.idempotency_key for m in claimed] == ["earlier", "later"]
    assert all(m.attempts == 1 for m in claimed)
    row = await _row(db_committing, "earlier")
    assert (row.state, row.claimed_by, row.claimed_at) == (
        STATE_CLAIMED,
        "w1",
        T0 + timedelta(seconds=5),
    )


async def test_a_row_not_yet_available_is_not_claimed(db_committing: Sessions) -> None:
    await _enqueue(db_committing, "future", available_at=T0 + timedelta(minutes=5))

    async with db_committing() as session:
        claimed = await SqlOutboxRepository(session).claim_batch(worker_id="w1", now=T0)
        await session.commit()

    assert claimed == []


async def test_two_concurrent_claims_take_disjoint_rows(db_committing: Sessions) -> None:
    """SKIP LOCKED: the second worker skips what the first holds, it does not wait."""
    await _enqueue(db_committing, *(f"job{n}" for n in range(6)))

    async with db_committing() as first, db_committing() as second:
        mine = await SqlOutboxRepository(first).claim_batch(worker_id="w1", batch=3, now=T0)
        # The first transaction is still open, so its rows are still locked.
        # Without SKIP LOCKED the second claim would wait on them forever; the
        # lock timeout turns that into a failure instead of a hung test.
        await second.execute(text("SET LOCAL lock_timeout = '2s'"))
        theirs = await SqlOutboxRepository(second).claim_batch(worker_id="w2", batch=10, now=T0)
        await first.commit()
        await second.commit()

    mine_ids = {m.id for m in mine}
    theirs_ids = {m.id for m in theirs}
    assert len(mine_ids) == 3
    assert len(theirs_ids) == 3
    assert mine_ids.isdisjoint(theirs_ids)


async def test_a_claimed_row_is_not_claimed_again(db_committing: Sessions) -> None:
    await _claim_one(db_committing, "k1")

    async with db_committing() as session:
        again = await SqlOutboxRepository(session).claim_batch(
            worker_id="w2", now=T0 + timedelta(minutes=1)
        )
        await session.commit()

    assert again == []


# ── Lease ───────────────────────────────────────────────────────────────────


async def test_an_expired_lease_returns_the_row_to_pending(db_committing: Sessions) -> None:
    await _claim_one(db_committing, "k1", at=T0)
    reap_at = T0 + timedelta(seconds=121)

    async with db_committing() as session:
        reaped = await SqlOutboxRepository(session).reap_leases(lease_seconds=120, now=reap_at)
        await session.commit()

    row = await _row(db_committing, "k1")
    assert reaped == 1
    assert (row.state, row.claimed_by, row.claimed_at, row.available_at) == (
        STATE_PENDING,
        None,
        None,
        reap_at,
    )
    assert row.attempts == 1


async def test_a_live_lease_is_left_alone(db_committing: Sessions) -> None:
    await _claim_one(db_committing, "k1", at=T0)

    async with db_committing() as session:
        reaped = await SqlOutboxRepository(session).reap_leases(
            lease_seconds=120, now=T0 + timedelta(seconds=119)
        )
        await session.commit()

    assert reaped == 0
    assert (await _row(db_committing, "k1")).state == STATE_CLAIMED


# ── Outcomes ────────────────────────────────────────────────────────────────


async def test_a_retry_backs_off_and_releases_the_claim(db_committing: Sessions) -> None:
    message_id = await _claim_one(db_committing, "k1")

    async with db_committing() as session:
        state = await SqlOutboxRepository(session).mark_retry(
            message_id, failure_code="handler_retry", now=T0, jitter=0
        )
        await session.commit()

    row = await _row(db_committing, "k1")
    assert state == STATE_PENDING
    assert row.available_at == T0 + timedelta(seconds=backoff_seconds(1, jitter=0))
    assert (row.claimed_by, row.claimed_at, row.last_error) == (None, None, "handler_retry")


async def test_retries_dead_letter_once_attempts_are_exhausted(db_committing: Sessions) -> None:
    await _enqueue(db_committing, "k1")
    moment = T0
    for attempt in range(1, DEFAULT_MAX_ATTEMPTS + 1):
        async with db_committing() as session:
            outbox = SqlOutboxRepository(session)
            (message,) = await outbox.claim_batch(worker_id="w1", now=moment)
            state = await outbox.mark_retry(
                message.id, failure_code="handler_retry", now=moment, jitter=0
            )
            await session.commit()
        assert message.attempts == attempt
        moment += timedelta(hours=1)

    row = await _row(db_committing, "k1")
    assert state == STATE_DEAD_LETTER
    assert (row.state, row.attempts) == (STATE_DEAD_LETTER, DEFAULT_MAX_ATTEMPTS)


@pytest.mark.parametrize(
    ("mark", "final_state"),
    [
        ("mark_done", STATE_DONE),
        ("mark_failed", STATE_FAILED),
        ("mark_dead_letter", STATE_DEAD_LETTER),
    ],
)
async def test_a_terminal_outcome_is_never_claimed_again(
    db_committing: Sessions, mark: str, final_state: str
) -> None:
    message_id = await _claim_one(db_committing, "k1")

    async with db_committing() as session:
        outbox = SqlOutboxRepository(session)
        if mark == "mark_done":
            await outbox.mark_done(message_id)
        else:
            await getattr(outbox, mark)(message_id, failure_code="synthetic")
        await session.commit()

    async with db_committing() as session:
        outbox = SqlOutboxRepository(session)
        reaped = await outbox.reap_leases(lease_seconds=0, now=T0 + timedelta(days=1))
        again = await outbox.claim_batch(worker_id="w2", now=T0 + timedelta(days=1))
        await session.commit()

    assert (await _row(db_committing, "k1")).state == final_state
    assert (reaped, again) == (0, [])
