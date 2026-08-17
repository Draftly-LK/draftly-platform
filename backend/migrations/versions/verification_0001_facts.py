"""verification_0001 — evidence references, fact versions, and review decisions

Revision ID: verification0001
Revises: task0001
Create Date: 2026-08-16

Creates: evidence_references, extracted_facts, review_decisions

Facts are append-only. Correcting one inserts a new row and sets the prior row's
superseded_by_fact_id, so the original extraction result stays recoverable after
an approval (workflow spec §6.5, plan §5.3 invariant 2).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "verification0001"
down_revision = "task0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_references",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("source_file_id", sa.String(64), nullable=False),
        sa.Column("detected_document_id", sa.String(64), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("bounding_box", sa.JSON, nullable=True),
        sa.Column("text_span", sa.Text, nullable=True),
        sa.Column("region_type", sa.String(32), nullable=True),
        sa.Column("extraction_run_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("page_number >= 1", name="ck_evidence_page_number_one_based"),
    )
    op.create_index(
        "ix_evidence_references_user_matter", "evidence_references", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_evidence_references_source", "evidence_references", ["source_file_id", "page_number"]
    )

    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("fact_type_id", sa.String(128), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("value", sa.JSON, nullable=True),
        sa.Column("normalized_value", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model_reported_confidence", sa.Float, nullable=True),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("derivation_kind", sa.String(64), nullable=True),
        sa.Column("derivation_input_fact_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("derivation_formula_version", sa.String(32), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_decision_id", sa.String(64), nullable=True),
        sa.Column("supersedes_fact_id", sa.String(64), nullable=True),
        sa.Column("superseded_by_fact_id", sa.String(64), nullable=True),
        sa.Column("locked_by_form_id", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # A lawyer-confirmed fact has a named reviewer and a time. Nothing may
        # reach that status anonymously (§6.4).
        sa.CheckConstraint(
            "status NOT IN ('LAWYER_CONFIRMED', 'LOCKED_FOR_FORM') OR "
            "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_extracted_fact_confirmation_requires_reviewer",
        ),
    )
    op.create_index(
        "ix_extracted_facts_user_matter", "extracted_facts", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_extracted_facts_matter_type", "extracted_facts", ["matter_id", "fact_type_id"]
    )
    op.create_index(
        "ix_extracted_facts_live",
        "extracted_facts",
        ["matter_id", "fact_type_id", "superseded_by_fact_id"],
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("previous_value", sa.JSON, nullable=True),
        sa.Column("new_value", sa.JSON, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("reviewer_id", sa.String(64), nullable=False),
        sa.Column("reviewer_role", sa.String(40), nullable=False),
        sa.Column("human_decision", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_review_decisions_user_matter", "review_decisions", ["user_id", "matter_id"]
    )
    op.create_index("ix_review_decisions_target", "review_decisions", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("review_decisions")
    op.drop_index("ix_extracted_facts_live", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_matter_type", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_user_matter", table_name="extracted_facts")
    op.drop_table("extracted_facts")
    op.drop_index("ix_evidence_references_source", table_name="evidence_references")
    op.drop_index("ix_evidence_references_user_matter", table_name="evidence_references")
    op.drop_table("evidence_references")
