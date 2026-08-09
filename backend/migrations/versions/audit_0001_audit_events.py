"""audit_0001 — append-only audit events table

Revision ID: audit0001
Revises: auth0001
Create Date: 2026-08-09

Depends on the auth migration (user_id is in every event row).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "audit0001"
down_revision = "auth0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=True),
        sa.Column("actor", sa.String(64), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("before_ref", sa.Text, nullable=True),
        sa.Column("after_ref", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("causation_id", sa.String(64), nullable=True),
        sa.Column("prev_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_audit_events_user_timestamp",
        "audit_events",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_events_user_matter",
        "audit_events",
        ["user_id", "matter_id"],
    )


def downgrade() -> None:
    op.drop_table("audit_events")
