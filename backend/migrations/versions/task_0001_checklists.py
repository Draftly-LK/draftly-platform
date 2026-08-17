"""task_0001 — checklist snapshots, items, and satisfaction links

Revision ID: task0001
Revises: matter0001
Create Date: 2026-08-16

Creates: checklist_snapshots, checklist_items, checklist_satisfaction_links

The seven status columns on checklist_items are separate columns rather than one
enum because the workflow spec §5.4 requires them to be able to disagree: an
item can be received, lawyer-confirmed, and still mismatched or expired.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "task0001"
down_revision = "matter0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checklist_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("compiler_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("checklist_version", sa.String(32), nullable=False),
        sa.Column("rule_pack_version", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("module_definition_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("supersedes_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_checklist_snapshots_user_matter", "checklist_snapshots", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_checklist_snapshots_fingerprint",
        "checklist_snapshots",
        ["matter_id", "fingerprint"],
    )

    op.create_table(
        "checklist_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "snapshot_id",
            sa.String(64),
            sa.ForeignKey("checklist_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_definition_id", sa.String(128), nullable=False),
        sa.Column("module_definition_id", sa.String(64), nullable=False),
        sa.Column("inclusion_reason", sa.String(40), nullable=False),
        sa.Column("inclusion_trigger_id", sa.String(128), nullable=True),
        sa.Column("applicability", sa.String(32), nullable=False),
        sa.Column("collection", sa.String(32), nullable=False),
        sa.Column("digital_review", sa.String(32), nullable=False),
        sa.Column("physical_original", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(32), nullable=False),
        sa.Column("consistency", sa.String(32), nullable=False),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("applicability_reason", sa.Text, nullable=True),
        sa.Column("applicability_decided_by", sa.String(64), nullable=True),
        sa.Column("assigned_to", sa.String(64), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_authority_id", sa.String(64), nullable=True),
        # Inspection reviewer, time, and method live together so the status can
        # never be present without the human event that justifies it (§5.4).
        sa.Column("original_inspection_reviewer_id", sa.String(64), nullable=True),
        sa.Column("original_inspection_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_inspection_method", sa.String(128), nullable=True),
        sa.Column("original_inspection_location", sa.String(255), nullable=True),
        sa.Column("original_inspection_note", sa.Text, nullable=True),
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
        sa.UniqueConstraint(
            "snapshot_id",
            "requirement_definition_id",
            name="uq_checklist_item_snapshot_requirement",
        ),
        sa.CheckConstraint(
            "(physical_original <> 'ORIGINAL_INSPECTED') OR "
            "(original_inspection_reviewer_id IS NOT NULL "
            "AND original_inspection_at IS NOT NULL "
            "AND original_inspection_method IS NOT NULL)",
            name="ck_checklist_item_original_inspection_requires_human",
        ),
    )
    op.create_index("ix_checklist_items_user_matter", "checklist_items", ["user_id", "matter_id"])
    op.create_index("ix_checklist_items_snapshot", "checklist_items", ["snapshot_id"])

    op.create_table(
        "checklist_satisfaction_links",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "checklist_item_id",
            sa.String(64),
            sa.ForeignKey("checklist_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("detected_document_id", sa.String(64), nullable=False),
        sa.Column("digital_review", sa.String(32), nullable=False),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("superseded_by_link_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_satisfaction_links_user_matter",
        "checklist_satisfaction_links",
        ["user_id", "matter_id"],
    )
    op.create_index(
        "ix_satisfaction_links_item", "checklist_satisfaction_links", ["checklist_item_id"]
    )
    op.create_index(
        "ix_satisfaction_links_document",
        "checklist_satisfaction_links",
        ["detected_document_id"],
    )


def downgrade() -> None:
    op.drop_table("checklist_satisfaction_links")
    op.drop_index("ix_checklist_items_snapshot", table_name="checklist_items")
    op.drop_index("ix_checklist_items_user_matter", table_name="checklist_items")
    op.drop_table("checklist_items")
    op.drop_index("ix_checklist_snapshots_fingerprint", table_name="checklist_snapshots")
    op.drop_index("ix_checklist_snapshots_user_matter", table_name="checklist_snapshots")
    op.drop_table("checklist_snapshots")
