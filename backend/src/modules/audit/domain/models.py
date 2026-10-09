"""Audit domain models — action enum, target type enum, domain entity.

The target type enum is wider than the frontend's (audit-service.md §3.1).
The frontend renders 8 values; the backend audit record may carry any of these.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime


class AuditTargetType(str, enum.Enum):
    """Backend-wide closed enum of auditable resource types.

    The frontend projects 8 of these; the backend has all. Any value the
    frontend does not recognise renders as a generic row (audit-service.md §3.1).
    """

    MATTER = "matter"
    DOCUMENT = "document"
    INSTRUMENT = "instrument"
    FACT = "fact"
    CHECK = "check"
    WORKFLOW_STEP = "workflow-step"
    ANSWER = "answer"
    CASE_SEARCH = "case-search"
    DRAFT = "draft"
    APPROVAL = "approval"
    EXPORT = "export"
    PERMISSION = "permission"
    PARTY = "party"
    OBLIGATION = "obligation"
    NOTIFICATION = "notification"
    CONTENT_DEFINITION = "content-definition"
    LEGAL_SOURCE = "legal-source"
    SUBSCRIPTION = "subscription"
    TRANSCRIPT = "transcript"
    USER = "user"
    RETENTION = "retention"
    # RTA matter workflow (draftly-rta-matter-workflow-v1 §12.2)
    INTAKE_ANSWER = "intake-answer"
    CHECKLIST_SNAPSHOT = "checklist-snapshot"
    CHECKLIST_ITEM = "checklist-item"
    SOURCE_FILE = "source-file"
    DETECTED_DOCUMENT = "detected-document"
    ISSUE = "issue"
    GENERATED_FORM = "generated-form"
    REGISTRATION_EVENT = "registration-event"


class AuditAction(str, enum.Enum):
    """Closed action enum (audit-service.md §3.2 — no free strings)."""

    # Matter
    MATTER_CREATED = "matter.created"
    MATTER_SCOPE_ASSOCIATED = "matter.scope-associated"
    MATTER_CLOSED = "matter.closed"
    MATTER_REOPENED = "matter.reopened"
    MATTER_RECLASSIFIED = "matter.reclassified"
    MATTER_ARCHIVED = "matter.archived"
    MATTER_MEMBERSHIP_ASSIGNED = "matter.membership.assigned"
    # Identity / accounts
    USER_PROVISIONED_PENDING = "user.provisioned_pending"
    USER_ACTIVATED = "user.activated"
    USER_ROLE_CHANGED = "user.role.changed"
    USER_SUSPENDED = "user.suspended"
    # Document
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_REPLACED = "document.replaced"
    DOCUMENT_DELETED = "document.deleted"
    # Fact / verification
    FACT_VERIFIED = "fact.verified"
    FACT_CORRECTED = "fact.corrected"
    # Check / finding
    CHECK_RESOLVED = "check.resolved"
    FINDING_RESOLVED = "finding.resolved"
    FINDING_WAIVED = "finding.waived"
    # Workflow
    STEP_COMPLETED = "step.completed"
    STEP_OVERRIDDEN = "step.overridden"
    # Draft
    DRAFT_CREATED = "draft.created"
    DRAFT_APPROVED = "draft.approved"
    DRAFT_RESTORED = "draft.restored"
    # Export
    EXPORT_CREATED = "export.created"
    # Bounded case retrieval; no fact patterns or source passages in audit.
    RESEARCH_CASES_SEARCHED = "research.cases-searched"
    # Compliance / retention
    RETENTION_HOLD_PLACED = "retention.hold.placed"
    RETENTION_DESTRUCTION_APPROVED = "retention.destruction.approved"
    # ── RTA matter workflow ──────────────────────────────────────────────
    # Every material transition in draftly-rta-matter-workflow-v1 §17 has an
    # action here, because "audit history identifies actor, role, event,
    # before/after version/hash, request, and time" is an acceptance criterion,
    # not a nice-to-have.
    RTA_MATTER_ROUTED = "rta.matter.routed"
    RTA_MATTER_SUBTYPE_CONFIRMED = "rta.matter.subtype-confirmed"
    RTA_MATTER_STATE_CHANGED = "rta.matter.state-changed"
    RTA_MATTER_AUTOMATION_SCOPE_CHANGED = "rta.matter.automation-scope-changed"
    RTA_MATTER_LEGACY_MIGRATED = "rta.matter.legacy-migrated"
    RTA_INTAKE_ANSWER_RECORDED = "rta.intake.answer-recorded"
    RTA_INTAKE_ANSWER_SUPERSEDED = "rta.intake.answer-superseded"
    RTA_CHECKLIST_COMPILED = "rta.checklist.compiled"
    RTA_CHECKLIST_ITEM_DECIDED = "rta.checklist.item-decided"
    RTA_CHECKLIST_ITEM_WAIVED = "rta.checklist.item-waived"
    RTA_ORIGINAL_INSPECTION_RECORDED = "rta.checklist.original-inspection-recorded"
    RTA_SOURCE_FILE_UPLOADED = "rta.source-file.uploaded"
    RTA_SOURCE_FILE_STATE_CHANGED = "rta.source-file.state-changed"
    RTA_SOURCE_FILE_REJECTED = "rta.source-file.rejected"
    RTA_SOURCE_FILE_VIEWED = "rta.source-file.viewed"
    RTA_DOCUMENT_BOUNDARY_DECIDED = "rta.document.boundary-decided"
    RTA_DOCUMENT_CLASSIFIED = "rta.document.classified"
    RTA_FACT_CONFIRMED = "rta.fact.confirmed"
    RTA_FACT_ADDED = "rta.fact.added"
    RTA_FACT_REJECTED = "rta.fact.rejected"
    RTA_FACT_ASSOCIATED = "rta.fact.associated"
    RTA_FACT_CORRECTED = "rta.fact.corrected"
    RTA_CHECK_RUN = "rta.check.run"
    RTA_ISSUE_CREATED = "rta.issue.created"
    RTA_ISSUE_DECIDED = "rta.issue.decided"
    RTA_FORM_GENERATED = "rta.form.generated"
    RTA_FORM_FIELD_DECIDED = "rta.form.field-decided"
    RTA_FORM_PREFLIGHT_RUN = "rta.form.preflight-run"
    RTA_FORM_APPROVED = "rta.form.approved"
    RTA_FORM_EXPORTED = "rta.form.exported"
    RTA_FORM_MARKED_STALE = "rta.form.marked-stale"
    RTA_REGISTRATION_EVENT_RECORDED = "rta.registration.event-recorded"


@dataclass
class AuditEvent:
    """Domain representation of a persisted audit event."""

    id: str
    user_id: str
    action: str
    target_type: str
    target_id: str
    hash: str
    prev_hash: str
    timestamp: datetime
    matter_id: str | None = None
    actor: str | None = None
    before_ref: str | None = None
    after_ref: str | None = None
    reason: str | None = None
    correlation_id: str = ""
    causation_id: str | None = None
