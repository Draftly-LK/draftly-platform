"""Preserve transaction scope and explicit legacy-unassigned eligibility.

Revision ID: verification0002
Revises: research0003
"""

import sqlalchemy as sa
from alembic import op

revision = "verification0002"
down_revision = "research0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extracted_facts", sa.Column("transaction_id", sa.String(64), nullable=True))
    op.add_column("extracted_facts", sa.Column("scope_status", sa.String(32), nullable=False, server_default="legacy-unassigned"))
    op.add_column("extracted_facts", sa.Column("evidence_stale", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("extracted_facts", "evidence_stale")
    op.drop_column("extracted_facts", "scope_status")
    op.drop_column("extracted_facts", "transaction_id")
