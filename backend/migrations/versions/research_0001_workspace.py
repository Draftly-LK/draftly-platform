"""research_0001: authoritative global research workspace."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "research0001"
down_revision = "matteragent0001"
branch_labels = None
depends_on = None


def _owned(columns: list[sa.Column[object]]) -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=True),
        *columns,
    ]


def upgrade() -> None:
    op.create_table(
        "research_conversations",
        *_owned(
            [
                sa.Column("scope_type", sa.String(32), nullable=False),
                sa.Column("scope_target_id", sa.String(64)),
                sa.Column("title", sa.String(256), nullable=False),
                sa.Column("active_branch_id", sa.String(64), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("archived_at", sa.DateTime(timezone=True)),
            ]
        ),
    )
    op.create_index(
        "ix_research_conversations_user_updated",
        "research_conversations",
        ["user_id", "updated_at"],
    )
    op.create_table(
        "research_branches",
        *_owned(
            [
                sa.Column(
                    "conversation_id",
                    sa.String(64),
                    sa.ForeignKey("research_conversations.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("root_message_id", sa.String(64)),
                sa.Column("created_by", sa.String(64), nullable=False),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        ),
    )
    op.create_table(
        "research_messages",
        *_owned(
            [
                sa.Column(
                    "conversation_id",
                    sa.String(64),
                    sa.ForeignKey("research_conversations.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column(
                    "branch_id",
                    sa.String(64),
                    sa.ForeignKey("research_branches.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("sequence", sa.Integer(), nullable=False),
                sa.Column("parent_message_id", sa.String(64)),
                sa.Column("edited_from_id", sa.String(64)),
                sa.Column("role", sa.String(16), nullable=False),
                sa.Column("content", sa.Text(), nullable=False),
                sa.Column("answer_id", sa.String(64)),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        ),
    )
    op.create_index(
        "ix_research_messages_user_conversation",
        "research_messages",
        ["user_id", "conversation_id", "created_at"],
    )
    op.create_table(
        "research_jobs",
        *_owned(
            [
                sa.Column(
                    "conversation_id",
                    sa.String(64),
                    sa.ForeignKey("research_conversations.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("user_message_id", sa.String(64), nullable=False),
                sa.Column("state", sa.String(32), nullable=False),
                sa.Column("corpus_version", sa.String(128), nullable=False),
                sa.Column("failure_class", sa.String(64)),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("finished_at", sa.DateTime(timezone=True)),
            ]
        ),
    )
    op.create_table(
        "research_stream_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(64),
            sa.ForeignKey("research_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("job_id", "sequence", name="uq_research_stream_job_sequence"),
    )
    op.create_table(
        "research_tool_calls",
        *_owned(
            [
                sa.Column(
                    "job_id",
                    sa.String(64),
                    sa.ForeignKey("research_jobs.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("message_id", sa.String(64), nullable=False),
                sa.Column("tool_name", sa.String(128), nullable=False),
                sa.Column("status", sa.String(32), nullable=False),
                sa.Column("input_summary", sa.String(256), nullable=False),
                sa.Column("result_reference", sa.String(128)),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        ),
    )
    op.create_table(
        "research_answers",
        *_owned(
            [
                sa.Column("conversation_id", sa.String(64), nullable=False),
                sa.Column("message_id", sa.String(64), nullable=False),
                sa.Column("kind", sa.String(32), nullable=False),
                sa.Column("question", sa.Text(), nullable=False),
                sa.Column("corpus_version", sa.String(128), nullable=False),
                sa.Column("reason_key", sa.String(128)),
                sa.Column("suggested_action_key", sa.String(128)),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            ]
        ),
    )
    op.create_table(
        "research_claims",
        *_owned(
            [
                sa.Column(
                    "answer_id",
                    sa.String(64),
                    sa.ForeignKey("research_answers.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("position", sa.Integer(), nullable=False),
                sa.Column("text", sa.Text(), nullable=False),
            ]
        ),
    )
    op.create_table(
        "research_citations",
        *_owned(
            [
                sa.Column(
                    "claim_id",
                    sa.String(64),
                    sa.ForeignKey("research_claims.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("source_id", sa.String(128), nullable=False),
                sa.Column("authority_id", sa.String(128), nullable=False),
                sa.Column("corpus_version", sa.String(128), nullable=False),
                sa.Column("passage", sa.Text(), nullable=False),
                sa.Column("page", sa.Integer(), nullable=False),
                sa.Column("verified", sa.Boolean(), nullable=False),
            ]
        ),
    )

    # The billing catalogue already knows this metric, but the original
    # synthetic plans predate research metering. Keep the local/CI plans usable
    # without weakening the runtime reservation requirement.
    plan_entitlements = sa.table(
        "plan_entitlements",
        sa.column("id", sa.String),
        sa.column("plan_version_id", sa.String),
        sa.column("feature_key", sa.String),
        sa.column("limit_value", sa.Integer),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        plan_entitlements,
        [
            {
                "id": "ent_trial_research_queries",
                "plan_version_id": "plan_trial_v1",
                "feature_key": "research_queries.monthly",
                "limit_value": None,
                "enabled": True,
            },
            {
                "id": "ent_solo_research_queries",
                "plan_version_id": "plan_solo_v1",
                "feature_key": "research_queries.monthly",
                "limit_value": None,
                "enabled": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM plan_entitlements "
            "WHERE id IN ('ent_trial_research_queries', 'ent_solo_research_queries')"
        )
    )
    for table in (
        "research_citations",
        "research_claims",
        "research_answers",
        "research_tool_calls",
        "research_stream_events",
        "research_jobs",
        "research_messages",
        "research_branches",
        "research_conversations",
    ):
        op.drop_table(table)
