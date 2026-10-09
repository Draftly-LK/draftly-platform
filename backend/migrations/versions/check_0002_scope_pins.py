"""Add explicit check and issue scope pins; preserve legacy history unassigned."""

import sqlalchemy as sa
from alembic import op

revision = "check0002"
down_revision = "task0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("cross_document_checks", "legal_issues"):
        op.add_column(table, sa.Column("transaction_id", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("subject_id", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("association_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table in ("cross_document_checks", "legal_issues"):
        if (
            op.get_bind()
            .execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE transaction_id IS NOT NULL"))
            .scalar_one()
        ):
            raise RuntimeError("Cannot discard scoped check or issue history.")
    for table in ("cross_document_checks", "legal_issues"):
        for column in ("association_version", "subject_id", "transaction_id"):
            op.drop_column(table, column)
