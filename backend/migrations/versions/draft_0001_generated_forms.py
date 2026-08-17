"""draft_0001 — generated forms and their evidence-linked field bindings

Revision ID: draft0001
Revises: check0001
Create Date: 2026-08-16

Creates: generated_forms, generated_form_fields

A generated form is a *binding record*, not a rendered file: it stores the
template version it was drafted against, the exact fact version each field was
populated from, and the page-level evidence behind it, so an approval can pin
itself to one snapshot and an auditor can reconstruct it (§9.3, §9.6).

`(matter_id, template_id, form_version)` is unique because §9.5 amends an
approved form by opening a *new* version rather than editing the old one; the
counter is per matter and template and is never reused.

The check constraints mirror `modules/draft/infrastructure/orm.py` so the two
can never drift: a field is either populated or unresolved and never both
(§9.4), a populated critical field cannot exist without its canonical fact id
and version (§9.3), an approved state cannot exist without the artifact hash
that makes it a snapshot, and a stale state cannot exist without the reason a
lawyer must act on. Evidence non-emptiness is enforced in the domain instead —
`evidence_reference_ids` is JSON and no portable check expresses "non-empty
array".
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "draft0001"
down_revision = "check0001"
branch_labels = None
depends_on = None

_FORM_STATES = (
    "'GENERATED_DRAFT', 'UNRESOLVED', 'REVIEW_READY', 'LAWYER_REVIEWED', "
    "'APPROVAL_PENDING', 'APPROVED', 'EXPORTED', 'SUBMITTED', 'REGISTERED', "
    "'STALE_TEMPLATE', 'STALE_AFTER_APPROVAL'"
)
_APPROVED_STATES = "'APPROVED', 'EXPORTED', 'SUBMITTED', 'REGISTERED', 'STALE_AFTER_APPROVAL'"
_STALE_STATES = "'STALE_TEMPLATE', 'STALE_AFTER_APPROVAL'"
_UNRESOLVED_REASONS = (
    "'NO_FACT', 'FACT_NOT_CONFIRMED', 'FACT_CONFLICTED', 'FACT_SUPERSEDED', 'BLOCKED_BY_ISSUE'"
)


def upgrade() -> None:
    op.create_table(
        "generated_forms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(128), nullable=False),
        # Pinned at generation and never refreshed in place: §9.5 forbids
        # auto-updating a live matter when a template changes.
        sa.Column("template_version", sa.String(32), nullable=False),
        sa.Column("form_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("subtype_id", sa.String(128), nullable=False),
        sa.Column("draft_artifact_hash", sa.String(80), nullable=True),
        # Written by the approval module, never by drafting.
        sa.Column("approved_artifact_hash", sa.String(80), nullable=True),
        sa.Column("approval_id", sa.String(64), nullable=True),
        sa.Column("stale_reason", sa.String(64), nullable=True),
        sa.Column("rule_pack_version", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
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
            "matter_id",
            "template_id",
            "form_version",
            name="uq_generated_form_matter_template_version",
        ),
        sa.CheckConstraint(f"state IN ({_FORM_STATES})", name="ck_generated_form_state"),
        sa.CheckConstraint("form_version >= 1", name="ck_generated_form_version_positive"),
        sa.CheckConstraint(
            f"state NOT IN ({_APPROVED_STATES}) OR approved_artifact_hash IS NOT NULL",
            name="ck_generated_form_approved_requires_hash",
        ),
        sa.CheckConstraint(
            f"state NOT IN ({_STALE_STATES}) OR stale_reason IS NOT NULL",
            name="ck_generated_form_stale_requires_reason",
        ),
    )
    op.create_index("ix_generated_forms_user_matter", "generated_forms", ["user_id", "matter_id"])
    op.create_index(
        "ix_generated_forms_matter_template", "generated_forms", ["matter_id", "template_id"]
    )
    op.create_index("ix_generated_forms_matter_state", "generated_forms", ["matter_id", "state"])

    op.create_table(
        "generated_form_fields",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "generated_form_id",
            sa.String(64),
            sa.ForeignKey("generated_forms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_id", sa.String(128), nullable=False),
        sa.Column("fact_id", sa.String(64), nullable=True),
        sa.Column("fact_version", sa.Integer, nullable=True),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("rendered_value", sa.Text, nullable=True),
        sa.Column("unresolved_reason", sa.String(32), nullable=True),
        sa.Column("transformation_id", sa.String(32), nullable=True),
        sa.Column("review_decision_id", sa.String(64), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("critical", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "generated_form_id", "field_id", name="uq_generated_form_field_form_field"
        ),
        sa.CheckConstraint(
            f"unresolved_reason IS NULL OR unresolved_reason IN ({_UNRESOLVED_REASONS})",
            name="ck_generated_form_field_unresolved_reason",
        ),
        # §9.4 — populated or unresolved, never both, never blank space.
        sa.CheckConstraint(
            "NOT (rendered_value IS NOT NULL AND unresolved_reason IS NOT NULL)",
            name="ck_generated_form_field_value_xor_unresolved",
        ),
        # §9.3 — a populated critical field carries its fact id and the exact
        # version bound. Evidence non-emptiness is a domain check.
        sa.CheckConstraint(
            "NOT (critical AND rendered_value IS NOT NULL "
            "AND (fact_id IS NULL OR fact_version IS NULL))",
            name="ck_generated_form_field_critical_requires_fact",
        ),
        sa.CheckConstraint(
            "(reviewed_by IS NULL) = (reviewed_at IS NULL)",
            name="ck_generated_form_field_review_pair",
        ),
    )
    op.create_index(
        "ix_generated_form_fields_user_matter", "generated_form_fields", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_generated_form_fields_form", "generated_form_fields", ["generated_form_id"]
    )
    op.create_index("ix_generated_form_fields_fact", "generated_form_fields", ["user_id", "fact_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_form_fields_fact", table_name="generated_form_fields")
    op.drop_index("ix_generated_form_fields_form", table_name="generated_form_fields")
    op.drop_index("ix_generated_form_fields_user_matter", table_name="generated_form_fields")
    op.drop_table("generated_form_fields")
    op.drop_index("ix_generated_forms_matter_state", table_name="generated_forms")
    op.drop_index("ix_generated_forms_matter_template", table_name="generated_forms")
    op.drop_index("ix_generated_forms_user_matter", table_name="generated_forms")
    op.drop_table("generated_forms")
