"""ORM models for generated forms and their field bindings.

Two constraints on `generated_form_fields` are the §9.4 rules expressed where a
direct SQL write also meets them: a field is either populated or unresolved and
never both, and a populated critical field cannot exist without the canonical
fact id and version behind it. Evidence non-emptiness stays a domain error —
``evidence_reference_ids`` is JSON and no portable check expresses "non-empty
array" — so `policies.guard_populated_critical_field` is the enforcement point
and is called before any populated critical row is written.

`generated_forms` carries the mirror of the §10.7 lifecycle: a state that claims
approval needs the approved hash, and a state that claims staleness needs the
reason a lawyer will act on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base

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


class GeneratedFormRow(Base):
    """One drafted instrument, pinned to the versions that produced it."""

    __tablename__ = "generated_forms"
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    missing_causes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    predecessor_form_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint(
            "matter_id",
            "template_id",
            "form_version",
            name="uq_generated_form_matter_template_version",
        ),
        Index("ix_generated_forms_user_matter", "user_id", "matter_id"),
        Index("ix_generated_forms_matter_template", "matter_id", "template_id"),
        Index("ix_generated_forms_matter_state", "matter_id", "state"),
        CheckConstraint(f"state IN ({_FORM_STATES})", name="ck_generated_form_state"),
        CheckConstraint("form_version >= 1", name="ck_generated_form_version_positive"),
        # §10.7 — approval creates an immutable snapshot *and its hash*. A row
        # claiming approval without one is not a snapshot, it is an assertion.
        CheckConstraint(
            f"state NOT IN ({_APPROVED_STATES}) OR approved_artifact_hash IS NOT NULL",
            name="ck_generated_form_approved_requires_hash",
        ),
        # A stale form always says why: the reason is what tells the lawyer
        # whether to re-review one field or open a new form version (§9.5).
        CheckConstraint(
            f"state NOT IN ({_STALE_STATES}) OR stale_reason IS NOT NULL",
            name="ck_generated_form_stale_requires_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    #: The template version at generation. Never refreshed in place: §9.5
    #: forbids auto-updating a live matter when a template changes.
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    form_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    subtype_id: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_artifact_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: Written by `approval`, never by this module. Approving is not drafting.
    approved_artifact_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GeneratedFormFieldRow(Base):
    """One field of one form, and the evidence chain behind its value (§9.3)."""

    __tablename__ = "generated_form_fields"
    __table_args__ = (
        UniqueConstraint(
            "generated_form_id", "field_id", name="uq_generated_form_field_form_field"
        ),
        Index("ix_generated_form_fields_user_matter", "user_id", "matter_id"),
        Index("ix_generated_form_fields_form", "generated_form_id"),
        Index("ix_generated_form_fields_fact", "user_id", "fact_id"),
        CheckConstraint(
            f"unresolved_reason IS NULL OR unresolved_reason IN ({_UNRESOLVED_REASONS})",
            name="ck_generated_form_field_unresolved_reason",
        ),
        # §9.4 — a field is either populated or unresolved. Never blank space,
        # never a value with an excuse attached to it.
        CheckConstraint(
            "NOT (rendered_value IS NOT NULL AND unresolved_reason IS NOT NULL)",
            name="ck_generated_form_field_value_xor_unresolved",
        ),
        # §9.3 — a populated critical field carries its canonical fact and the
        # exact version bound. Evidence non-emptiness is checked in the domain.
        CheckConstraint(
            "NOT (critical AND rendered_value IS NOT NULL "
            "AND (fact_id IS NULL OR fact_version IS NULL))",
            name="ck_generated_form_field_critical_requires_fact",
        ),
        CheckConstraint(
            "(reviewed_by IS NULL) = (reviewed_at IS NULL)",
            name="ck_generated_form_field_review_pair",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("generated_forms.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Stored beside the id because a correction creates a new version: the row
    #: records which version was bound, not which one is current (§10.5).
    fact_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rendered_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unresolved_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transformation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order: Mapped[int] = mapped_column("order", Integer, nullable=False, default=0)
