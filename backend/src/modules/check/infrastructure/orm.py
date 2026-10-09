"""ORM models for cross-document checks and legal issues.

`cross_document_checks` has no update path: a rerun after a fact changes appends
a new row pinned to the new fact versions, so the state a conclusion was drawn
under stays reconstructible (§7.1, §12.2).

`legal_issues` is the mutable half, and carries the two constraints that make
§7.3 unbypassable at the storage layer as well as in the domain: a statutory
blocker can never hold ``ACCEPTED_RISK``, and a disposition that ends an issue
without evidence cannot exist without a recorded reason.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base

_OUTCOMES = "'PASS', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN'"
_SEVERITIES = "'INFORMATION', 'WARNING', 'HIGH_RISK', 'BLOCKING'"
_BLOCKER_KINDS = "'STATUTORY', 'EVIDENCE', 'V0_SCOPE', 'OFFICE_POLICY', 'PROFESSIONAL_JUDGMENT'"
_ISSUE_STATES = (
    "'OPEN', 'TRIAGED', 'ACTION_REQUIRED', 'RESOLVED', "
    "'ACCEPTED_RISK', 'FALSE_POSITIVE', 'OUTSIDE_SCOPE'"
)


class CrossDocumentCheckRow(Base):
    """One deterministic comparison, as it stood at one moment."""

    __tablename__ = "cross_document_checks"
    __table_args__ = (
        Index("ix_cross_document_checks_user_matter", "user_id", "matter_id"),
        Index("ix_cross_document_checks_run", "user_id", "run_id"),
        Index("ix_cross_document_checks_definition", "matter_id", "check_definition_id"),
        CheckConstraint(f"outcome IN ({_OUTCOMES})", name="ck_cross_document_check_outcome"),
        CheckConstraint(
            f"default_severity IN ({_SEVERITIES})", name="ck_cross_document_check_severity"
        ),
        # §7.1: a pass means only that the encoded comparison passed. The form
        # completeness check is the single mechanical exception, so no other
        # check can be stored as needing no human conclusion.
        CheckConstraint(
            "requires_human_conclusion OR check_definition_id = 'CHK_FORM_REQUIRED_FIELDS'",
            name="ck_cross_document_check_human_conclusion_required",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    association_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_definition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    check_definition_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    default_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation_key: Mapped[str] = mapped_column(String(191), nullable=False)
    #: ``[{"factId": ..., "version": ...}]`` — the exact versions read, so a
    #: later correction is visible as a different input set (§7.1).
    input_fact_versions: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    requires_human_conclusion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LegalIssueRow(Base):
    """A red flag worked through the §10.6 lifecycle."""

    __tablename__ = "legal_issues"
    __table_args__ = (
        Index("ix_legal_issues_user_matter", "user_id", "matter_id"),
        Index("ix_legal_issues_matter_state", "matter_id", "state"),
        Index("ix_legal_issues_matter_type", "matter_id", "issue_type_id"),
        CheckConstraint(f"severity IN ({_SEVERITIES})", name="ck_legal_issue_severity"),
        CheckConstraint(f"blocker_kind IN ({_BLOCKER_KINDS})", name="ck_legal_issue_blocker_kind"),
        CheckConstraint(f"state IN ({_ISSUE_STATES})", name="ck_legal_issue_state"),
        # The one refusal the product must never let a caller talk its way
        # around, expressed where even a direct SQL write meets it (§7.3, §10.6).
        CheckConstraint(
            "NOT (blocker_kind = 'STATUTORY' AND state = 'ACCEPTED_RISK')",
            name="ck_legal_issue_statutory_never_accepted",
        ),
        # A disposition that ends an issue without new evidence is a legal act
        # with an author and a reason, or it is not recorded at all (§10.6).
        CheckConstraint(
            "state NOT IN ('ACCEPTED_RISK', 'FALSE_POSITIVE', 'OUTSIDE_SCOPE') "
            "OR resolution_reason IS NOT NULL",
            name="ck_legal_issue_disposition_requires_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    association_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Nullable: a lawyer may raise an issue no deterministic check produced.
    check_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    blocker_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_key: Mapped[str] = mapped_column(String(191), nullable=False)
    #: The legal basis the check cited, so the issue carries its authority.
    source_record_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
