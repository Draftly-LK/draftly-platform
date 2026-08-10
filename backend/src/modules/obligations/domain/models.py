"""Obligations domain models — pure entities, no framework imports."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


class ObligationScope(str, enum.Enum):
    USER = "user"
    MATTER = "matter"
    FIRM = "firm"


class ObligationClass(str, enum.Enum):
    LEGAL_DEADLINE = "legal-deadline"
    COMPLIANCE_DEADLINE = "compliance-deadline"
    CLIENT_COMMITMENT = "client-commitment"
    INTERNAL_TARGET = "internal-target"
    FOLLOW_UP = "follow-up"
    ADMINISTRATIVE_REMINDER = "administrative-reminder"
    RETENTION_REVIEW = "retention-review"


class ObligationType(str, enum.Enum):
    COURT_DATE = "court-date"
    FILING_DEADLINE = "filing-deadline"
    SERVICE_DEADLINE = "service-deadline"
    LIMITATION_DEADLINE = "limitation-deadline"
    NOTARIAL_MONTHLY_RETURN = "notarial-monthly-return"
    NOTARIAL_REGISTRATION = "notarial-registration"
    NOTARIAL_ANNUAL_CERTIFICATE = "notarial-annual-certificate"
    AML_CDD = "aml-cdd"
    AML_SANCTIONS_REPORT = "aml-sanctions-report"
    AML_STR = "aml-str"
    AML_POLICY_REVIEW = "aml-policy-review"
    CLIENT_FOLLOW_UP = "client-follow-up"
    DOCUMENT_REQUEST = "document-request"
    LAWYER_REVIEW = "lawyer-review"
    SIGNING_APPOINTMENT = "signing-appointment"
    REGISTRY_FOLLOW_UP = "registry-follow-up"
    DOCUMENT_COLLECTION = "document-collection"
    RETENTION_REVIEW = "retention-review"
    INTERNAL_ADMIN = "internal-admin"


class ObligationHardness(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"


class ObligationStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting-confirmation"
    UPCOMING = "upcoming"
    DUE = "due"
    OVERDUE = "overdue"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class LawyerConfirmationStatus(str, enum.Enum):
    NOT_REQUIRED = "not-required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"


class ConfidentialityLevel(str, enum.Enum):
    STANDARD = "standard"
    PRIVATE_MATTER = "private-matter"
    RESTRICTED_COMPLIANCE = "restricted-compliance"


class SourceType(str, enum.Enum):
    MANUAL = "manual"
    TASK = "task"
    CHECK = "check"
    RULE = "rule"
    EVENT = "event"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    ATTESTATION = "attestation"
    MONTHLY_CLOSE = "monthly-close"
    ANNUAL = "annual"
    DESIGNATED_PERSON = "designated-person"


class ReminderType(str, enum.Enum):
    ADVANCE = "advance"
    DUE_DAY = "due-day"
    OVERDUE = "overdue"


@dataclass
class LawyerConfirmation:
    status: LawyerConfirmationStatus
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    reason: str | None = None
    original_due_at: datetime | None = None


@dataclass
class ReminderOccurrence:
    id: str
    organisation_id: str
    obligation_id: str
    recipient_user_id: str
    reminder_type: ReminderType
    scheduled_for: datetime
    emitted_at: datetime | None = None
    event_id: str | None = None


@dataclass
class Obligation:
    id: str
    organisation_id: str
    scope: ObligationScope
    obligation_type: ObligationType
    obligation_class: ObligationClass
    label_key: str
    source_type: SourceType
    source_id: str
    trigger_type: TriggerType
    trigger_date: datetime
    due_at: datetime
    timezone: str
    hardness: ObligationHardness
    status: ObligationStatus
    assignee_user_id: str
    reminder_policy_id: str
    confidentiality_level: ConfidentialityLevel
    lawyer_confirmation: LawyerConfirmation
    version: int
    created_at: datetime
    updated_at: datetime
    matter_id: str | None = None
    owner_user_id: str | None = None
    source_version: str | None = None
    legal_authority_ref: str | None = None
    trigger_id: str | None = None
    calculation_rule_id: str | None = None
    calculation_version: str | None = None
    calculation_explanation: str | None = None
    backup_assignee_user_id: str | None = None
    recurrence_rule: str | None = None
    escalation_policy_id: str | None = None
    completion_evidence_ref: str | None = None
    completed_at: datetime | None = None
    completed_by: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None
    cancellation_reason: str | None = None


@dataclass
class DeadlineCalculation:
    trigger_date: datetime
    rule_id: str
    rule_version: str
    raw_due_at: datetime
    explanation: str
    adjusted_due_at: datetime | None = None
    adjustment_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReminderScheduleSpec:
    reminder_type: ReminderType
    offset_days: int


@dataclass
class ApprovedDeadlineRule:
    id: str
    version: str
    obligation_type: ObligationType
    obligation_class: ObligationClass
    trigger_type: TriggerType
    timezone: str
    explanation_template: str
    reminder_policy_id: str
    hardness: ObligationHardness = ObligationHardness.HARD
    label_key: str = "obligation.label.fixture"
