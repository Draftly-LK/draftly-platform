"""notarial_register_0001 — attestations, register, protocol, returns, outbox

Revision ID: notarial0001
Revises: audit0001
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "notarial0001"
down_revision = "obligations0001"
branch_labels = ("notarial_register",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attestations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("instrument_kind", sa.String(32), nullable=False),
        sa.Column("registration_regime", sa.String(32), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("export_id", sa.String(64), nullable=True),
        sa.Column("draft_version_id", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("attestation_clause_definition_id", sa.String(64), nullable=False),
        sa.Column("attestation_clause_version", sa.String(32), nullable=False),
        sa.Column("attestation_conditions_json", sa.Text, nullable=False),
        sa.Column("notary_user_id", sa.String(64), nullable=False),
        sa.Column("practising_jurisdiction_id", sa.String(64), nullable=False),
        sa.Column("registration_jurisdiction_id", sa.String(64), nullable=False),
        sa.Column("instrument_language", sa.String(16), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("place_of_execution", sa.String(255), nullable=False),
        sa.Column("executants_json", sa.Text, nullable=False),
        sa.Column("witnesses_json", sa.Text, nullable=False),
        sa.Column("consideration_recorded", sa.Boolean, nullable=True),
        sa.Column("external_reason", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_index("ix_attestations_user_id", "attestations", ["user_id"])
    op.create_index("ix_attestations_matter_id", "attestations", ["matter_id"])

    op.create_table(
        "register_serial_counters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("notary_user_id", sa.String(64), nullable=False),
        sa.Column("register_year", sa.Integer, nullable=False),
        sa.Column("last_serial", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("notary_user_id", "register_year", name="uq_register_serial_scope"),
    )

    op.create_table(
        "register_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("notary_user_id", sa.String(64), nullable=False),
        sa.Column("register_year", sa.Integer, nullable=False),
        sa.Column("serial_number", sa.Integer, nullable=False),
        sa.Column(
            "attestation_id",
            sa.String(64),
            sa.ForeignKey("attestations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("instrument_kind", sa.String(32), nullable=False),
        sa.Column("party_summary_ref", sa.String(128), nullable=False),
        sa.Column("consideration_ref", sa.String(128), nullable=True),
        sa.Column("folio_ref", sa.String(128), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "notary_user_id",
            "register_year",
            "serial_number",
            name="uq_register_entry_serial",
        ),
    )
    op.create_index("ix_register_entries_user_id", "register_entries", ["user_id"])

    op.create_table(
        "protocol_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "attestation_id",
            sa.String(64),
            sa.ForeignKey("attestations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("copy_kind", sa.String(32), nullable=False),
        sa.Column("storage_ref", sa.String(255), nullable=True),
        sa.Column("physical_location", sa.String(255), nullable=True),
        sa.Column("custodian_user_id", sa.String(64), nullable=False),
        sa.Column("issued_to", sa.String(64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_class", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
    )

    op.create_table(
        "registration_submissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "attestation_id",
            sa.String(64),
            sa.ForeignKey("attestations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("registry_id", sa.String(128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("defect_notes", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
    )

    op.create_table(
        "monthly_return_periods",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("notary_user_id", sa.String(64), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("instrument_ids_json", sa.Text, nullable=False),
        sa.Column("is_nil_return", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("components_json", sa.Text, nullable=False),
        sa.Column("component_states_json", sa.Text, nullable=False),
        sa.Column("certified_by", sa.String(64), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_index("ix_monthly_return_periods_user_id", "monthly_return_periods", ["user_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
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
    op.create_index("ix_outbox_events_user_id", "outbox_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_user_id", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_monthly_return_periods_user_id", table_name="monthly_return_periods")
    op.drop_table("monthly_return_periods")
    op.drop_table("registration_submissions")
    op.drop_table("protocol_records")
    op.drop_index("ix_register_entries_user_id", table_name="register_entries")
    op.drop_table("register_entries")
    op.drop_table("register_serial_counters")
    op.drop_index("ix_attestations_matter_id", table_name="attestations")
    op.drop_index("ix_attestations_user_id", table_name="attestations")
    op.drop_table("attestations")
