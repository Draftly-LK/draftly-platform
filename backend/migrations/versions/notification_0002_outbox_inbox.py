"""notification_0002 — outbox, inbox, provider events, delivery hardening.

Revision ID: notification0002
Revises: notification0001
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "notification0002"
down_revision = "notification0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Shared outbox is created in platform0001; this revision only hardens
    # notification delivery / inbox / provider event tables.
    op.add_column(
        "notification_deliveries",
        sa.Column("subject_ref", sa.String(64), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE notification_deliveries SET subject_ref = obligation_id "
            "WHERE subject_ref IS NULL"
        )
    )
    op.alter_column("notification_deliveries", "subject_ref", nullable=False)
    op.alter_column("notification_deliveries", "obligation_id", nullable=True)
    op.add_column(
        "notification_deliveries",
        sa.Column("provider_state", sa.String(32), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("failure_class", sa.String(32), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
    )
    op.alter_column(
        "notification_deliveries",
        "reminder_type",
        type_=sa.String(128),
        existing_type=sa.String(64),
    )

    op.drop_constraint("uq_notif_delivery_idempotent", "notification_deliveries", type_="unique")
    op.create_unique_constraint(
        "uq_notif_delivery_idempotent",
        "notification_deliveries",
        ["organisation_id", "subject_ref", "recipient_user_id", "reminder_type", "channel"],
    )
    op.create_index(
        "ix_notif_delivery_provider_message",
        "notification_deliveries",
        ["provider_message_id"],
    )

    op.create_table(
        "notification_consumed_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("event_id", name="uq_notif_consumed_event_id"),
    )

    op.create_table(
        "notification_provider_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column("delivery_id", sa.String(64), nullable=True),
        sa.Column("organisation_id", sa.String(64), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_notif_provider_event"),
    )
    op.create_index(
        "ix_notif_provider_event_message",
        "notification_provider_events",
        ["provider_message_id"],
    )

    op.create_table(
        "notification_template_deployments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("template_key", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("source_version", sa.String(32), nullable=False),
        sa.Column("provider_template_id", sa.String(128), nullable=False),
        sa.Column("published_by", sa.String(64), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "environment", "template_key", "locale", name="uq_notif_template_deployment"
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_template_deployments")
    op.drop_table("notification_provider_events")
    op.drop_table("notification_consumed_events")
    op.drop_index("ix_notif_delivery_provider_message", table_name="notification_deliveries")
    op.drop_constraint("uq_notif_delivery_idempotent", "notification_deliveries", type_="unique")
    op.create_unique_constraint(
        "uq_notif_delivery_idempotent",
        "notification_deliveries",
        ["organisation_id", "obligation_id", "recipient_user_id", "reminder_type", "channel"],
    )
    op.drop_column("notification_deliveries", "correlation_id")
    op.drop_column("notification_deliveries", "failure_class")
    op.drop_column("notification_deliveries", "provider_state")
    op.drop_column("notification_deliveries", "subject_ref")
    op.alter_column("notification_deliveries", "obligation_id", nullable=False)
