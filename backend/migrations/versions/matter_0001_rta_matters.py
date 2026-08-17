"""matter_0001 — RTA matters, classification history, and intake answers

Revision ID: matter0001
Revises: audit0001
Create Date: 2026-08-16

Creates: matters, matter_classifications, matter_intake_answers

Non-destructive by design. ``matters.legacy_matter_type`` preserves the retired
M2 vocabulary verbatim so a migrated record stays readable, and
matter_classifications is append-only so the rule set a matter was worked under
remains reconstructible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "matter0001"
down_revision = "audit0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(128), nullable=False),
        sa.Column("client_reference", sa.String(128), nullable=True),
        sa.Column("responsible_lawyer_id", sa.String(64), nullable=False),
        sa.Column("regime_id", sa.String(64), nullable=False),
        sa.Column("family_id", sa.String(64), nullable=True),
        sa.Column("subtype_id", sa.String(128), nullable=True),
        sa.Column("subtype_decision_status", sa.String(32), nullable=False),
        sa.Column("legacy_matter_type", sa.String(32), nullable=True),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("rta_state", sa.String(32), nullable=False),
        sa.Column("automation_scope", sa.String(32), nullable=False),
        sa.Column("title_status", sa.String(32), nullable=False),
        sa.Column("parcel_kind", sa.String(40), nullable=False),
        sa.Column("disposition_scope", sa.String(40), nullable=False),
        sa.Column("dispute_stage", sa.String(40), nullable=False),
        sa.Column("instrument_language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("declared_legal_basis", sa.Text, nullable=True),
        sa.Column("local_authority_id", sa.String(64), nullable=True),
        sa.Column("active_checklist_snapshot_id", sa.String(64), nullable=True),
        sa.Column("party_contexts", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "activated_conditional_module_ids", sa.JSON, nullable=False, server_default="[]"
        ),
        sa.Column(
            "suppressed_conditional_module_ids", sa.JSON, nullable=False, server_default="[]"
        ),
        sa.Column(
            "automation_exclusion_reason_keys", sa.JSON, nullable=False, server_default="[]"
        ),
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
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "reference", name="uq_matters_user_reference"),
    )
    op.create_index("ix_matters_user_state", "matters", ["user_id", "rta_state"])
    op.create_index("ix_matters_user_lifecycle", "matters", ["user_id", "lifecycle_status"])

    op.create_table(
        "matter_classifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "matter_id",
            sa.String(64),
            sa.ForeignKey("matters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("regime_id", sa.String(64), nullable=False),
        sa.Column("family_id", sa.String(64), nullable=True),
        sa.Column("subtype_id", sa.String(128), nullable=True),
        sa.Column("subtype_decision_status", sa.String(32), nullable=False),
        sa.Column("title_status", sa.String(32), nullable=False),
        sa.Column("parcel_kind", sa.String(40), nullable=False),
        sa.Column("disposition_scope", sa.String(40), nullable=False),
        sa.Column("property_characteristics", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("execution_circumstances", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("rule_pack_version", sa.String(32), nullable=False),
        sa.Column("changed_by", sa.String(64), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.UniqueConstraint("matter_id", "version", name="uq_matter_classification_version"),
    )
    op.create_index(
        "ix_matter_classifications_user_matter",
        "matter_classifications",
        ["user_id", "matter_id"],
    )

    op.create_table(
        "matter_intake_answers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "matter_id",
            sa.String(64),
            sa.ForeignKey("matters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_definition_id", sa.String(64), nullable=False),
        sa.Column("value", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("inferred_from_fact_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("answered_by", sa.String(64), nullable=True),
        sa.Column("answer_reason", sa.Text, nullable=True),
        sa.Column("supersedes_id", sa.String(64), nullable=True),
        sa.Column("lawyer_confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_intake_answers_user_matter", "matter_intake_answers", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_intake_answers_matter_question",
        "matter_intake_answers",
        ["matter_id", "question_definition_id"],
    )


def downgrade() -> None:
    op.drop_table("matter_intake_answers")
    op.drop_table("matter_classifications")
    op.drop_index("ix_matters_user_lifecycle", table_name="matters")
    op.drop_index("ix_matters_user_state", table_name="matters")
    op.drop_table("matters")
