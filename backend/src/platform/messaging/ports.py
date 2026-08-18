"""Outbox port — the only way an application service publishes or enqueues.

Pure protocols so application and domain layers stay free of SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from src.platform.messaging.envelope import EventEnvelope


class OutboxPort(Protocol):
    """Writes event and job rows in the caller's transaction (jobs-and-workers.md §2)."""

    async def publish_event(self, envelope: EventEnvelope) -> bool:
        """Append an event row. Returns False when the idempotency key already exists."""
        ...

    async def enqueue_job(
        self,
        *,
        job_type: str,
        organisation_id: str,
        idempotency_key: str,
        message: Mapping[str, Any],
        available_at: datetime | None = None,
    ) -> bool:
        """Append a job row. Returns False when the idempotency key already exists."""
        ...


__all__ = ["OutboxPort"]
