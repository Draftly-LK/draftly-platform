"""document_0001 — immutable source files, detected documents, fragments, runs

Revision ID: document0001
Revises: verification0001
Create Date: 2026-08-16

Creates: source_files, detected_documents, document_fragments,
source_file_processing_runs

``(user_id, matter_id, sha256)`` is indexed but deliberately NOT unique. The
workflow spec §6.3 requires a repeated upload to be *detected* and shown to the
lawyer with both copies retained; a unique constraint would refuse the second
upload instead, which is the one behaviour the spec rules out.

The check constraints mirror ``modules/document/infrastructure/orm.py`` so the
database enforces the same invariants as the ORM: a rejected file always states
a reason, no state that implies stored bytes can exist without a storage object,
and a fragment can never claim page 0 or a backwards range.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "document0001"
down_revision = "verification0001"
branch_labels = None
depends_on = None

_STORED_STATES = "'STORED', 'PROCESSING', 'PROCESSED', 'PROCESSING_FAILED', 'SUPERSEDED'"


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("byte_length", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        # Empty exactly when quarantine refused the bytes: nothing was stored,
        # but the refusal is still a record the lawyer can act on.
        sa.Column("storage_object_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("storage_object_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("upload_actor_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("detected_languages", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("retention_class", sa.String(64), nullable=False),
        sa.Column("failure_reason", sa.String(32), nullable=True),
        sa.Column("failure_explanation_key", sa.String(128), nullable=True),
        sa.Column("superseded_by_source_file_id", sa.String(64), nullable=True),
        # A cleaned or rotated copy is a new row pointing back at its original;
        # source bytes are never rewritten (§10.2).
        sa.Column("derived_from_source_file_id", sa.String(64), nullable=True),
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
        sa.CheckConstraint("byte_length >= 0", name="ck_source_file_byte_length_nonnegative"),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count >= 1", name="ck_source_file_page_count_positive"
        ),
        sa.CheckConstraint(
            "(state <> 'REJECTED') OR "
            "(failure_reason IS NOT NULL AND failure_explanation_key IS NOT NULL)",
            name="ck_source_file_rejection_states_reason",
        ),
        sa.CheckConstraint(
            f"(state NOT IN ({_STORED_STATES})) OR storage_object_key <> ''",
            name="ck_source_file_stored_states_have_object",
        ),
        sa.CheckConstraint(
            "(state <> 'SUPERSEDED') OR superseded_by_source_file_id IS NOT NULL",
            name="ck_source_file_superseded_names_successor",
        ),
    )
    op.create_index("ix_source_files_user_matter", "source_files", ["user_id", "matter_id"])
    op.create_index(
        "ix_source_files_user_matter_sha256",
        "source_files",
        ["user_id", "matter_id", "sha256"],
    )

    op.create_table(
        "detected_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("class_id", sa.String(128), nullable=True),
        sa.Column("class_confidence", sa.Float, nullable=True),
        sa.Column("class_status", sa.String(32), nullable=False),
        sa.Column("language_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("issuer", sa.String(255), nullable=True),
        sa.Column("issue_or_execution_date_fact_id", sa.String(64), nullable=True),
        sa.Column("version_relationship", sa.String(32), nullable=True),
        sa.Column("duplicate_of_detected_document_id", sa.String(64), nullable=True),
        sa.Column("boundary_status", sa.String(32), nullable=False),
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
        sa.CheckConstraint(
            "class_confidence IS NULL OR (class_confidence >= 0 AND class_confidence <= 1)",
            name="ck_detected_document_class_confidence_range",
        ),
        # §6.3: UNIDENTIFIED and REJECTED are the only classless states.
        sa.CheckConstraint(
            "(class_status NOT IN ('AI_ORGANIZED', 'REVIEW_REQUIRED', 'LAWYER_CONFIRMED')) OR "
            "class_id IS NOT NULL",
            name="ck_detected_document_filed_has_class",
        ),
    )
    op.create_index(
        "ix_detected_documents_user_matter", "detected_documents", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_detected_documents_class",
        "detected_documents",
        ["user_id", "matter_id", "class_status"],
    )

    op.create_table(
        "document_fragments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "detected_document_id",
            sa.String(64),
            sa.ForeignKey("detected_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.String(64),
            sa.ForeignKey("source_files.id"),
            nullable=False,
        ),
        sa.Column("page_start", sa.Integer, nullable=False),
        sa.Column("page_end", sa.Integer, nullable=False),
        sa.Column("order_in_document", sa.Integer, nullable=False, server_default="0"),
        # NULL for a range a human drew: a lawyer's decision is not a model score.
        sa.Column("boundary_confidence", sa.Float, nullable=True),
        sa.Column("boundary_status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "page_start >= 1 AND page_end >= page_start", name="ck_document_fragment_page_range"
        ),
        sa.CheckConstraint(
            "boundary_confidence IS NULL OR "
            "(boundary_confidence >= 0 AND boundary_confidence <= 1)",
            name="ck_document_fragment_confidence_range",
        ),
    )
    op.create_index(
        "ix_document_fragments_user_matter", "document_fragments", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_document_fragments_document", "document_fragments", ["detected_document_id"]
    )
    op.create_index("ix_document_fragments_source", "document_fragments", ["source_file_id"])

    op.create_table(
        "source_file_processing_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "source_file_id",
            sa.String(64),
            sa.ForeignKey("source_files.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reasons", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("pages_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_extraction_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False, server_default=""),
        sa.CheckConstraint(
            "pages_processed >= 0 AND ai_extraction_calls >= 0",
            name="ck_processing_run_meters_nonnegative",
        ),
    )
    op.create_index(
        "ix_processing_runs_user_matter",
        "source_file_processing_runs",
        ["user_id", "matter_id"],
    )
    op.create_index("ix_processing_runs_source", "source_file_processing_runs", ["source_file_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_runs_source", table_name="source_file_processing_runs")
    op.drop_index("ix_processing_runs_user_matter", table_name="source_file_processing_runs")
    op.drop_table("source_file_processing_runs")
    op.drop_index("ix_document_fragments_source", table_name="document_fragments")
    op.drop_index("ix_document_fragments_document", table_name="document_fragments")
    op.drop_index("ix_document_fragments_user_matter", table_name="document_fragments")
    op.drop_table("document_fragments")
    op.drop_index("ix_detected_documents_class", table_name="detected_documents")
    op.drop_index("ix_detected_documents_user_matter", table_name="detected_documents")
    op.drop_table("detected_documents")
    op.drop_index("ix_source_files_user_matter_sha256", table_name="source_files")
    op.drop_index("ix_source_files_user_matter", table_name="source_files")
    op.drop_table("source_files")
