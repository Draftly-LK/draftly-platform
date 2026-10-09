"""Pin extraction and reviewed evidence to append-only document interpretations."""

import sqlalchemy as sa
from alembic import op

revision = "document0003"
down_revision = "matter0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_file_processing_runs",
        sa.Column("kind", sa.String(32), nullable=False, server_default="source"),
    )
    op.add_column(
        "detected_documents", sa.Column("refresh_failure_reason", sa.String(64), nullable=True)
    )
    op.add_column(
        "detected_documents",
        sa.Column("interpretation_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "detected_documents",
        sa.Column("extraction_state", sa.String(32), nullable=False, server_default="current"),
    )
    op.add_column(
        "detected_documents", sa.Column("latest_refresh_run_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "processing_logical_documents",
        sa.Column("interpretation_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "processing_logical_documents", sa.Column("page_sources", sa.JSON(), nullable=True)
    )
    op.add_column(
        "processing_candidate_fields", sa.Column("source_file_id", sa.String(64), nullable=True)
    )
    op.add_column(
        "evidence_references", sa.Column("interpretation_generation", sa.Integer(), nullable=True)
    )
    op.create_table(
        "document_interpretations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "detected_document_id",
            sa.String(64),
            sa.ForeignKey("detected_documents.id"),
            nullable=False,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.String(128), nullable=True),
        sa.Column("fragments", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "detected_document_id", "generation", name="uq_document_interpretation_generation"
        ),
    )


def downgrade() -> None:
    # Older readers cannot interpret these pins. Refuse a lossy rollback after
    # corrections instead of making historical candidates authoritative again.
    changed = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM detected_documents WHERE interpretation_generation > 1) "
                "OR EXISTS (SELECT 1 FROM processing_logical_documents WHERE page_sources IS NOT NULL)"
            )
        )
        .scalar()
    )
    if changed:
        raise RuntimeError(
            "Cannot downgrade document interpretations after corrections or refresh."
        )
    op.drop_column("source_file_processing_runs", "kind")
    op.drop_column("detected_documents", "refresh_failure_reason")
    op.drop_table("document_interpretations")
    op.drop_column("evidence_references", "interpretation_generation")
    op.drop_column("processing_candidate_fields", "source_file_id")
    op.drop_column("processing_logical_documents", "page_sources")
    op.drop_column("processing_logical_documents", "interpretation_generation")
    op.drop_column("detected_documents", "latest_refresh_run_id")
    op.drop_column("detected_documents", "extraction_state")
    op.drop_column("detected_documents", "interpretation_generation")
