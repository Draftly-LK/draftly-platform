"""notification_0001 — preferences and delivery tables.

Revision ID: notification0001
Revises: audit0001
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "notification0001"
down_revision = "party0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("quiet_hours_start", sa.String(8), nullable=True),
        sa.Column("quiet_hours_end", sa.String(8), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "user_id",
            "channel",
            name="uq_notif_pref_user_channel",
        ),
    )
    op.create_index(
        "ix_notification_preferences_org_user",
        "notification_preferences",
        ["organisation_id", "user_id"],
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("source_event_id", sa.String(64), nullable=False),
        sa.Column("obligation_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=True),
        sa.Column("recipient_user_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("reminder_type", sa.String(64), nullable=False),
        sa.Column("obligation_class", sa.String(64), nullable=False),
        sa.Column("urgency", sa.String(32), nullable=False),
        sa.Column("confidentiality_level", sa.String(64), nullable=False),
        sa.Column("template_key", sa.String(128), nullable=False),
        sa.Column("delivery_policy_key", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("preview_title", sa.String(255), nullable=False, server_default=""),
        sa.Column("preview_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "obligation_id",
            "recipient_user_id",
            "reminder_type",
            "channel",
            name="uq_notif_delivery_idempotent",
        ),
        sa.UniqueConstraint(
            "source_event_id",
            "channel",
            name="uq_notif_delivery_source_channel",
        ),
    )
    op.create_index(
        "ix_notif_delivery_recipient_created",
        "notification_deliveries",
        ["organisation_id", "recipient_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_preferences")
