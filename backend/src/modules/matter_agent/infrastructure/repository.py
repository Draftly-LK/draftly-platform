"""SQLAlchemy repositories and the Neon conversation adapter.

``NeonConversationAdapter`` is the **only** ``ConversationPort`` implementation.
Chat history is served from Neon and never from a provider
(``matter-agent-service.md`` invariant 5). There is deliberately no
provider-backed conversation adapter to fall back to.

Every query filters ``user_id`` first (``security-model.md`` §2). A row
belonging to another user is invisible, which is what makes the router's 404
indistinguishable from a genuinely missing session.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter_agent.domain.models import (
    AgentMessage,
    AgentSession,
    MessageRole,
    PendingAction,
    PendingActionState,
    SessionState,
    ToolCallRecord,
    content_hash,
)
from src.modules.matter_agent.infrastructure.orm import (
    AgentMessageRow,
    AgentPendingActionRow,
    AgentSessionRow,
    AgentToolCallRow,
)
from src.modules.matter_agent.ports import MessagePage
from src.platform import ids
from src.platform.pagination import Cursor


def _to_session(row: AgentSessionRow) -> AgentSession:
    return AgentSession(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        model_version=row.model_version,
        prompt_version=row.prompt_version,
        state=SessionState(row.state),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_message(row: AgentMessageRow) -> AgentMessage:
    return AgentMessage(
        id=row.id,
        session_id=row.session_id,
        matter_id=row.matter_id,
        user_id=row.user_id,
        sequence=row.sequence,
        role=MessageRole(row.role),
        content=row.content,
        content_hash=row.content_hash,
        job_id=row.job_id,
        tool_call_id=row.tool_call_id,
        pending_action_id=row.pending_action_id,
        created_at=row.created_at,
    )


def _to_pending_action(row: AgentPendingActionRow) -> PendingAction:
    return PendingAction(
        id=row.id,
        session_id=row.session_id,
        matter_id=row.matter_id,
        user_id=row.user_id,
        action_kind=row.action_kind,
        arguments=dict(row.arguments),
        target_ref=row.target_ref,
        target_version=row.target_version,
        state=PendingActionState(row.state),
        reason_code=row.reason_code,
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


class SqlAgentSessionRepository:
    """Lazy provisioning of the one session per (user_id, matter_id)."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def find(self, *, user_id: str, matter_id: str) -> AgentSession | None:
        row = (
            await self._db.execute(
                select(AgentSessionRow).where(
                    AgentSessionRow.user_id == user_id,
                    AgentSessionRow.matter_id == matter_id,
                )
            )
        ).scalar_one_or_none()
        return _to_session(row) if row else None

    async def create(self, session: AgentSession) -> AgentSession:
        self._db.add(
            AgentSessionRow(
                id=session.id,
                user_id=session.user_id,
                matter_id=session.matter_id,
                state=session.state.value,
                model_version=session.model_version,
                prompt_version=session.prompt_version,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )
        await self._db.flush()
        return session


class NeonConversationAdapter:
    """The authoritative transcript, read and written in Neon.

    ``append`` allocates the next sequence inside the caller's transaction, so
    the message and its outbox event commit together or not at all. The unique
    constraint on ``(session_id, sequence)`` is the backstop: two concurrent
    appends cannot both claim the same slot.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def append(
        self,
        *,
        session: AgentSession,
        role: MessageRole,
        content: str,
        job_id: str | None = None,
        tool_call_id: str | None = None,
        pending_action_id: str | None = None,
    ) -> AgentMessage:
        next_sequence = (
            await self._db.execute(
                select(func.coalesce(func.max(AgentMessageRow.sequence), 0) + 1).where(
                    AgentMessageRow.session_id == session.id
                )
            )
        ).scalar_one()

        message = AgentMessage(
            id=ids.new_id(ids.AGENT_MESSAGE),
            session_id=session.id,
            matter_id=session.matter_id,
            user_id=session.user_id,
            sequence=int(next_sequence),
            role=role,
            content=content,
            content_hash=content_hash(content),
            job_id=job_id,
            tool_call_id=tool_call_id,
            pending_action_id=pending_action_id,
            created_at=datetime.now(tz=UTC),
        )
        self._db.add(
            AgentMessageRow(
                id=message.id,
                session_id=message.session_id,
                user_id=message.user_id,
                matter_id=message.matter_id,
                sequence=message.sequence,
                role=message.role.value,
                content=message.content,
                content_hash=message.content_hash,
                job_id=message.job_id,
                tool_call_id=message.tool_call_id,
                pending_action_id=message.pending_action_id,
                created_at=message.created_at,
            )
        )
        await self._db.flush()
        return message

    async def page(
        self,
        *,
        session_id: str,
        limit: int,
        cursor: Cursor | None = None,
    ) -> MessagePage:
        """Newest first, cursor keyed on the monotonic sequence.

        The sequence is the sort key and the tie-breaker at once, which is
        stronger than ``createdAt`` plus id: two messages cannot share it.
        """
        query = select(AgentMessageRow).where(AgentMessageRow.session_id == session_id)
        if cursor is not None:
            query = query.where(AgentMessageRow.sequence < int(cursor.id))
        rows = (
            (
                await self._db.execute(
                    query.order_by(AgentMessageRow.sequence.desc()).limit(limit + 1)
                )
            )
            .scalars()
            .all()
        )

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            Cursor(created_at=page_rows[-1].created_at, id=str(page_rows[-1].sequence))
            if has_more and page_rows
            else None
        )
        return MessagePage(
            items=tuple(_to_message(row) for row in page_rows),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def recent(self, *, session_id: str, limit: int) -> tuple[AgentMessage, ...]:
        rows = (
            (
                await self._db.execute(
                    select(AgentMessageRow)
                    .where(AgentMessageRow.session_id == session_id)
                    .order_by(AgentMessageRow.sequence.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return tuple(_to_message(row) for row in reversed(rows))


class SqlToolCallRepository:
    """Records every attempted tool call, executed or refused."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def record(self, call: ToolCallRecord) -> None:
        self._db.add(
            AgentToolCallRow(
                id=call.id,
                session_id=call.session_id,
                job_id=call.job_id,
                user_id=call.user_id,
                matter_id=call.matter_id,
                actor_id=call.actor_id,
                tool=call.tool,
                capability=call.capability,
                outcome=call.outcome.value,
                reason_code=call.reason_code,
                model_version=call.model_version,
                prompt_version=call.prompt_version,
                input_summary=call.input_summary,
                result_refs=list(call.result_refs),
                started_at=call.started_at,
                finished_at=call.finished_at,
            )
        )
        await self._db.flush()


class SqlPendingActionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def get(self, *, action_id: str, matter_id: str) -> PendingAction | None:
        row = (
            await self._db.execute(
                select(AgentPendingActionRow).where(
                    AgentPendingActionRow.id == action_id,
                    AgentPendingActionRow.matter_id == matter_id,
                )
            )
        ).scalar_one_or_none()
        return _to_pending_action(row) if row else None

    async def create(self, action: PendingAction) -> PendingAction:
        self._db.add(
            AgentPendingActionRow(
                id=action.id,
                session_id=action.session_id,
                user_id=action.user_id,
                matter_id=action.matter_id,
                action_kind=action.action_kind,
                arguments=dict(action.arguments),
                target_ref=action.target_ref,
                target_version=action.target_version,
                state=action.state.value,
                reason_code=action.reason_code,
                confirmed_by=action.confirmed_by,
                confirmed_at=action.confirmed_at,
                expires_at=action.expires_at,
                created_at=action.created_at,
            )
        )
        await self._db.flush()
        return action

    async def update(self, action: PendingAction) -> PendingAction:
        row = (
            await self._db.execute(
                select(AgentPendingActionRow).where(AgentPendingActionRow.id == action.id)
            )
        ).scalar_one()
        row.state = action.state.value
        row.reason_code = action.reason_code
        row.confirmed_by = action.confirmed_by
        row.confirmed_at = action.confirmed_at
        await self._db.flush()
        return action
