"""matter_agent_0002: archived conversation segments and answer citations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "matteragent0002"
down_revision = "research0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_agent_conversations_session_created",
        "agent_conversations",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_agent_conversations_user_matter",
        "agent_conversations",
        ["user_id", "matter_id"],
    )

    op.add_column("agent_sessions", sa.Column("active_conversation_id", sa.String(64)))
    op.add_column("agent_messages", sa.Column("conversation_id", sa.String(64)))
    op.add_column(
        "agent_messages",
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_foreign_key(
        "fk_agent_messages_conversation",
        "agent_messages",
        "agent_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Every existing durable session becomes the first archived-capable segment.
    connection.execute(
        sa.text(
            """
        INSERT INTO agent_conversations
            (id, session_id, user_id, matter_id, state, created_at, updated_at)
        SELECT
            'aconv_' || id, id, user_id, matter_id, 'active', created_at, updated_at
        FROM agent_sessions
        """
        )
    )
    connection.execute(
        sa.text(
            "UPDATE agent_messages SET conversation_id = 'aconv_' || session_id "
            "WHERE conversation_id IS NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE agent_sessions SET active_conversation_id = 'aconv_' || id "
            "WHERE active_conversation_id IS NULL"
        )
    )
    op.create_index(
        "ix_agent_messages_conversation_sequence",
        "agent_messages",
        ["conversation_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_messages_conversation_sequence", table_name="agent_messages")
    op.drop_constraint("fk_agent_messages_conversation", "agent_messages", type_="foreignkey")
    op.drop_column("agent_messages", "citations")
    op.drop_column("agent_messages", "conversation_id")
    op.drop_column("agent_sessions", "active_conversation_id")
    op.drop_table("agent_conversations")
