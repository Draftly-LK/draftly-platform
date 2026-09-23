"""Half-wired worker machinery, recorded as strict expected failures (§6.5).

Each test states the behaviour the system should have. ``strict=True`` turns
the day it starts passing into a failure too, so whoever closes the gap is
told to delete the marker rather than leave a stale one. ``raises`` pins the
expected failure to the assertion, so a refactor that breaks the test itself
surfaces as an error instead of hiding inside the xfail.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from src.modules.obligations.infrastructure.repository import SqlNotificationIntentPort
from src.platform.messaging.outbox import SqlOutboxRepository

SRC = Path(__file__).resolve().parents[2] / "src"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "matter_agent.jobs.purge_stream_events has no caller and no scheduler, so "
        "resumable stream events accumulate forever (jobs-and-workers.md §6)."
    ),
)
def test_purge_stream_events_has_a_caller() -> None:
    callers = [
        path
        for path in SRC.rglob("*.py")
        if re.search(r"(?<!def )\bpurge_stream_events\(", path.read_text(encoding="utf-8"))
    ]

    assert callers, "nothing calls purge_stream_events"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "The notification-intent port wired in api/deps.py keeps reminders in an "
        "in-process list, so no obligation.reminder-due event reaches the outbox and "
        "the notification consumer for it can never fire."
    ),
)
async def test_a_recorded_reminder_reaches_the_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[str] = []

    async def publish_event(self: SqlOutboxRepository, envelope: Any) -> bool:
        published.append(envelope.event_name)
        return True

    async def enqueue_job(self: SqlOutboxRepository, **job: Any) -> bool:
        published.append(job["job_type"])
        return True

    monkeypatch.setattr(SqlOutboxRepository, "publish_event", publish_event)
    monkeypatch.setattr(SqlOutboxRepository, "enqueue_job", enqueue_job)

    await SqlNotificationIntentPort().record_reminder_intent(object())

    assert "obligation.reminder-due" in published
