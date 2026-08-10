"""party_0001 — protected party tier tables

Revision ID: party0001
Revises: audit0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "party0001"
down_revision = "platform0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parties",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("party_kind", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(512), nullable=False),
        sa.Column("name_parts", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("former_names", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("registration_number", sa.String(128), nullable=True),
        sa.Column("nationality", sa.String(128), nullable=True),
        sa.Column("residency_status", sa.String(64), nullable=True),
        sa.Column("addresses", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("contact_points", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("risk_rating", sa.String(32), nullable=False, server_default="unassessed"),
        sa.Column("screening_status", sa.String(32), nullable=False, server_default="not-run"),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="standard",
        ),
        sa.Column("merged_into_party_id", sa.String(64), nullable=True),
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
    op.create_index("ix_parties_user_id", "parties", ["user_id"])
    op.create_index("ix_parties_user_display_name", "parties", ["user_id", "display_name"])
    op.create_index("ix_parties_user_registration", "parties", ["user_id", "registration_number"])

    op.create_table(
        "identity_evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "party_id",
            sa.String(64),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_kind", sa.String(64), nullable=False),
        sa.Column("identifier_ciphertext", sa.LargeBinary, nullable=False),
        sa.Column("identifier_blind_index", sa.String(64), nullable=False),
        sa.Column("identifier_last4", sa.String(4), nullable=False),
        sa.Column("issued_on", sa.Date, nullable=True),
        sa.Column("expires_on", sa.Date, nullable=True),
        sa.Column("issuing_authority", sa.String(255), nullable=True),
        sa.Column("document_id", sa.String(64), nullable=True),
        sa.Column("document_version_id", sa.String(64), nullable=True),
        sa.Column("evidence_span", postgresql.JSONB, nullable=True),
        sa.Column("verified_by", sa.String(64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="recorded"),
        sa.Column("supersedes_evidence_id", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_identity_evidence_party_id", "identity_evidence", ["party_id"])
    op.create_index(
        "ix_identity_evidence_blind_index",
        "identity_evidence",
        ["identifier_blind_index"],
    )

    op.create_table(
        "beneficial_owners",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "party_id",
            sa.String(64),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_party_id", sa.String(64), nullable=False),
        sa.Column("ownership_kind", sa.String(32), nullable=False),
        sa.Column("percentage", sa.Float, nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("determined_by", sa.String(64), nullable=False),
        sa.Column("determined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="recorded"),
    )
    op.create_index("ix_beneficial_owners_party_id", "beneficial_owners", ["party_id"])

    op.create_table(
        "cdd_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "party_id",
            sa.String(64),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matter_id", sa.String(64), nullable=True),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column("risk_factors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("assessed_by", sa.String(64), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_due_on", sa.Date, nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_cdd_assessments_party_id", "cdd_assessments", ["party_id"])

    op.create_table(
        "screening_results",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "party_id",
            sa.String(64),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("list_version", sa.String(64), nullable=False),
        sa.Column("provider_ref", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("match_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disposition_reason", sa.Text, nullable=True),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="restricted-compliance",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_screening_results_party_id", "screening_results", ["party_id"])

    op.create_table(
        "screening_match_detail",
        sa.Column(
            "screening_result_id",
            sa.String(64),
            sa.ForeignKey("screening_results.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider_payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("match_narrative", sa.Text, nullable=True),
        sa.Column("list_entry_ref", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("screening_match_detail")
    op.drop_table("screening_results")
    op.drop_table("cdd_assessments")
    op.drop_table("beneficial_owners")
    op.drop_table("identity_evidence")
    op.drop_table("parties")
