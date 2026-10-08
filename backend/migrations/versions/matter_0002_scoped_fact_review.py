"""Matter scope references and canonical fact decision history.

Revision ID: matter0002
Revises: verification0002
"""

import sqlalchemy as sa
from alembic import op

revision = "matter0002"
down_revision = "verification0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matter_subjects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "user_id", "matter_id", "kind", "ordinal", name="uq_matter_subject_ordinal"
        ),
    )
    op.create_table(
        "matter_transactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), sa.ForeignKey("matters.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("parcel_subject_ids", sa.JSON(), nullable=False),
        sa.Column("party_roles", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "user_id", "matter_id", "ordinal", name="uq_matter_transaction_ordinal"
        ),
    )
    op.create_table(
        "matter_transaction_revisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "transaction_id", sa.String(64), sa.ForeignKey("matter_transactions.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parcel_subject_ids", sa.JSON(), nullable=False),
        sa.Column("party_roles", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("transaction_id", "version", name="uq_transaction_revision"),
    )
    for name, type_, default in [
        ("original_value", sa.JSON(), None),
        ("origin", sa.String(16), "legacy"),
        ("source_candidate_id", sa.String(64), None),
        ("source_candidate_version", sa.Integer(), None),
        ("lineage_id", sa.String(64), None),
        ("manual_reason", sa.Text(), None),
    ]:
        op.add_column(
            "extracted_facts",
            sa.Column(name, type_, nullable=default is None, server_default=default),
        )
    op.create_index(
        "ix_extracted_facts_source_candidate_id", "extracted_facts", ["source_candidate_id"]
    )
    op.create_index("ix_extracted_facts_lineage_id", "extracted_facts", ["lineage_id"])
    op.add_column("evidence_references", sa.Column("page_text", sa.Text(), nullable=True))
    op.add_column(
        "evidence_references",
        sa.Column("precision", sa.String(16), nullable=False, server_default="page"),
    )
    op.add_column(
        "evidence_references", sa.Column("candidate_version", sa.Integer(), nullable=True)
    )
    op.add_column("evidence_references", sa.Column("candidate_id", sa.String(64), nullable=True))
    op.add_column(
        "review_decisions",
        sa.Column("resolved_fact_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    # Preserve historical types/values/decisions. Attach original observations
    # through existing owner/matter links; an NIC never established a role.
    op.execute(
        sa.text("""
        UPDATE extracted_facts AS f
        SET source_candidate_id = c.id, source_candidate_version = c.version,
            original_value = to_json(c.candidate_value), lineage_id = f.id,
            scope_status = CASE WHEN l.type_id = 'rta.doc.nic'
                AND c.key = 'transfereeNic' THEN 'unassigned' ELSE f.scope_status END
        FROM processing_candidate_fields AS c
        JOIN processing_logical_documents AS l ON l.id = c.logical_document_id
        WHERE c.approved_fact_id = f.id AND c.user_id = f.user_id
          AND c.matter_id = f.matter_id AND l.user_id = f.user_id
          AND l.matter_id = f.matter_id
    """)
    )


def downgrade() -> None:
    op.drop_column("review_decisions", "resolved_fact_ids")
    for name in ("candidate_id", "candidate_version", "precision", "page_text"):
        op.drop_column("evidence_references", name)
    op.drop_index("ix_extracted_facts_source_candidate_id", "extracted_facts")
    op.drop_index("ix_extracted_facts_lineage_id", "extracted_facts")
    for name in (
        "manual_reason",
        "lineage_id",
        "source_candidate_version",
        "source_candidate_id",
        "origin",
        "original_value",
    ):
        op.drop_column("extracted_facts", name)
    op.drop_table("matter_transaction_revisions")
    op.drop_table("matter_transactions")
    op.drop_table("matter_subjects")
