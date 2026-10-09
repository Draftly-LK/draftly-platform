"""Worker jobs for the matter agent.

``agent.run-turn`` executes one turn off the request path. The payload carries
identifiers only, so this module re-reads the message content from Neon by id
(``events.md`` §2).

A failed turn never mutates the transcript it was reporting on: the user's
message stays, the job row records the failure, and no assistant message is
fabricated (``jobs-and-workers.md`` §4).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter_agent.domain.models import JobState
from src.modules.matter_agent.infrastructure.orm import (
    AgentJobRow,
    AgentMessageRow,
    AgentSessionRow,
    AgentStreamEventRow,
)

log = structlog.get_logger(__name__)

RUN_TURN_JOB_TYPE = "agent.run-turn"
PURGE_STREAM_EVENTS_JOB_TYPE = "agent.purge-stream-events"

#: Resumable stream events are presentation state and are dropped after a day
#: (`matter-agent-service.md` §Events and jobs).
STREAM_EVENT_TTL = timedelta(hours=24)


async def run_turn_job(session: AsyncSession, payload: Mapping[str, Any]) -> str:
    """Execute one queued turn.

    Returns a stable outcome string the dispatcher maps to an outbox result:
    ``completed``, ``failed``, ``retry`` or ``unknown-job``.
    """
    job_id = str(payload.get("jobId", ""))
    session_id = str(payload.get("sessionId", ""))
    message_id = str(payload.get("messageId", ""))
    if not (job_id and session_id and message_id):
        return "unknown-job"

    from src.modules.matter_agent.infrastructure.job_repository import SqlAgentJobPort

    jobs = SqlAgentJobPort(session)

    chat_session = (
        await session.execute(select(AgentSessionRow).where(AgentSessionRow.id == session_id))
    ).scalar_one_or_none()
    user_message = (
        await session.execute(select(AgentMessageRow).where(AgentMessageRow.id == message_id))
    ).scalar_one_or_none()
    if chat_session is None or user_message is None:
        # The transcript row is gone — destroyed or rolled back. Nothing to
        # answer, and inventing a reply would be worse than doing nothing.
        return "unknown-job"

    job = (
        await session.execute(
            select(AgentJobRow)
            .where(
                AgentJobRow.id == job_id,
                AgentJobRow.session_id == session_id,
                AgentJobRow.user_id == chat_session.user_id,
                AgentJobRow.matter_id == chat_session.matter_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if (
        job is None
        or user_message.session_id != session_id
        or user_message.user_id != chat_session.user_id
        or user_message.matter_id != chat_session.matter_id
        or (job.source_message_id and job.source_message_id != user_message.id)
    ):
        return "unknown-job"
    if job.state in ("succeeded", "failed", "dead_letter"):
        return "completed" if job.state == "succeeded" else "failed"
    job.state = "running"

    # Imported lazily so this module stays out of the wiring graph.
    from src.bootstrap import run_agent_turn

    result = await run_agent_turn(
        session,
        job_id=job_id,
        chat_session=chat_session,
        user_message=user_message,
    )
    await jobs.finish(
        job_id=job_id,
        state=result.outcome,
        tool_call_count=result.tool_call_count,
        failure_class=result.failure_class,
    )
    log.info(
        "agent.turn_finished",
        job_id=job_id,
        outcome=result.outcome.value,
        tool_calls=result.tool_call_count,
    )
    return "completed" if result.outcome is JobState.SUCCEEDED else "failed"


async def purge_stream_events(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Delete resumable stream events older than the TTL.

    Idempotent and safe to run late, like every scheduled job
    (``jobs-and-workers.md`` §6).
    """
    cutoff = (now or datetime.now(tz=UTC)) - STREAM_EVENT_TTL
    result = await session.execute(
        delete(AgentStreamEventRow).where(AgentStreamEventRow.created_at < cutoff)
    )
    deleted = int(getattr(result, "rowcount", 0) or 0)
    await session.flush()
    if deleted:
        log.info("agent.stream_events_purged", count=deleted)
    return deleted
