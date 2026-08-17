"""approval_0001 — approvals, form exports, and registration events

Revision ID: approval0001
Revises: draft0001
Create Date: 2026-08-16

Creates: approvals, form_exports, registration_events

`approvals` is the §9.6 signed application event and is append-only: there is no
version column because an approval is immutable, and the one field that ever
changes is `revoked_by_approval_id`, written when a later approval supersedes
it. A revocation therefore cannot exist without the approval that caused it,
which is what §17's "a correction after approval ... prevents reuse of the old
approval" needs in order to be provable from the data.

`form_exports` records that a projection left the system. Two constraints make
§9.4's separation structural rather than conventional: a registration-ready
export cannot exist without an approval, and a watermarked artifact can never be
registration-ready. Both are false for every row this repository can produce
today — no template here has a lawyer-approved production rendering (§9.5).

`registration_events` records attestation, presentation, and registration as
three separate human acts. The constraints hold the shape of each: an
attestation or a registration names the instrument it was performed on, a day
book entry carries the registry's reference, and a refusal or return carries the
reason. Evidence non-emptiness stays a domain check — `evidence_reference_ids`
is JSON and no portable constraint expresses "non-empty array".

Every constraint here mirrors `src/modules/approval/infrastructure/orm.py` so
the two can never drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "approval0001"
down_revision = "draft0001"
branch_labels = None
depends_on = None

_APPROVAL_TARGET_TYPES = "'GENERATED_FORM', 'MATTER_PREFLIGHT', 'PHYSICAL_ORIGINAL_INSPECTION'"
_EXPORT_FORMATS = "'WORKING_DRAFT_MANIFEST', 'APPROVED_MANIFEST', 'EVIDENCE_SCHEDULE'"
_EVENT_TYPES = "'ATTESTED', 'PRESENTED', 'DAY_BOOK_ENTERED', 'REGISTERED', 'REFUSED', 'RETURNED'"
_FORM_REQUIRED_EVENTS = "'ATTESTED', 'REGISTERED'"


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        # Read from the server's own record of the form, never from the request.
        sa.Column("target_version", sa.String(32), nullable=False),
        sa.Column("approver_id", sa.String(64), nullable=False),
        sa.Column("approver_workflow_role", sa.String(32), nullable=False),
        sa.Column("declaration_version", sa.String(16), nullable=False),
        sa.Column("declaration_text_hash", sa.String(96), nullable=False),
        sa.Column("snapshot_hash", sa.String(80), nullable=False),
        sa.Column("confirmed_fact_hash", sa.String(80), nullable=False),
        sa.Column("warning_disposition_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("template_id", sa.String(128), nullable=False),
        sa.Column("template_version", sa.String(32), nullable=False),
        sa.Column("rule_pack_version", sa.String(32), nullable=False),
        sa.Column("revoked_by_approval_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"target_type IN ({_APPROVAL_TARGET_TYPES})", name="ck_approval_target_type"
        ),
        sa.CheckConstraint(
            "revoked_by_approval_id IS NULL OR revoked_by_approval_id <> id",
            name="ck_approval_revocation_is_another_approval",
        ),
        sa.CheckConstraint(
            "length(declaration_text_hash) > 0 AND length(snapshot_hash) > 0 "
            "AND length(confirmed_fact_hash) > 0",
            name="ck_approval_hashes_present",
        ),
    )
    op.create_index("ix_approvals_user_matter", "approvals", ["user_id", "matter_id"])
    op.create_index("ix_approvals_target", "approvals", ["user_id", "target_id"])
    op.create_index("ix_approvals_approver", "approvals", ["user_id", "approver_id"])

    op.create_table(
        "form_exports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "generated_form_id",
            sa.String(64),
            sa.ForeignKey("generated_forms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approval_id",
            sa.String(64),
            sa.ForeignKey("approvals.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("export_format", sa.String(32), nullable=False),
        sa.Column("artifact_hash", sa.String(80), nullable=False),
        # `inline:manifest/<id>` today: the manifest column is the artifact, and
        # no bytes are written because no page may be fabricated (§9.5).
        sa.Column("artifact_key", sa.String(256), nullable=False),
        sa.Column("watermarked", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("registration_ready", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("manifest", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("artifact_key", name="uq_form_export_artifact_key"),
        sa.CheckConstraint(f"export_format IN ({_EXPORT_FORMATS})", name="ck_form_export_format"),
        sa.CheckConstraint(
            "NOT registration_ready OR approval_id IS NOT NULL",
            name="ck_form_export_registration_ready_requires_approval",
        ),
        sa.CheckConstraint(
            "NOT (watermarked AND registration_ready)",
            name="ck_form_export_watermark_excludes_registration_ready",
        ),
    )
    op.create_index("ix_form_exports_user_matter", "form_exports", ["user_id", "matter_id"])
    op.create_index("ix_form_exports_form", "form_exports", ["user_id", "generated_form_id"])

    op.create_table(
        "registration_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "generated_form_id",
            sa.String(64),
            sa.ForeignKey("generated_forms.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        # A day, not an instant: s. 45(1) counts working days from attestation.
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("evidence_reference_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("day_book_reference", sa.String(128), nullable=True),
        sa.Column("registry_office", sa.String(128), nullable=True),
        sa.Column("result_note", sa.Text, nullable=True),
        sa.Column("recorded_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"event_type IN ({_EVENT_TYPES})", name="ck_registration_event_type"),
        sa.CheckConstraint(
            f"event_type NOT IN ({_FORM_REQUIRED_EVENTS}) OR generated_form_id IS NOT NULL",
            name="ck_registration_event_form_required",
        ),
        sa.CheckConstraint(
            "event_type <> 'DAY_BOOK_ENTERED' OR day_book_reference IS NOT NULL",
            name="ck_registration_event_day_book_reference",
        ),
        sa.CheckConstraint(
            "event_type NOT IN ('REFUSED', 'RETURNED') OR result_note IS NOT NULL",
            name="ck_registration_event_result_note",
        ),
    )
    op.create_index(
        "ix_registration_events_user_matter", "registration_events", ["user_id", "matter_id"]
    )
    op.create_index(
        "ix_registration_events_form", "registration_events", ["user_id", "generated_form_id"]
    )
    op.create_index(
        "ix_registration_events_type", "registration_events", ["matter_id", "event_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_registration_events_type", table_name="registration_events")
    op.drop_index("ix_registration_events_form", table_name="registration_events")
    op.drop_index("ix_registration_events_user_matter", table_name="registration_events")
    op.drop_table("registration_events")
    op.drop_index("ix_form_exports_form", table_name="form_exports")
    op.drop_index("ix_form_exports_user_matter", table_name="form_exports")
    op.drop_table("form_exports")
    op.drop_index("ix_approvals_approver", table_name="approvals")
    op.drop_index("ix_approvals_target", table_name="approvals")
    op.drop_index("ix_approvals_user_matter", table_name="approvals")
    op.drop_table("approvals")
