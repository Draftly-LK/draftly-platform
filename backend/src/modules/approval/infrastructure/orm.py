"""ORM models for approvals, form exports, and registration events.

The check constraints are the append-only invariants expressed where a direct
SQL write also meets them, and each is mirrored in
`migrations/versions/approval_0001_approvals_and_registration.py` so the two
cannot drift.

`approvals` has no version column: §12.2 and api-conventions §3 both make an
approval immutable, so there is nothing to concurrency-control. The single field
that ever changes is ``revoked_by_approval_id``, and the constraint that it
never points at itself is the difference between "superseded by a later
approval" and "quietly withdrawn".

`registration_events` carries an evidence column that must not be the empty
array, which is checkable in the domain but not portably in SQL — what SQL does
enforce is the shape of each event type: a day book entry carries the registry's
reference, a refusal carries the reason, and an attestation or registration
names the instrument it was performed on.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base

_APPROVAL_TARGET_TYPES = "'GENERATED_FORM', 'MATTER_PREFLIGHT', 'PHYSICAL_ORIGINAL_INSPECTION'"
_EXPORT_FORMATS = "'WORKING_DRAFT_MANIFEST', 'APPROVED_MANIFEST', 'EVIDENCE_SCHEDULE'"
_EVENT_TYPES = "'ATTESTED', 'PRESENTED', 'DAY_BOOK_ENTERED', 'REGISTERED', 'REFUSED', 'RETURNED'"
_FORM_REQUIRED_EVENTS = "'ATTESTED', 'REGISTERED'"


class ApprovalRow(Base):
    """One §9.6 signed application event. Append-only."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_user_matter", "user_id", "matter_id"),
        Index("ix_approvals_target", "user_id", "target_id"),
        Index("ix_approvals_approver", "user_id", "approver_id"),
        CheckConstraint(
            f"target_type IN ({_APPROVAL_TARGET_TYPES})", name="ck_approval_target_type"
        ),
        # An approval is superseded by a *later* approval. Pointing at itself
        # would be a withdrawal with no successor, which §9.6 does not have.
        CheckConstraint(
            "revoked_by_approval_id IS NULL OR revoked_by_approval_id <> id",
            name="ck_approval_revocation_is_another_approval",
        ),
        # §9.6 — the declaration, the snapshot, and the confirmed facts are all
        # pinned by hash. A row missing one is not a record of what was signed.
        CheckConstraint(
            "length(declaration_text_hash) > 0 AND length(snapshot_hash) > 0 "
            "AND length(confirmed_fact_hash) > 0",
            name="ck_approval_hashes_present",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The form version approved, read from the server's own record (§9.6).
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    approver_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Stored beside the approver because §12.5 makes the authority part of the
    #: event: who they were on this matter, not who they are today.
    approver_workflow_role: Mapped[str] = mapped_column(String(32), nullable=False)
    declaration_version: Mapped[str] = mapped_column(String(16), nullable=False)
    declaration_text_hash: Mapped[str] = mapped_column(String(96), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmed_fact_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    warning_disposition_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked_by_approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FormExportRow(Base):
    """One projection of a form that left the system (§9.6)."""

    __tablename__ = "form_exports"
    __table_args__ = (
        Index("ix_form_exports_user_matter", "user_id", "matter_id"),
        Index("ix_form_exports_form", "user_id", "generated_form_id"),
        UniqueConstraint("artifact_key", name="uq_form_export_artifact_key"),
        CheckConstraint(f"export_format IN ({_EXPORT_FORMATS})", name="ck_form_export_format"),
        # §9.4, §9.6 — a registration-ready export is a projection of an
        # approval. Without one it is a working draft, whatever was asked for.
        CheckConstraint(
            "NOT registration_ready OR approval_id IS NOT NULL",
            name="ck_form_export_registration_ready_requires_approval",
        ),
        # The two are opposites by construction: what carries the draft notice
        # on every page is not what may be presented to a registry.
        CheckConstraint(
            "NOT (watermarked AND registration_ready)",
            name="ck_form_export_watermark_excludes_registration_ready",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("generated_forms.id", ondelete="RESTRICT"), nullable=False
    )
    approval_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("approvals.id", ondelete="RESTRICT"), nullable=True
    )
    export_format: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    #: ``inline:manifest/<id>`` today — the manifest column *is* the artifact.
    #: No bytes are written because no page may be fabricated (§9.5).
    artifact_key: Mapped[str] = mapped_column(String(256), nullable=False)
    watermarked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    registration_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RegistrationEventRow(Base):
    """One official act, recorded by a human from evidence (§10.1)."""

    __tablename__ = "registration_events"
    __table_args__ = (
        Index("ix_registration_events_user_matter", "user_id", "matter_id"),
        Index("ix_registration_events_form", "user_id", "generated_form_id"),
        Index("ix_registration_events_type", "matter_id", "event_type"),
        CheckConstraint(f"event_type IN ({_EVENT_TYPES})", name="ck_registration_event_type"),
        # An attestation or a registration is an act on one identified
        # instrument; the s. 45(1) clock cannot run on an unnamed one.
        CheckConstraint(
            f"event_type NOT IN ({_FORM_REQUIRED_EVENTS}) OR generated_form_id IS NOT NULL",
            name="ck_registration_event_form_required",
        ),
        CheckConstraint(
            "event_type <> 'DAY_BOOK_ENTERED' OR day_book_reference IS NOT NULL",
            name="ck_registration_event_day_book_reference",
        ),
        CheckConstraint(
            "event_type NOT IN ('REFUSED', 'RETURNED') OR result_note IS NOT NULL",
            name="ck_registration_event_result_note",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_form_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("generated_forms.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: A day, not an instant: what the registry records and what s. 45(1) counts
    #: from is a date.
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: Non-emptiness is a domain check — JSON has no portable "non-empty array"
    #: constraint — enforced by `policies.guard_registration_event`.
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    day_book_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    registry_office: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
