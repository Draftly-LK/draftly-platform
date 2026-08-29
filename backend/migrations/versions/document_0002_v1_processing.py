"""document_0002: persisted V1 pages, groups, derivatives, and review candidates."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "document0002"
down_revision = "merge0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_processing_pages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "processing_run_id",
            sa.String(64),
            sa.ForeignKey("source_file_processing_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id", sa.String(64), sa.ForeignKey("source_files.id"), nullable=False
        ),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("original_width", sa.Integer, nullable=False),
        sa.Column("original_height", sa.Integer, nullable=False),
        sa.Column("corrected_width", sa.Integer, nullable=False),
        sa.Column("corrected_height", sa.Integer, nullable=False),
        sa.Column("detected_orientation", sa.Integer, nullable=True),
        sa.Column("correction_degrees", sa.Integer, nullable=False),
        sa.Column("rotation_status", sa.String(32), nullable=False),
        sa.Column("rotation_vote_share", sa.Float, nullable=False),
        sa.Column("usable_word_count", sa.Integer, nullable=False),
        sa.Column("detected_languages", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("classification_type_id", sa.String(128), nullable=False),
        sa.Column("suggested_name", sa.String(255), nullable=True),
        sa.Column("starts_new_document", sa.Boolean, nullable=False),
        sa.Column("classification_confidence", sa.Float, nullable=False),
        sa.Column("corrected_webp_key", sa.String(768), nullable=False),
        sa.Column("corrected_webp_version", sa.String(128), nullable=False),
        sa.Column("corrected_ocr_key", sa.String(768), nullable=False),
        sa.Column("corrected_ocr_version", sa.String(128), nullable=False),
        sa.Column("plain_text_key", sa.String(768), nullable=False),
        sa.Column("plain_text_version", sa.String(128), nullable=False),
        sa.CheckConstraint("page_no >= 1", name="ck_processing_page_number_positive"),
    )
    op.create_index(
        "ix_processing_pages_user_run",
        "document_processing_pages",
        ["user_id", "processing_run_id"],
    )
    op.create_index(
        "ix_processing_pages_source",
        "document_processing_pages",
        ["user_id", "source_file_id", "page_no"],
    )

    op.create_table(
        "processing_logical_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "processing_run_id",
            sa.String(64),
            sa.ForeignKey("source_file_processing_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id", sa.String(64), sa.ForeignKey("source_files.id"), nullable=False
        ),
        sa.Column("detected_document_id", sa.String(64), nullable=True),
        sa.Column("document_index", sa.Integer, nullable=False),
        sa.Column("type_id", sa.String(128), nullable=False),
        sa.Column("suggested_name", sa.String(255), nullable=True),
        sa.Column("page_numbers", sa.JSON, nullable=False),
    )
    op.create_index(
        "ix_logical_documents_user_run",
        "processing_logical_documents",
        ["user_id", "processing_run_id"],
    )

    op.create_table(
        "processing_candidate_fields",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "logical_document_id",
            sa.String(64),
            sa.ForeignKey("processing_logical_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("candidate_value", sa.Text, nullable=False),
        sa.Column("edited_value", sa.Text, nullable=True),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("model_reported_confidence", sa.Float, nullable=False),
        sa.Column("review_state", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_fact_id",
            sa.String(64),
            sa.ForeignKey("extracted_facts.id"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint(
            "(review_state = 'unverified' AND approved_by IS NULL AND approved_at IS NULL "
            "AND approved_fact_id IS NULL) OR (review_state = 'approved' "
            "AND approved_by IS NOT NULL AND approved_at IS NOT NULL "
            "AND approved_fact_id IS NOT NULL)",
            name="ck_candidate_review_state_valid",
        ),
    )
    op.create_index(
        "ix_candidate_fields_user_document",
        "processing_candidate_fields",
        ["user_id", "logical_document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_fields_user_document", table_name="processing_candidate_fields")
    op.drop_table("processing_candidate_fields")
    op.drop_index("ix_logical_documents_user_run", table_name="processing_logical_documents")
    op.drop_table("processing_logical_documents")
    op.drop_index("ix_processing_pages_source", table_name="document_processing_pages")
    op.drop_index("ix_processing_pages_user_run", table_name="document_processing_pages")
    op.drop_table("document_processing_pages")
