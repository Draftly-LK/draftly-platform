"""matter_agent_0001: the authoritative chat transcript and the agent turn loop.

Neon holds the complete transcript. ``agent_messages.content`` is the record;
no provider and no object store carries chat content
(``matter-agent-service.md`` §Summary).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "matteragent0001"
down_revision = "document0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.Column("model_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "matter_id", name="uq_agent_sessions_user_matter"),
    )
    op.create_index("ix_agent_sessions_user_matter", "agent_sessions", ["user_id", "matter_id"])

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("pending_action_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("session_id", "sequence", name="uq_agent_messages_session_sequence"),
    )
    op.create_index(
        "ix_agent_messages_session_sequence", "agent_messages", ["session_id", "sequence"]
    )
    op.create_index("ix_agent_messages_user_matter", "agent_messages", ["user_id", "matter_id"])

    op.create_table(
        "agent_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("failure_class", sa.String(64), nullable=True),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_jobs_session_state", "agent_jobs", ["session_id", "state"])
    op.create_index("ix_agent_jobs_user_matter", "agent_jobs", ["user_id", "matter_id"])

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("tool", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("model_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("input_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_tool_calls_job", "agent_tool_calls", ["job_id"])
    op.create_index("ix_agent_tool_calls_user_matter", "agent_tool_calls", ["user_id", "matter_id"])
    op.create_index("ix_agent_tool_calls_outcome", "agent_tool_calls", ["session_id", "outcome"])

    op.create_table(
        "agent_pending_actions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("action_kind", sa.String(64), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("target_ref", sa.String(128), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("confirmed_by", sa.String(64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_agent_pending_actions_session_state", "agent_pending_actions", ["session_id", "state"]
    )
    op.create_index(
        "ix_agent_pending_actions_user_matter", "agent_pending_actions", ["user_id", "matter_id"]
    )

    op.create_table(
        "agent_stream_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("job_id", "sequence", name="uq_agent_stream_events_job_sequence"),
    )
    op.create_index(
        "ix_agent_stream_events_job_sequence", "agent_stream_events", ["job_id", "sequence"]
    )
    op.create_index("ix_agent_stream_events_created", "agent_stream_events", ["created_at"])

    op.create_table(
        "matter_notes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("author_id", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False, server_default="human"),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_matter_notes_user_matter", "matter_notes", ["user_id", "matter_id"])


def downgrade() -> None:
    op.drop_table("matter_notes")
    op.drop_table("agent_stream_events")
    op.drop_table("agent_pending_actions")
    op.drop_table("agent_tool_calls")
    op.drop_table("agent_jobs")
    op.drop_table("agent_messages")
    op.drop_table("agent_sessions")
