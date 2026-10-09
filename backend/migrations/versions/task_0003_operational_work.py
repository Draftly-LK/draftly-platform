"""Operational task records and immutable history; existing evidence remains intact."""

import sqlalchemy as sa
from alembic import op

revision = "task0003"
down_revision = "draft0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matter_work_tasks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("group", sa.String(32), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("title_key", sa.String(256)),
        sa.Column("reason", sa.Text()),
        sa.Column("reason_key", sa.String(256)),
        sa.Column("assigned_to", sa.String(64)),
        sa.Column("completed_by", sa.String(64)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("suggestion_status", sa.String(32)),
        sa.Column("dedup_key", sa.String(64)),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "matter_id", "dedup_key", name="uq_work_task_dedup"),
    )
    op.create_index("ix_work_tasks_user_matter", "matter_work_tasks", ["user_id", "matter_id"])
    op.create_table(
        "matter_work_task_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(128), sa.ForeignKey("matter_work_tasks.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("evidence", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_work_history_task",
        "matter_work_task_history",
        ["user_id", "matter_id", "task_id", "id"],
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM matter_work_tasks")).scalar_one()
    if count:
        raise RuntimeError("Cannot discard recorded matter tasks or decision history.")
    op.drop_table("matter_work_task_history")
    op.drop_table("matter_work_tasks")
