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


class ResearchConversationRow(Base):
    __tablename__ = "research_conversations"
    __table_args__ = (Index("ix_research_conversations_user_updated", "user_id", "updated_at"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_target_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    active_branch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchBranchRow(Base):
    __tablename__ = "research_branches"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_conversations.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    root_message_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchMessageRow(Base):
    __tablename__ = "research_messages"
    __table_args__ = (
        Index("ix_research_messages_user_conversation", "user_id", "conversation_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_conversations.id", ondelete="CASCADE")
    )
    branch_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_branches.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_message_id: Mapped[str | None] = mapped_column(String(64))
    edited_from_id: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchJobRow(Base):
    __tablename__ = "research_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_conversations.id", ondelete="CASCADE")
    )
    user_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchStreamEventRow(Base):
    __tablename__ = "research_stream_events"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_research_stream_job_sequence"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_jobs.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchToolCallRow(Base):
    __tablename__ = "research_tool_calls"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_jobs.id", ondelete="CASCADE")
    )
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_summary: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    result_reference: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchAnswerRow(Base):
    __tablename__ = "research_answers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_key: Mapped[str | None] = mapped_column(String(128))
    suggested_action_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchClaimRow(Base):
    __tablename__ = "research_claims"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    answer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_answers.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class ResearchCitationRow(Base):
    __tablename__ = "research_citations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("research_claims.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authority_id: Mapped[str] = mapped_column(String(128), nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(128), nullable=False)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    verified: Mapped[bool] = mapped_column(nullable=False)
