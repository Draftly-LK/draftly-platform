"""party_0002 — carry user_id on every party-owned row

Every table in the protected identity tier gets the tenant key so that every
query filters on user_id first rather than reaching a child row through its
parent (party-service.md §9).

Revision ID: party0002
Revises: party0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "party0002"
down_revision = "party0001"
branch_labels = None
depends_on = None

_CHILD_TABLES = (
    "identity_evidence",
    "beneficial_owners",
    "cdd_assessments",
    "screening_results",
)


def upgrade() -> None:
    for table in _CHILD_TABLES:
        op.add_column(table, sa.Column("user_id", sa.String(64), nullable=True))
        op.execute(
            f"UPDATE {table} SET user_id = parties.user_id "  # noqa: S608 - fixed table list
            f"FROM parties WHERE parties.id = {table}.party_id"
        )
        op.alter_column(table, "user_id", nullable=False)
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])

    op.add_column("screening_match_detail", sa.Column("user_id", sa.String(64), nullable=True))
    op.execute(
        "UPDATE screening_match_detail SET user_id = screening_results.user_id "
        "FROM screening_results "
        "WHERE screening_results.id = screening_match_detail.screening_result_id"
    )
    op.alter_column("screening_match_detail", "user_id", nullable=False)
    op.create_index(
        "ix_screening_match_detail_user_id", "screening_match_detail", ["user_id"]
    )

    op.create_index(
        "ix_identity_evidence_user_blind",
        "identity_evidence",
        ["user_id", "identifier_blind_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_identity_evidence_user_blind", table_name="identity_evidence")
    op.drop_index("ix_screening_match_detail_user_id", table_name="screening_match_detail")
    op.drop_column("screening_match_detail", "user_id")
    for table in _CHILD_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
