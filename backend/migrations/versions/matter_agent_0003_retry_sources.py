"""Keep retry attempts separate from immutable saved messages and failed jobs."""

import sqlalchemy as sa
from alembic import op

revision = "matteragent0003"
down_revision = "check0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_jobs", sa.Column("source_message_id", sa.String(64), nullable=True))
    op.add_column("agent_jobs", sa.Column("retry_of_job_id", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_agent_jobs_retry_of_job_id", "agent_jobs", ["retry_of_job_id"])


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM agent_jobs WHERE retry_of_job_id IS NOT NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade while agent retry history exists")
    op.drop_constraint("uq_agent_jobs_retry_of_job_id", "agent_jobs", type_="unique")
    op.drop_column("agent_jobs", "retry_of_job_id")
    op.drop_column("agent_jobs", "source_message_id")
