"""SQLAlchemy ORM models for the matter master agent.

Neon is authoritative for the transcript, so ``agent_messages`` stores message
content and is the record — not an index into a provider
(``matter-agent-service.md`` §Summary). No chat transcript is written to GCS.

Every row carries ``user_id``. It is the first predicate of every query
(``security-model.md`` §2). No table carries ``organisation_id``, matching every
other module in this codebase; see §2.1 for the open central decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class AgentSessionRow(Base):
    """One durable chat session per (user_id, matter_id)."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "matter_id", name="uq_agent_sessions_user_matter"),
        Index("ix_agent_sessions_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    active_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentConversationRow(Base):
    """A visible transcript segment; closing it never removes its messages."""

    __tablename__ = "agent_conversations"
    __table_args__ = (
        Index("ix_agent_conversations_session_created", "session_id", "created_at"),
        Index("ix_agent_conversations_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentMessageRow(Base):
    """The authoritative transcript. Chat content lives here and nowhere else."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_agent_messages_session_sequence"),
        Index("ix_agent_messages_session_sequence", "session_id", "sequence"),
        Index("ix_agent_messages_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_action_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=True
    )
    citations: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentJobRow(Base):
    """One turn. States match ``api-conventions.md`` §6, including dead_letter."""

    __tablename__ = "agent_jobs"
    __table_args__ = (
        Index("ix_agent_jobs_session_state", "session_id", "state"),
        Index("ix_agent_jobs_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    failure_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentToolCallRow(Base):
    """Every attempted tool call, executed or refused.

    A denial is stored as deliberately as an execution: it is the outside view
    of a prompt injection (``matter-agent-service.md`` §Audit of tool calls).
    ``input_summary`` is a safe summary, never raw tool arguments.
    """

    __tablename__ = "agent_tool_calls"
    __table_args__ = (
        Index("ix_agent_tool_calls_job", "job_id"),
        Index("ix_agent_tool_calls_user_matter", "user_id", "matter_id"),
        Index("ix_agent_tool_calls_outcome", "session_id", "outcome"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.id"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    input_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_refs: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentPendingActionRow(Base):
    """A typed card awaiting human confirmation. ``target_version`` drives 412."""

    __tablename__ = "agent_pending_actions"
    __table_args__ = (
        Index("ix_agent_pending_actions_session_state", "session_id", "state"),
        Index("ix_agent_pending_actions_user_matter", "user_id", "matter_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_sessions.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentStreamEventRow(Base):
    """Short-lived resumable SSE events, purged hourly once older than 24h."""

    __tablename__ = "agent_stream_events"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_agent_stream_events_job_sequence"),
        Index("ix_agent_stream_events_job_sequence", "job_id", "sequence"),
        Index("ix_agent_stream_events_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MatterNoteRow(Base):
    """Non-authoritative working notes, the target of ``note.create``.

    ``origin`` is AI_SUGGESTED for anything the agent created — a stored column,
    not a rendering convention.
    """

    __tablename__ = "matter_notes"
    __table_args__ = (Index("ix_matter_notes_user_matter", "user_id", "matter_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="human")
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
