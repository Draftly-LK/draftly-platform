"""Worker runner: claim, dispatch, then ack / retry / fail / dead-letter.

The outbox repository and session maker are replaced with in-memory fakes, so
one iteration of the loop runs without a database. What is pinned here is the
contract in jobs-and-workers.md §1: one transaction per message, and a handler
crash costs a retry rather than the worker.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.platform.messaging.dispatcher import MessageDispatcher, MessageResult
from src.platform.messaging.outbox import KIND_EVENT, KIND_JOB, ClaimedMessage
from src.workers import runner


class FakeSession:
    def __init__(self, journal: list[tuple[Any, ...]], number: int) -> None:
        self.journal = journal
        self.number = number

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.journal.append(("close", self.number))

    async def commit(self) -> None:
        self.journal.append(("commit", self.number))

    async def rollback(self) -> None:
        self.journal.append(("rollback", self.number))


class FakeOutbox:
    """Stands in for SqlOutboxRepository; records calls against its session."""

    pending: list[ClaimedMessage] = []

    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def _record(self, *entry: Any) -> None:
        self._session.journal.append((*entry, self._session.number))

    async def reap_leases(self, *, lease_seconds: int) -> int:
        self._record("reap", lease_seconds)
        return 0

    async def claim_batch(self, *, worker_id: str, batch: int) -> list[ClaimedMessage]:
        self._record("claim", worker_id, batch)
        claimed, FakeOutbox.pending = FakeOutbox.pending[:batch], FakeOutbox.pending[batch:]
        return claimed

    async def mark_done(self, outbox_id: int) -> None:
        self._record("done", outbox_id)

    async def mark_retry(self, outbox_id: int, *, failure_code: str) -> None:
        self._record("retry", outbox_id, failure_code)

    async def mark_failed(self, outbox_id: int, *, failure_code: str) -> None:
        self._record("failed", outbox_id, failure_code)

    async def mark_dead_letter(self, outbox_id: int, *, failure_code: str) -> None:
        self._record("dead_letter", outbox_id, failure_code)


@pytest.fixture
def journal(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    entries: list[tuple[Any, ...]] = []
    counter = iter(range(1, 1000))

    def session_maker() -> FakeSession:
        return FakeSession(entries, next(counter))

    monkeypatch.setattr(runner, "get_session_maker", lambda: session_maker)
    monkeypatch.setattr(runner, "SqlOutboxRepository", FakeOutbox)
    FakeOutbox.pending = []
    return entries


def _message(outbox_id: int = 1, *, kind: str = KIND_JOB, name: str = "demo.job") -> ClaimedMessage:
    return ClaimedMessage(
        id=outbox_id,
        organisation_id="org_1",
        kind=kind,
        name=name,
        payload={"n": outbox_id},
        idempotency_key=f"key-{outbox_id}",
        attempts=1,
    )


def _dispatcher_returning(result: MessageResult) -> MessageDispatcher:
    dispatcher = MessageDispatcher()

    async def handler(session: Any, message: ClaimedMessage) -> MessageResult:
        return result

    dispatcher.register_job("demo.job", handler)
    return dispatcher


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (MessageResult.DONE, ("done", 7)),
        (MessageResult.RETRY, ("retry", 7, "handler_retry")),
        (MessageResult.FAILED, ("failed", 7, "handler_permanent_failure")),
        (MessageResult.DEAD_LETTER, ("dead_letter", 7, "handler_dead_letter")),
    ],
)
async def test_handler_result_maps_to_one_outbox_transition(
    journal: list[tuple[Any, ...]], result: MessageResult, expected: tuple[Any, ...]
) -> None:
    returned = await runner.process_message(
        _dispatcher_returning(result), _message(7), worker_id="w1"
    )

    assert returned is result
    # State change and commit happen on the same session as the handler.
    assert journal == [(*expected, 1), ("commit", 1), ("close", 1)]


async def test_handler_receives_the_transaction_session(journal: list[tuple[Any, ...]]) -> None:
    seen: list[tuple[Any, ClaimedMessage]] = []
    dispatcher = MessageDispatcher()

    async def handler(session: Any, message: ClaimedMessage) -> MessageResult:
        seen.append((session, message))
        return MessageResult.DONE

    dispatcher.register_job("demo.job", handler)
    await runner.process_message(dispatcher, _message(3), worker_id="w1")

    assert len(seen) == 1
    assert isinstance(seen[0][0], FakeSession)
    assert seen[0][1].payload == {"n": 3}


async def test_handler_crash_rolls_back_and_schedules_retry_in_a_fresh_session(
    journal: list[tuple[Any, ...]],
) -> None:
    dispatcher = MessageDispatcher()

    async def handler(session: Any, message: ClaimedMessage) -> MessageResult:
        raise ValueError("boom")

    dispatcher.register_job("demo.job", handler)

    returned = await runner.process_message(dispatcher, _message(9), worker_id="w1")

    assert returned is MessageResult.RETRY
    assert journal == [
        ("rollback", 1),
        ("retry", 9, "handler_error", 2),
        ("commit", 2),
        ("close", 2),
        ("close", 1),
    ]
    # The poisoned transaction is never committed.
    assert ("commit", 1) not in journal


async def test_job_without_a_handler_is_a_permanent_failure(
    journal: list[tuple[Any, ...]],
) -> None:
    returned = await runner.process_message(
        MessageDispatcher(), _message(4, name="nobody.listens"), worker_id="w1"
    )
    assert returned is MessageResult.FAILED
    assert ("failed", 4, "handler_permanent_failure", 1) in journal


async def test_event_without_a_subscriber_is_acknowledged(
    journal: list[tuple[Any, ...]],
) -> None:
    returned = await runner.process_message(
        MessageDispatcher(), _message(5, kind=KIND_EVENT, name="x.happened"), worker_id="w1"
    )
    assert returned is MessageResult.DONE
    assert ("done", 5, 1) in journal


async def test_run_once_reaps_claims_commits_then_processes_each_message(
    journal: list[tuple[Any, ...]],
) -> None:
    FakeOutbox.pending = [_message(1), _message(2), _message(3)]

    handled = await runner.run_once(
        _dispatcher_returning(MessageResult.DONE), worker_id="w9", batch=2
    )

    assert handled == 2
    assert journal[:4] == [
        ("reap", runner.DEFAULT_LEASE_SECONDS, 1),
        ("claim", "w9", 2, 1),
        ("commit", 1),
        ("close", 1),
    ]
    # One transaction per message, each in its own session.
    assert journal[4:] == [
        ("done", 1, 2),
        ("commit", 2),
        ("close", 2),
        ("done", 2, 3),
        ("commit", 3),
        ("close", 3),
    ]
    assert [m.id for m in FakeOutbox.pending] == [3]


async def test_run_once_with_empty_outbox_handles_nothing(journal: list[tuple[Any, ...]]) -> None:
    handled = await runner.run_once(_dispatcher_returning(MessageResult.DONE), worker_id="w1")

    assert handled == 0
    assert ("claim", "w1", runner.DEFAULT_BATCH, 1) in journal
    assert not any(entry[0] in {"done", "retry", "failed", "dead_letter"} for entry in journal)


async def test_one_crashing_message_does_not_stop_the_batch(
    journal: list[tuple[Any, ...]],
) -> None:
    dispatcher = MessageDispatcher()

    async def handler(session: Any, message: ClaimedMessage) -> MessageResult:
        if message.id == 1:
            raise RuntimeError("first one breaks")
        return MessageResult.DONE

    dispatcher.register_job("demo.job", handler)
    FakeOutbox.pending = [_message(1), _message(2)]

    handled = await runner.run_once(dispatcher, worker_id="w1")

    assert handled == 2
    transitions = [e[:2] for e in journal if e[0] in {"done", "retry"}]
    assert transitions == [("retry", 1), ("done", 2)]
