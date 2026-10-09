"""Retain confirmed action results independently of the immutable proposal."""

import sqlalchemy as sa
from alembic import op

revision = "matteragent0004"
down_revision = "matteragent0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_pending_actions", sa.Column("result", sa.JSON(), nullable=False, server_default="{}")
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM agent_pending_actions WHERE state IN ('executed','declined','stale','failed') LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("Cannot downgrade while confirmed-action history exists")
    op.drop_column("agent_pending_actions", "result")
