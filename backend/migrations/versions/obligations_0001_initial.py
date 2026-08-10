"""obligations_0001 — obligations, lawyer confirmations, reminders, outbox stub

Revision ID: obligations0001
Revises: audit0001
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "obligations0001"
down_revision = "notification0001"
branch_labels = ("obligations",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "obligations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=True),
        sa.Column("owner_user_id", sa.String(64), nullable=True),
        sa.Column("obligation_type", sa.String(64), nullable=False),
        sa.Column("obligation_class", sa.String(64), nullable=False),
        sa.Column("label_key", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("source_version", sa.String(32), nullable=True),
        sa.Column("legal_authority_ref", sa.String(128), nullable=True),
        sa.Column("trigger_type", sa.String(64), nullable=False),
        sa.Column("trigger_id", sa.String(64), nullable=True),
        sa.Column("trigger_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("calculation_rule_id", sa.String(64), nullable=True),
        sa.Column("calculation_version", sa.String(32), nullable=True),
        sa.Column("calculation_explanation", sa.Text, nullable=True),
        sa.Column("hardness", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assignee_user_id", sa.String(64), nullable=False),
        sa.Column("backup_assignee_user_id", sa.String(64), nullable=True),
        sa.Column("recurrence_rule", sa.String(255), nullable=True),
        sa.Column("reminder_policy_id", sa.String(64), nullable=False),
        sa.Column("escalation_policy_id", sa.String(64), nullable=True),
        sa.Column("confidentiality_level", sa.String(32), nullable=False),
        sa.Column("completion_evidence_ref", sa.String(128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.String(64), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.String(64), nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_obligations_org_assignee", "obligations", ["organisation_id", "assignee_user_id"])
    op.create_index("ix_obligations_org_matter", "obligations", ["organisation_id", "matter_id"])
    op.create_index("ix_obligations_org_due", "obligations", ["organisation_id", "due_at"])

    op.create_table(
        "lawyer_confirmations",
        sa.Column(
            "obligation_id",
            sa.String(64),
            sa.ForeignKey("obligations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confirmed_by", sa.String(64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("original_due_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "reminder_occurrences",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column(
            "obligation_id",
            sa.String(64),
            sa.ForeignKey("obligations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_user_id", sa.String(64), nullable=False),
        sa.Column("reminder_type", sa.String(32), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_id", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "obligation_id",
            "recipient_user_id",
            "reminder_type",
            name="uq_reminder_occurrence",
        ),
    )

    op.create_table(
        "obligation_outbox_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("obligation_outbox_events")
    op.drop_table("reminder_occurrences")
    op.drop_table("lawyer_confirmations")
    op.drop_index("ix_obligations_org_due", table_name="obligations")
    op.drop_index("ix_obligations_org_matter", table_name="obligations")
    op.drop_index("ix_obligations_org_assignee", table_name="obligations")
    op.drop_table("obligations")
