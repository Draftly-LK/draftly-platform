"""Resumable stream events for one agent turn.

The persisted job row is authoritative; a stream is presentation state
(``api-conventions.md`` §6). A client that loses its connection resumes with
``Last-Event-ID`` and replays from the next sequence, and a client that never
connects loses nothing because polling reads the same job row.

Events are purged after 24 hours by ``agent.purge-stream-events``, so a very
late reconnect gets the job's final state rather than a partial replay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter_agent.infrastructure.orm import AgentStreamEventRow
from src.platform import ids


class SqlStreamEventRepository:
    """Append-only per-job event log with a monotonic sequence."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def append(
        self,
        *,
        job_id: str,
        user_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """Append one event and return its sequence.

        ``data`` carries identifiers, states and counts only — never message
        text or tool arguments. A stream frame is as public as a log line.
        """
        next_sequence = int(
            (
                await self._db.execute(
                    select(func.coalesce(func.max(AgentStreamEventRow.sequence), 0) + 1).where(
                        AgentStreamEventRow.job_id == job_id
                    )
                )
            ).scalar_one()
        )
        self._db.add(
            AgentStreamEventRow(
                id=ids.new_id("astr"),
                job_id=job_id,
                user_id=user_id,
                sequence=next_sequence,
                event_type=event_type,
                data=data,
                created_at=datetime.now(tz=UTC),
            )
        )
        await self._db.flush()
        return next_sequence

    async def since(
        self, *, job_id: str, user_id: str, after_sequence: int
    ) -> tuple[tuple[int, str, dict[str, Any]], ...]:
        """Events after the given sequence, oldest first.

        Filtered by ``user_id`` like every other read, so a guessed job id
        returns nothing rather than another user's progress.
        """
        rows = (
            (
                await self._db.execute(
                    select(AgentStreamEventRow)
                    .where(
                        AgentStreamEventRow.job_id == job_id,
                        AgentStreamEventRow.user_id == user_id,
                        AgentStreamEventRow.sequence > after_sequence,
                    )
                    .order_by(AgentStreamEventRow.sequence)
                )
            )
            .scalars()
            .all()
        )
        return tuple((row.sequence, row.event_type, dict(row.data)) for row in rows)
