"""Agent job rows and the outbox enqueue.

Both happen on the caller's session, so the job, the message and the outbox
entry commit in a single transaction (``jobs-and-workers.md`` §2). Nothing is
enqueued before commit and nothing calls a queue inside the transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter_agent.application.agent_service import AgentJob, RetrySource
from src.modules.matter_agent.domain.models import JobState, MessageRole
from src.modules.matter_agent.infrastructure.orm import (
    AgentJobRow,
    AgentMessageRow,
    AgentToolCallRow,
)
from src.modules.matter_agent.infrastructure.repository import _to_message
from src.platform import ids
from src.platform.messaging.outbox import SqlOutboxRepository

JOB_TYPE = "agent.run-turn"


class SqlAgentJobPort:
    """Creates the job row and hands the turn to the existing worker."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session
        self._outbox = SqlOutboxRepository(session)

    async def create(
        self,
        *,
        session_id: str,
        user_id: str,
        matter_id: str,
        correlation_id: str,
        retry_of_job_id: str | None = None,
    ) -> AgentJob:
        job_id = ids.new_id(ids.AGENT_JOB)
        self._db.add(
            AgentJobRow(
                id=job_id,
                session_id=session_id,
                user_id=user_id,
                matter_id=matter_id,
                state=JobState.QUEUED.value,
                correlation_id=correlation_id,
                retry_of_job_id=retry_of_job_id,
                tool_call_count=0,
                created_at=datetime.now(tz=UTC),
            )
        )
        await self._db.flush()
        return AgentJob(job_id=job_id, state=JobState.QUEUED)

    async def enqueue(self, *, job_id: str, session_id: str, message_id: str, user_id: str) -> None:
        """Queue the turn. The payload carries identifiers only.

        No message text goes into the outbox: the worker re-reads content from
        Neon by id, because a payload may never carry matter content
        (``events.md`` §2).
        """
        job = (
            await self._db.execute(
                select(AgentJobRow).where(AgentJobRow.id == job_id, AgentJobRow.user_id == user_id)
            )
        ).scalar_one()
        job.source_message_id = message_id
        await self._outbox.enqueue_job(
            job_type=JOB_TYPE,
            # V0 has no organisation aggregate; the outbox tenant column carries
            # the owning user id, as billing_service already does
            # (`security-model.md` §2.1).
            organisation_id=user_id,
            message={"jobId": job_id, "sessionId": session_id, "messageId": message_id},
            idempotency_key=f"{JOB_TYPE}:{job_id}",
        )

    async def get(self, *, job_id: str, user_id: str) -> AgentJob | None:
        row = (
            await self._db.execute(
                select(AgentJobRow).where(AgentJobRow.id == job_id, AgentJobRow.user_id == user_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return AgentJob(
            job_id=row.id,
            state=JobState(row.state),
            tool_call_count=row.tool_call_count,
            failure_class=row.failure_class,
        )

    async def latest(
        self, *, session_id: str, user_id: str, conversation_id: str | None
    ) -> AgentJob | None:
        row = (
            await self._db.execute(
                select(AgentJobRow)
                .join(
                    AgentMessageRow,
                    or_(
                        AgentMessageRow.id == AgentJobRow.source_message_id,
                        (AgentJobRow.source_message_id.is_(None))
                        & (AgentMessageRow.job_id == AgentJobRow.id),
                    ),
                )
                .where(
                    AgentJobRow.user_id == user_id,
                    AgentJobRow.session_id == session_id,
                    AgentMessageRow.conversation_id == conversation_id,
                    AgentMessageRow.role == "user",
                )
                .order_by(AgentJobRow.created_at.desc(), AgentJobRow.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return (
            AgentJob(
                job_id=row.id,
                state=JobState(row.state),
                tool_call_count=row.tool_call_count,
                failure_class=row.failure_class,
            )
            if row
            else None
        )

    async def retry_source(
        self, *, job_id: str, user_id: str, matter_id: str
    ) -> RetrySource | None:
        row = (
            await self._db.execute(
                select(AgentJobRow)
                .where(
                    AgentJobRow.user_id == user_id,
                    AgentJobRow.matter_id == matter_id,
                    AgentJobRow.id == job_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        query = select(AgentMessageRow).where(
            AgentMessageRow.user_id == user_id,
            AgentMessageRow.matter_id == matter_id,
            AgentMessageRow.session_id == row.session_id,
            AgentMessageRow.role == MessageRole.USER.value,
        )
        # Old jobs predate the source-message column; retain their retry path.
        query = (
            query.where(AgentMessageRow.id == row.source_message_id)
            if row.source_message_id
            else query.where(AgentMessageRow.job_id == job_id)
        )
        message = (await self._db.execute(query)).scalar_one_or_none()
        if message is None:
            return None
        tool_call = (
            await self._db.execute(
                select(AgentToolCallRow.id)
                .where(
                    AgentToolCallRow.user_id == user_id,
                    AgentToolCallRow.job_id == job_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        latest = (
            await self._db.execute(
                select(AgentMessageRow.id)
                .where(
                    AgentMessageRow.user_id == user_id,
                    AgentMessageRow.session_id == row.session_id,
                )
                .order_by(AgentMessageRow.sequence.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        existing = (
            await self._db.execute(
                select(AgentJobRow).where(
                    AgentJobRow.user_id == user_id,
                    AgentJobRow.retry_of_job_id == job_id,
                )
            )
        ).scalar_one_or_none()
        return RetrySource(
            job=AgentJob(job_id=row.id, state=JobState(row.state), failure_class=row.failure_class),
            message=_to_message(message),
            has_tool_calls=tool_call is not None,
            is_latest_message=latest == message.id,
            existing_retry=AgentJob(job_id=existing.id, state=JobState(existing.state))
            if existing
            else None,
        )

    async def finish(
        self,
        *,
        job_id: str,
        state: JobState,
        tool_call_count: int,
        failure_class: str | None = None,
    ) -> None:
        row = (
            await self._db.execute(select(AgentJobRow).where(AgentJobRow.id == job_id))
        ).scalar_one()
        row.state = state.value
        row.tool_call_count = tool_call_count
        row.failure_class = failure_class
        row.finished_at = datetime.now(tz=UTC)
        await self._db.flush()
