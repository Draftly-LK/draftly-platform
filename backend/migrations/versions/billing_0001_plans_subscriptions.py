"""billing_0001 — plan catalogue, subscriptions, usage, webhook events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "billing0001"
down_revision = "audit0001"
branch_labels = ("billing",)
depends_on = None

# Synthetic seeded plan ids (deterministic).
_PLAN_TRIAL = "plan_trial_v1"
_PLAN_SOLO = "plan_solo_v1"


def upgrade() -> None:
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("family", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("price_minor_units", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "plan_version_id",
            sa.String(64),
            sa.ForeignKey("plan_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(128), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("plan_version_id", "feature_key", name="uq_plan_entitlement_key"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_version_id",
            sa.String(64),
            sa.ForeignKey("plan_versions.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_customer_id", sa.String(128), nullable=True),
        sa.Column("provider_subscription_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_state_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", name="uq_subscription_user"),
    )
    op.create_index(
        "ix_subscriptions_provider_sub",
        "subscriptions",
        ["provider_subscription_id"],
    )

    op.create_table(
        "usage_ledger_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operation_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "metric", "operation_id", name="uq_usage_ledger_operation"
        ),
    )

    op.create_table(
        "usage_aggregates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "user_id", "metric", "period_start", "period_end", name="uq_usage_aggregate_period"
        ),
    )

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_state", sa.String(16), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_billing_webhook_provider_event"
        ),
    )

    plan_versions = sa.table(
        "plan_versions",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("family", sa.String),
        sa.column("name", sa.String),
        sa.column("version", sa.Integer),
        sa.column("billing_interval", sa.String),
        sa.column("currency", sa.String),
        sa.column("price_minor_units", sa.Integer),
        sa.column("state", sa.String),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("effective_to", sa.DateTime(timezone=True)),
    )
    plan_entitlements = sa.table(
        "plan_entitlements",
        sa.column("id", sa.String),
        sa.column("plan_version_id", sa.String),
        sa.column("feature_key", sa.String),
        sa.column("limit_value", sa.Integer),
        sa.column("enabled", sa.Boolean),
    )

    op.bulk_insert(
        plan_versions,
        [
            {
                "id": _PLAN_TRIAL,
                "code": "trial-v1",
                "family": "trial",
                "name": "Trial (synthetic)",
                "version": 1,
                "billing_interval": "trial",
                "currency": "LKR",
                "price_minor_units": 0,
                "state": "active",
                "effective_from": "2026-01-01T00:00:00+00:00",
                "effective_to": None,
            },
            {
                "id": _PLAN_SOLO,
                "code": "solo-v1",
                "family": "solo",
                "name": "Solo (synthetic)",
                "version": 1,
                "billing_interval": "monthly",
                "currency": "LKR",
                "price_minor_units": 499900,
                "state": "active",
                "effective_from": "2026-01-01T00:00:00+00:00",
                "effective_to": None,
            },
        ],
    )

    trial_entitlements = [
        ("ent_trial_dp", "document_processing.enabled", None, True),
        ("ent_trial_research", "research.enabled", None, True),
        ("ent_trial_draft", "drafting.enabled", None, True),
        ("ent_trial_export", "export.enabled", None, True),
        ("ent_trial_matters", "active_matters.max", 2, True),
        ("ent_trial_pages", "document_pages.monthly", 50, True),
    ]
    solo_entitlements = [
        ("ent_solo_dp", "document_processing.enabled", None, True),
        ("ent_solo_research", "research.enabled", None, True),
        ("ent_solo_draft", "drafting.enabled", None, True),
        ("ent_solo_export", "export.enabled", None, True),
        ("ent_solo_matters", "active_matters.max", 25, True),
        ("ent_solo_pages", "document_pages.monthly", 500, True),
    ]

    op.bulk_insert(
        plan_entitlements,
        [
            {
                "id": eid,
                "plan_version_id": _PLAN_TRIAL,
                "feature_key": key,
                "limit_value": limit,
                "enabled": enabled,
            }
            for eid, key, limit, enabled in trial_entitlements
        ]
        + [
            {
                "id": eid,
                "plan_version_id": _PLAN_SOLO,
                "feature_key": key,
                "limit_value": limit,
                "enabled": enabled,
            }
            for eid, key, limit, enabled in solo_entitlements
        ],
    )


def downgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("usage_aggregates")
    op.drop_table("usage_ledger_entries")
    op.drop_table("subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_table("plan_versions")
