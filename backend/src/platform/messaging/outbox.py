"""SQL transactional outbox: enqueue, claim, retry, dead-letter.

One implementation for every service (jobs-and-workers.md §2–§4). Writes happen
in the caller's transaction; nothing here commits.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.messaging.envelope import EventEnvelope
from src.platform.messaging.events import EventEnvelope as BillingEventEnvelope
from src.platform.messaging.orm import OutboxRow

log = structlog.get_logger(__name__)

BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 30 * 60
JITTER_FRACTION = 0.2
DEFAULT_MAX_ATTEMPTS = 8

KIND_EVENT = "event"
KIND_JOB = "job"

STATE_PENDING = "pending"
STATE_CLAIMED = "claimed"
STATE_DONE = "done"
STATE_FAILED = "failed"
STATE_DEAD_LETTER = "dead_letter"


def backoff_seconds(attempts: int, *, jitter: float | None = None) -> float:
    """backoff(n) = min(2^n x 5s, 30min) with +/-20% jitter (jobs-and-workers.md §4)."""
    exponent = max(attempts, 0)
    base = min(float(BASE_BACKOFF_SECONDS * (2**exponent)), float(MAX_BACKOFF_SECONDS))
    factor = jitter if jitter is not None else random.uniform(-JITTER_FRACTION, JITTER_FRACTION)  # noqa: S311
    return base * (1.0 + max(-JITTER_FRACTION, min(JITTER_FRACTION, factor)))


@dataclass(frozen=True)
class ClaimedMessage:
    """A claimed outbox row handed to a worker."""

    id: int
    organisation_id: str
    kind: str
    name: str
    payload: dict[str, Any]
    idempotency_key: str
    attempts: int


class SqlOutboxRepository:
    """Outbox writes and claims over the request or worker session."""

    def __init__(self, session: AsyncSession, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> None:
        self._session = session
        self._max_attempts = max_attempts

    async def publish_event(self, envelope: EventEnvelope) -> bool:
        return await self._insert(
            organisation_id=envelope.organisation_id,
            kind=KIND_EVENT,
            name=envelope.event_name,
            payload=envelope.to_payload(),
            idempotency_key=envelope.idempotency_key,
            available_at=None,
        )

    async def enqueue_job(
        self,
        *,
        job_type: str,
        organisation_id: str,
        idempotency_key: str,
        message: Mapping[str, Any],
        available_at: datetime | None = None,
    ) -> bool:
        return await self._insert(
            organisation_id=organisation_id,
            kind=KIND_JOB,
            name=job_type,
            payload=dict(message),
            idempotency_key=idempotency_key,
            available_at=available_at,
        )

    async def _insert(
        self,
        *,
        organisation_id: str,
        kind: str,
        name: str,
        payload: dict[str, Any],
        idempotency_key: str,
        available_at: datetime | None,
    ) -> bool:
        existing = await self._session.execute(
            select(OutboxRow.id).where(
                OutboxRow.kind == kind,
                OutboxRow.name == name,
                OutboxRow.idempotency_key == idempotency_key,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False

        row = OutboxRow(
            organisation_id=organisation_id,
            kind=kind,
            name=name,
            payload=payload,
            idempotency_key=idempotency_key,
            available_at=available_at or datetime.now(tz=UTC),
            state=STATE_PENDING,
            attempts=0,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            # Concurrent producer won the unique key; one row is the intended outcome.
            return False
        return True

    async def claim_batch(
        self, *, worker_id: str, batch: int = 10, now: datetime | None = None
    ) -> Sequence[ClaimedMessage]:
        moment = now or datetime.now(tz=UTC)
        stmt = (
            select(OutboxRow)
            .where(OutboxRow.state == STATE_PENDING, OutboxRow.available_at <= moment)
            .order_by(OutboxRow.available_at, OutboxRow.id)
            .limit(batch)
        )
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        claimed: list[ClaimedMessage] = []
        for row in rows:
            row.state = STATE_CLAIMED
            row.claimed_at = moment
            row.claimed_by = worker_id
            row.attempts += 1
            claimed.append(
                ClaimedMessage(
                    id=row.id,
                    organisation_id=row.organisation_id,
                    kind=row.kind,
                    name=row.name,
                    payload=dict(row.payload),
                    idempotency_key=row.idempotency_key,
                    attempts=row.attempts,
                )
            )
        await self._session.flush()
        return claimed

    async def mark_done(self, message_id: int) -> None:
        row = await self._require(message_id)
        row.state = STATE_DONE
        row.last_error = None
        await self._session.flush()

    async def mark_retry(
        self,
        message_id: int,
        *,
        failure_code: str,
        now: datetime | None = None,
        jitter: float | None = None,
    ) -> str:
        """Back off a retryable failure, or dead-letter once attempts are exhausted."""
        row = await self._require(message_id)
        row.last_error = failure_code
        if row.attempts >= self._max_attempts:
            row.state = STATE_DEAD_LETTER
            log.error(
                "outbox.dead_letter",
                outbox_id=row.id,
                job_type=row.name,
                attempts=row.attempts,
                failure_code=failure_code,
            )
        else:
            moment = now or datetime.now(tz=UTC)
            row.state = STATE_PENDING
            row.claimed_at = None
            row.claimed_by = None
            row.available_at = moment + timedelta(
                seconds=backoff_seconds(row.attempts, jitter=jitter)
            )
        await self._session.flush()
        return row.state

    async def mark_failed(self, message_id: int, *, failure_code: str) -> None:
        """Permanent failure — never retried (jobs-and-workers.md §4)."""
        row = await self._require(message_id)
        row.state = STATE_FAILED
        row.last_error = failure_code
        await self._session.flush()

    async def mark_dead_letter(self, message_id: int, *, failure_code: str) -> None:
        row = await self._require(message_id)
        row.state = STATE_DEAD_LETTER
        row.last_error = failure_code
        log.error(
            "outbox.dead_letter", outbox_id=row.id, job_type=row.name, failure_code=failure_code
        )
        await self._session.flush()

    async def reap_leases(
        self,
        *,
        lease_seconds: int,
        overrides: Mapping[str, int] | None = None,
        now: datetime | None = None,
    ) -> int:
        """Return claims whose lease expired to pending (jobs-and-workers.md §3).

        ``lease_seconds`` is the default; ``overrides`` sets a longer or shorter
        lease per message name (§5), so a long job is not handed to a second
        worker while the first is still running it.
        """
        moment = now or datetime.now(tz=UTC)
        leases = dict(overrides or {})
        shortest = min([lease_seconds, *leases.values()])
        result = await self._session.execute(
            select(OutboxRow).where(
                OutboxRow.state == STATE_CLAIMED,
                OutboxRow.claimed_at.is_not(None),
                OutboxRow.claimed_at <= moment - timedelta(seconds=shortest),
            )
        )
        reaped = 0
        for row in result.scalars().all():
            lease = leases.get(row.name, lease_seconds)
            if row.claimed_at is None or row.claimed_at > moment - timedelta(seconds=lease):
                continue
            row.state = STATE_PENDING
            row.claimed_at = None
            row.claimed_by = None
            row.available_at = moment
            reaped += 1
        await self._session.flush()
        return reaped

    async def _require(self, message_id: int) -> OutboxRow:
        row = await self._session.get(OutboxRow, message_id)
        if row is None:
            raise ValueError("outbox row missing")
        return row


class SqlOutboxEventPort:
    """Billing-facing EventPort: write an outbound EventEnvelope into the outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def emit(self, event: BillingEventEnvelope) -> None:
        existing = await self._session.execute(
            select(OutboxRow.id)
            .where(
                OutboxRow.kind == KIND_EVENT,
                OutboxRow.name == event.event_name,
                OutboxRow.idempotency_key == event.idempotency_key,
            )
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return

        row = OutboxRow(
            organisation_id=event.organisation_id,
            kind=KIND_EVENT,
            name=event.event_name,
            payload=event.to_payload(event_id=f"evt_{uuid.uuid4().hex}"),
            idempotency_key=event.idempotency_key,
            available_at=event.occurred_at,
            attempts=0,
            state=STATE_PENDING,
        )
        self._session.add(row)
        await self._session.flush()


class InMemoryEventPort:
    """Test double only. Never wired in bootstrap for a real environment."""

    def __init__(self) -> None:
        self.events: list[BillingEventEnvelope] = []

    async def emit(self, event: BillingEventEnvelope) -> None:
        self.events.append(event)


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "KIND_EVENT",
    "KIND_JOB",
    "STATE_CLAIMED",
    "STATE_DEAD_LETTER",
    "STATE_DONE",
    "STATE_FAILED",
    "STATE_PENDING",
    "ClaimedMessage",
    "InMemoryEventPort",
    "SqlOutboxEventPort",
    "SqlOutboxRepository",
    "backoff_seconds",
]
