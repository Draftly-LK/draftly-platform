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
    ORGANISATION = "organisation"
    RETENTION = "retention"


class AuditAction(str, enum.Enum):
    """Closed action enum (audit-service.md §3.2 — no free strings)."""

    # Matter
    MATTER_CREATED = "matter.created"
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
    # Compliance / retention
    RETENTION_HOLD_PLACED = "retention.hold.placed"
    RETENTION_DESTRUCTION_APPROVED = "retention.destruction.approved"


@dataclass
class AuditEvent:
    """Domain representation of a persisted audit event."""

    id: str
    organisation_id: str
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
