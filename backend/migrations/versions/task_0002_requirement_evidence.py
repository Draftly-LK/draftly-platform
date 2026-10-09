"""Pin requirement links and retain original-inspection history without inventing bindings."""

import sqlalchemy as sa
from alembic import op

revision = "task0002"
down_revision = "document0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("document_version", "interpretation_generation"):
        op.add_column("checklist_satisfaction_links", sa.Column(name, sa.Integer()))
    op.add_column(
        "checklist_satisfaction_links",
        sa.Column("originals", sa.JSON(), nullable=False, server_default="[]"),
    )
    for name in ("original_inspection_sources", "inspection_history"):
        op.add_column(
            "checklist_items", sa.Column(name, sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(
            sa.text("""SELECT COUNT(*) FROM checklist_satisfaction_links
        WHERE document_version IS NOT NULL OR interpretation_generation IS NOT NULL
        OR json_array_length(originals) > 0""")
        )
        .scalar_one()
    )
    inspections = (
        op.get_bind()
        .execute(
            sa.text("""SELECT COUNT(*) FROM checklist_items
        WHERE json_array_length(original_inspection_sources) > 0
        OR json_array_length(inspection_history) > 0""")
        )
        .scalar_one()
    )
    if count or inspections:
        raise RuntimeError("Cannot discard pinned requirement evidence or inspection history.")
    for name in ("inspection_history", "original_inspection_sources"):
        op.drop_column("checklist_items", name)
    for name in ("originals", "interpretation_generation", "document_version"):
        op.drop_column("checklist_satisfaction_links", name)
