"""check_0001 — cross-document check results and legal issues

Revision ID: check0001
Revises: document0001
Create Date: 2026-08-16

Creates: cross_document_checks, legal_issues

`cross_document_checks` is append-only: a rerun after a fact changes inserts a
new row pinned to the new fact versions rather than editing the old one, so the
state a conclusion was drawn under stays reconstructible (§7.1, §12.2).

Two check constraints on `legal_issues` mirror the domain policies so the two
can never drift: a `STATUTORY` blocker can never hold `ACCEPTED_RISK` (§7.3),
and a disposition that ends an issue without new evidence cannot exist without a
recorded reason (§10.6).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "check0001"
down_revision = "document0001"
branch_labels = None
depends_on = None

_OUTCOMES = "'PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN'"
_SEVERITIES = "'INFORMATION', 'WARNING', 'HIGH_RISK', 'BLOCKING'"
_BLOCKER_KINDS = "'STATUTORY', 'EVIDENCE', 'V0_SCOPE', 'OFFICE_POLICY', 'PROFESSIONAL_JUDGMENT'"
_ISSUE_STATES = (
    "'OPEN', 'TRIAGED', 'ACTION_REQUIRED', 'RESOLVED', "
    "'ACCEPTED_RISK', 'FALSE_POSITIVE', 'OUTSIDE_SCOPE'"
)


def upgrade() -> None:
    op.create_table(
        "cross_document_checks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("check_definition_id", sa.String(64), nullable=False),
        sa.Column("check_definition_version", sa.String(32), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("default_severity", sa.String(16), nullable=False),
        sa.Column("explanation_key", sa.String(191), nullable=False),
        # [{"factId": ..., "version": ...}] — the exact versions the check read.
        sa.Column("input_fact_versions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("requires_human_conclusion", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"outcome IN ({_OUTCOMES})", name="ck_cross_document_check_outcome"),
        sa.CheckConstraint(
            f"default_severity IN ({_SEVERITIES})", name="ck_cross_document_check_severity"
        ),
        # §7.1: a pass means only that the encoded comparison passed. Form
        # completeness is the single mechanical exception.
        sa.CheckConstraint(
            "requires_human_conclusion OR check_definition_id = 'CHK_FORM_REQUIRED_FIELDS'",
            name="ck_cross_document_check_human_conclusion_required",
        ),
    )
    op.create_index(
        "ix_cross_document_checks_user_matter",
        "cross_document_checks",
        ["user_id", "matter_id"],
    )
    op.create_index("ix_cross_document_checks_run", "cross_document_checks", ["user_id", "run_id"])
    op.create_index(
        "ix_cross_document_checks_definition",
        "cross_document_checks",
        ["matter_id", "check_definition_id"],
    )

    op.create_table(
        "legal_issues",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        # Nullable: a lawyer may raise an issue no deterministic check produced.
        sa.Column("check_id", sa.String(64), nullable=True),
        sa.Column("issue_type_id", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("blocker_kind", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("summary_key", sa.String(191), nullable=False),
        sa.Column("source_record_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("assigned_to", sa.String(64), nullable=True),
        sa.Column("resolution_decision_id", sa.String(64), nullable=True),
        sa.Column("resolution_reason", sa.Text, nullable=True),
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
        sa.CheckConstraint(f"severity IN ({_SEVERITIES})", name="ck_legal_issue_severity"),
        sa.CheckConstraint(
            f"blocker_kind IN ({_BLOCKER_KINDS})", name="ck_legal_issue_blocker_kind"
        ),
        sa.CheckConstraint(f"state IN ({_ISSUE_STATES})", name="ck_legal_issue_state"),
        # Draftly cannot set aside a statutory prohibition. Enforced here as
        # well as in `check/domain/policies.py` so a direct write cannot either.
        sa.CheckConstraint(
            "NOT (blocker_kind = 'STATUTORY' AND state = 'ACCEPTED_RISK')",
            name="ck_legal_issue_statutory_never_accepted",
        ),
        sa.CheckConstraint(
            "state NOT IN ('ACCEPTED_RISK', 'FALSE_POSITIVE', 'OUTSIDE_SCOPE') "
            "OR resolution_reason IS NOT NULL",
            name="ck_legal_issue_disposition_requires_reason",
        ),
    )
    op.create_index("ix_legal_issues_user_matter", "legal_issues", ["user_id", "matter_id"])
    op.create_index("ix_legal_issues_matter_state", "legal_issues", ["matter_id", "state"])
    op.create_index("ix_legal_issues_matter_type", "legal_issues", ["matter_id", "issue_type_id"])


def downgrade() -> None:
    op.drop_index("ix_legal_issues_matter_type", table_name="legal_issues")
    op.drop_index("ix_legal_issues_matter_state", table_name="legal_issues")
    op.drop_index("ix_legal_issues_user_matter", table_name="legal_issues")
    op.drop_table("legal_issues")
    op.drop_index("ix_cross_document_checks_definition", table_name="cross_document_checks")
    op.drop_index("ix_cross_document_checks_run", table_name="cross_document_checks")
    op.drop_index("ix_cross_document_checks_user_matter", table_name="cross_document_checks")
    op.drop_table("cross_document_checks")
