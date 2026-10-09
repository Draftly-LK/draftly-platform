"""Append page dispositions and pin refresh runs to their exact interpretation."""

import sqlalchemy as sa
from alembic import op

revision = "document0004"
down_revision = "document0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_file_processing_runs", sa.Column("detected_document_id", sa.String(64)))
    op.add_column(
        "source_file_processing_runs", sa.Column("interpretation_generation", sa.Integer())
    )
    op.create_table(
        "document_page_dispositions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "source_file_id", sa.String(64), sa.ForeignKey("source_files.id"), nullable=False
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "source_file_id",
            "page_number",
            "source_version",
            name="uq_document_page_disposition_version",
        ),
        sa.CheckConstraint("page_number >= 1", name="ck_page_disposition_page"),
        sa.CheckConstraint(
            "disposition IN ('blank', 'unsupported', 'review_required')",
            name="ck_page_disposition_status",
        ),
    )
    op.create_index(
        "ix_document_page_dispositions_scope",
        "document_page_dispositions",
        ["user_id", "matter_id", "source_file_id"],
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM document_page_dispositions) OR EXISTS (SELECT 1 FROM source_file_processing_runs WHERE detected_document_id IS NOT NULL)"))
        .scalar()
    ):
        raise RuntimeError(
            "Cannot downgrade recorded page dispositions or interpretation runs without losing review history."
        )
    op.drop_table("document_page_dispositions")
    op.drop_column("source_file_processing_runs", "interpretation_generation")
    op.drop_column("source_file_processing_runs", "detected_document_id")
