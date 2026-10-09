"""The closed vocabularies of the RTA matter workflow.

Every enum here is a legal or product distinction that the workflow spec
(`docs/draftly-rta-matter-workflow-v1.md`) refuses to collapse. They live in
`content_governance` because they are governed content shared by the matter,
task, document, verification, check, draft, and approval modules — not tenant
data and not the property of any one runtime aggregate.

Spec cross-references are given per enum so a reader can check the wording
against the authority rather than against this file.
"""

from __future__ import annotations

import enum


class LegalRegime(str, enum.Enum):
    """Registration system that governs the parcel (§3.1).

    Only ``LK_RTA`` has a rule pack. The other regimes exist so a matter can be
    routed out of the RTA workflow instead of being silently treated as RTA.
    """

    LK_RTA = "lk.rta"
    LK_DEED = "lk.deed"
    LK_CONDOMINIUM = "lk.condominium"
    LK_SPECIAL_AREA = "lk.special_area"


class SourceClass(str, enum.Enum):
    """What kind of authority a requirement or rule rests on (§1.1).

    These do not collapse into one generic "required" flag: an Act establishes
    legal effect, an agency instruction establishes current submission
    practice, and a lawyer's checklist establishes professional risk control.
    """

    LAW = "LAW"
    REG = "REG"
    OPS = "OPS"
    LOCAL_OPS = "LOCAL_OPS"
    PRACTICE = "PRACTICE"
    PRODUCT = "PRODUCT"
    UNVERIFIED = "UNVERIFIED"


class SourceConfidence(str, enum.Enum):
    """Confidence in the source proposition itself (§13.1)."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceCurrencyStatus(str, enum.Enum):
    """Whether the source is still known to be operative (§13.1, §13.2.5).

    ``UNKNOWN`` is not "current forever": an undated official page stores its
    retrieval date and stays re-verifiable.
    """

    CURRENT = "CURRENT"
    REVERIFY = "REVERIFY"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class MatterFamily(str, enum.Enum):
    """Lawyer-facing grouping shown instead of 22 flat tiles (§3.2)."""

    OWNERSHIP_CHANGE = "ownership_change"
    AGREEMENT_SECURITY = "agreement_security"
    USE_INTEREST = "use_interest"
    CANCEL_RELEASE = "cancel_release"
    NOTICE_ADMIN = "notice_admin"
    PARCEL_STRUCTURE = "parcel_structure"
    TITLE_SETTLEMENT = "title_settlement"
    DISPUTE_RECTIFICATION = "dispute_rectification"
    CONTROLLED_OTHER = "controlled_other"


class SubtypeKind(str, enum.Enum):
    """Whether a subtype is a prescribed instrument, a statutory process, or a
    registry service (§3.1 namespaces, §3.4)."""

    PRESCRIBED_INSTRUMENT = "PRESCRIBED_INSTRUMENT"
    STATUTORY_PROCESS = "STATUTORY_PROCESS"
    REGISTRY_SERVICE = "REGISTRY_SERVICE"
    CONTROLLED_OTHER = "CONTROLLED_OTHER"


class ExaminationLevel(str, enum.Enum):
    """Draftly workflow decision, not terminology used by the Act (§3.3)."""

    FULL = "FULL"
    FOCUSED = "FOCUSED"
    SPECIAL = "SPECIAL"
    MINIMAL = "MINIMAL"
    TRACKING = "TRACKING"


class ReleaseTier(str, enum.Enum):
    """How far Draftly automates this subtype today (§3.3, §2.2)."""

    V0 = "V0"
    V1 = "V1"
    DEFERRED = "DEFERRED"
    MANUAL_ONLY = "MANUAL_ONLY"


class MatterState(str, enum.Enum):
    """Matter state machine (§10.1, §12.2 ``MatterState``).

    ``MANUAL_SUPPORTED`` and ``LITIGATION_HOLD`` are exception states, not
    terminal failures: evidence and checklist work continue in both.
    """

    INTAKE_DRAFT = "INTAKE_DRAFT"
    ROUTED = "ROUTED"
    EVIDENCE_COLLECTION = "EVIDENCE_COLLECTION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    READY_TO_DRAFT = "READY_TO_DRAFT"
    DRAFTING = "DRAFTING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    SUBMITTED = "SUBMITTED"
    REGISTERED = "REGISTERED"
    CLOSED = "CLOSED"
    MANUAL_SUPPORTED = "MANUAL_SUPPORTED"
    LITIGATION_HOLD = "LITIGATION_HOLD"
    CANCELLED = "CANCELLED"


class AutomationScope(str, enum.Enum):
    """How much of the matter Draftly may automate (§2.3)."""

    ASSESSING = "ASSESSING"
    V0_AUTOMATED = "V0_AUTOMATED"
    MANUAL_SUPPORTED = "MANUAL_SUPPORTED"
    LITIGATION_HOLD = "LITIGATION_HOLD"


class SubtypeDecisionStatus(str, enum.Enum):
    """Whether the exact instrument is still provisional (§12.2 ``Matter``).

    A model or a legacy migration may only ever produce ``PROVISIONAL``.
    """

    PROVISIONAL = "PROVISIONAL"
    LAWYER_CONFIRMED = "LAWYER_CONFIRMED"


class TitleStatus(str, enum.Enum):
    """First gate: is the parcel already on an RTA Title Register? (§Executive 1)."""

    UNKNOWN = "UNKNOWN"
    INITIAL_COMPILATION = "INITIAL_COMPILATION"
    RTA_REGISTERED = "RTA_REGISTERED"


class ParcelKind(str, enum.Enum):
    """Ordinary land versus strata (§2.2, ss. 50–52)."""

    UNKNOWN = "UNKNOWN"
    ORDINARY = "ORDINARY"
    CONDOMINIUM_UNIT = "CONDOMINIUM_UNIT"
    CONVERSION_TO_CONDOMINIUM = "CONVERSION_TO_CONDOMINIUM"


class DispositionScope(str, enum.Enum):
    """Whole parcel, part, or undivided interest (§4.2 Q03; RTA s. 47)."""

    UNKNOWN = "UNKNOWN"
    WHOLE_REGISTERED_PARCEL = "WHOLE_REGISTERED_PARCEL"
    PART_OF_PARCEL = "PART_OF_PARCEL"
    UNDIVIDED_INTEREST = "UNDIVIDED_INTEREST"


class PartyContext(str, enum.Enum):
    """Non-individual party indicators from Q05 (§4.2)."""

    NATURAL_PERSONS_ONLY = "NATURAL_PERSONS_ONLY"
    COMPANY = "COMPANY"
    ESTATE_OR_DECEASED = "ESTATE_OR_DECEASED"
    ATTORNEY_POWER_OF_ATTORNEY = "ATTORNEY_POWER_OF_ATTORNEY"
    PUBLIC_BODY = "PUBLIC_BODY"
    OTHER_NON_INDIVIDUAL = "OTHER_NON_INDIVIDUAL"


class TriState(str, enum.Enum):
    """Answer vocabulary for routing and resolution questions (§4.1).

    ``UNKNOWN`` is a valid routing answer and is never coerced into ``NO``:
    "no document found" creates a missing-evidence task, not a negative legal
    fact (§4.4).
    """

    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AnswerStatus(str, enum.Enum):
    """Provenance of an intake answer (§12.2 ``IntakeAnswer``)."""

    PROVISIONAL = "PROVISIONAL"
    INFERRED = "INFERRED"
    LAWYER_CONFIRMED = "LAWYER_CONFIRMED"
    SUPERSEDED = "SUPERSEDED"


class QuestionStage(str, enum.Enum):
    """When a question is asked (§4.1)."""

    ROUTING = "ROUTING"
    RESOLUTION = "RESOLUTION"
    PRE_DRAFT = "PRE_DRAFT"


class AnswerValueKind(str, enum.Enum):
    """Shape of an accepted answer value, so the API can validate it."""

    TRI_STATE = "TRI_STATE"
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTI_CHOICE = "MULTI_CHOICE"
    TEXT = "TEXT"
    DATE = "DATE"
    MONEY = "MONEY"
    FILE_UPLOAD = "FILE_UPLOAD"


class MandatoryBasis(str, enum.Enum):
    """Why a checklist requirement is on the list (§5.1).

    Shown beside every item so a lawyer can tell a statute from an office
    habit. ``LOCAL_AUTHORITY`` is separated from ``OPERATIONAL`` because a rule
    for one council must never activate globally (§13.2.8).
    """

    LEGAL = "LEGAL"
    REGULATORY = "REGULATORY"
    OPERATIONAL = "OPERATIONAL"
    LAWYER_POLICY = "LAWYER_POLICY"
    PRODUCT_SAFETY = "PRODUCT_SAFETY"
    LOCAL_AUTHORITY = "LOCAL_AUTHORITY"
    CONDITIONAL = "CONDITIONAL"


class RequirementGroup(str, enum.Enum):
    """UI grouping of checklist items (§11.1 Generated Checklist)."""

    LEGAL_REGISTRY = "LEGAL_REGISTRY"
    TITLE_EXAMINATION = "TITLE_EXAMINATION"
    CONDITIONAL = "CONDITIONAL"
    OFFICE_ADDED = "OFFICE_ADDED"


class ApplicabilityStatus(str, enum.Enum):
    """§5.4 — does this requirement apply to this matter?"""

    PROVISIONAL_REQUIRED = "PROVISIONAL_REQUIRED"
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WAIVED_BY_LAWYER = "WAIVED_BY_LAWYER"


class CollectionStatus(str, enum.Enum):
    """§5.4 — has the evidence arrived?"""

    NOT_REQUESTED = "NOT_REQUESTED"
    REQUESTED = "REQUESTED"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"


class DigitalReviewStatus(str, enum.Enum):
    """§5.4 — how far has the digital copy been reviewed?

    ``AI_ORGANIZED`` is deliberately distinct from ``LAWYER_CONFIRMED``; the
    pipeline can reach the first and never the second (§6.4).
    """

    UNREVIEWED = "UNREVIEWED"
    AI_ORGANIZED = "AI_ORGANIZED"
    LAWYER_CONFIRMED = "LAWYER_CONFIRMED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class PhysicalOriginalStatus(str, enum.Enum):
    """§5.4 — physical original custody.

    ``ORIGINAL_INSPECTED`` requires a named human reviewer, a timestamp, an
    inspection method, and an audit event. No scan, OCR result, or model
    confidence may set it (§Executive 5, §5.4 rules).
    """

    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"
    COPY_ONLY = "COPY_ONLY"
    ORIGINAL_REPORTED = "ORIGINAL_REPORTED"
    ORIGINAL_INSPECTED = "ORIGINAL_INSPECTED"


class CurrencyStatus(str, enum.Enum):
    """§5.4 — is the evidence still current enough?"""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


class ConsistencyStatus(str, enum.Enum):
    """§5.4 — does the evidence agree with the rest of the matter?"""

    NOT_CHECKED = "NOT_CHECKED"
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    INCONCLUSIVE = "INCONCLUSIVE"


class ResolutionStatus(str, enum.Enum):
    """§5.4 — the lawyer-facing disposition of the item."""

    OPEN = "OPEN"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    SATISFIED = "SATISFIED"
    EXCEPTION_ACCEPTED = "EXCEPTION_ACCEPTED"
    REMEDIATED = "REMEDIATED"
    CLOSED = "CLOSED"


class ChecklistItemLifecycle(str, enum.Enum):
    """Derived lifecycle for the UI (§10.4). Computed, never stored as truth."""

    NOT_TRIGGERED = "NOT_TRIGGERED"
    OPEN = "OPEN"
    REQUESTED = "REQUESTED"
    MISSING = "MISSING"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    REVIEW_READY = "REVIEW_READY"
    SATISFIED = "SATISFIED"


class SourceFileState(str, enum.Enum):
    """§10.2 — ingestion state machine for immutable uploaded bytes.

    Source bytes never transition to "edited". A corrected file is a new source
    with a ``DERIVED_FROM`` link.
    """

    UPLOAD_INITIATED = "UPLOAD_INITIATED"
    QUARANTINED = "QUARANTINED"
    VALIDATED = "VALIDATED"
    STORED = "STORED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ProcessingFailureReason(str, enum.Enum):
    """Why processing did not produce a result — always recoverable-explained.

    ``NOT_CONFIGURED`` is the honest answer when no OCR/classification provider
    is wired: the document is stored and readable, nothing was processed, and
    nothing pretends otherwise.
    """

    NOT_CONFIGURED = "NOT_CONFIGURED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    DATA_PROTECTION_GATE = "DATA_PROTECTION_GATE"
    TIMEOUT = "TIMEOUT"


class BoundaryStatus(str, enum.Enum):
    """§12.2 ``DocumentFragment`` — page-range confidence state."""

    CANDIDATE = "CANDIDATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFIRMED = "CONFIRMED"


class DocumentClassStatus(str, enum.Enum):
    """§12.2 ``DetectedDocument`` — classification state.

    ``UNIDENTIFIED`` is a first-class result, never silently relabelled
    ``other`` (§6.3).
    """

    UNIDENTIFIED = "UNIDENTIFIED"
    AI_ORGANIZED = "AI_ORGANIZED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LAWYER_CONFIRMED = "LAWYER_CONFIRMED"
    REJECTED = "REJECTED"


class DocumentVersionRelationship(str, enum.Enum):
    """§6.3 — how one detected document relates to another."""

    CURRENT = "CURRENT"
    POSSIBLE_VERSION = "POSSIBLE_VERSION"
    SUPERSEDED = "SUPERSEDED"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"


class EvidenceRegionType(str, enum.Enum):
    """§6.2.4 — region types are separate because they carry different weight.

    Detecting a signature is not a statement that the signature is valid
    (§6.3).
    """

    PRINTED_TEXT = "PRINTED_TEXT"
    HANDWRITING = "HANDWRITING"
    STAMP = "STAMP"
    SIGNATURE = "SIGNATURE"
    SEAL = "SEAL"
    PHOTO = "PHOTO"
    TABLE = "TABLE"


class FactStatus(str, enum.Enum):
    """§10.5 — extracted-fact lifecycle.

    A critical fact reaches ``LAWYER_CONFIRMED`` only through a human decision,
    whatever the model confidence (§6.4).
    """

    EXTRACTED_CANDIDATE = "EXTRACTED_CANDIDATE"
    REJECTED = "REJECTED"
    CORROBORATED = "CORROBORATED"
    CONFLICTED = "CONFLICTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LAWYER_CONFIRMED = "LAWYER_CONFIRMED"
    LOCKED_FOR_FORM = "LOCKED_FOR_FORM"
    SUPERSEDED = "SUPERSEDED"


class CheckOutcome(str, enum.Enum):
    """§7.1 — a "pass" means only that the encoded comparison passed."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_RUN = "NOT_RUN"


class IssueSeverity(str, enum.Enum):
    """§7.3 — gates on draft generation, approval, and export."""

    INFORMATION = "INFORMATION"
    WARNING = "WARNING"
    HIGH_RISK = "HIGH_RISK"
    BLOCKING = "BLOCKING"


class BlockerKind(str, enum.Enum):
    """§7.3 — who, if anyone, may override the blocker.

    ``STATUTORY`` cannot be overridden inside Draftly at all.
    """

    STATUTORY = "STATUTORY"
    EVIDENCE = "EVIDENCE"
    V0_SCOPE = "V0_SCOPE"
    OFFICE_POLICY = "OFFICE_POLICY"
    PROFESSIONAL_JUDGMENT = "PROFESSIONAL_JUDGMENT"


class IssueState(str, enum.Enum):
    """§10.6 — legal-issue lifecycle.

    ``ACCEPTED_RISK`` never changes a failed deterministic check to ``PASS``;
    it records a separate disposition (§7.3).
    """

    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"


class DisputeStage(str, enum.Enum):
    """§8.3 — title-settlement and post-registration challenge stages.

    A section 12 notice is not proof of a dispute and a section 14 declaration
    is not necessarily final registration (§Executive 8).
    """

    NO_INDICIA_FOUND = "NO_INDICIA_FOUND"
    S12_NOTICE_PUBLISHED = "S12_NOTICE_PUBLISHED"
    CLAIM_WINDOW_OPEN = "CLAIM_WINDOW_OPEN"
    CLAIMS_FILED = "CLAIMS_FILED"
    S13_INVESTIGATION_PENDING = "S13_INVESTIGATION_PENDING"
    CONCILIATION_PENDING = "CONCILIATION_PENDING"
    S14_DECLARATION_PUBLISHED = "S14_DECLARATION_PUBLISHED"
    S21_DC_REFERRED = "S21_DC_REFERRED"
    S22_APPEAL_FILED = "S22_APPEAL_FILED"
    COURT_INQUIRY_PENDING = "COURT_INQUIRY_PENDING"
    COURT_ORDER_ISSUED = "COURT_ORDER_ISSUED"
    SCHEDULE_PREPARED = "SCHEDULE_PREPARED"
    INITIAL_REGISTER_CREATED = "INITIAL_REGISTER_CREATED"
    S29_CHALLENGE_NOTED = "S29_CHALLENGE_NOTED"
    RECTIFICATION_PENDING = "RECTIFICATION_PENDING"
    FINAL_REGISTER_CONFIRMED = "FINAL_REGISTER_CONFIRMED"


class TemplateNamespace(str, enum.Enum):
    """§9.1 — form number alone is never a primary key.

    ``rta.reg.2022.form.31`` (register an address) and ``rta.ops.tire.31``
    (apply for a new Title Certificate) are different forms in different
    namespaces and must never collide.
    """

    REGULATION = "REGULATION"
    OPERATIONAL = "OPERATIONAL"
    COURT = "COURT"
    TITLE_CERTIFICATE = "TITLE_CERTIFICATE"
    TITLE_REGISTER = "TITLE_REGISTER"


class TemplateStatus(str, enum.Enum):
    """§9.5 — a transcription is not an approved production rendering."""

    DRAFT_TRANSCRIPTION = "DRAFT_TRANSCRIPTION"
    VALIDATED = "VALIDATED"
    SUPERSEDED = "SUPERSEDED"


class GeneratedFormState(str, enum.Enum):
    """§10.7 — generated-form lifecycle. Export changes no legal effect."""

    GENERATED_DRAFT = "GENERATED_DRAFT"
    UNRESOLVED = "UNRESOLVED"
    REVIEW_READY = "REVIEW_READY"
    LAWYER_REVIEWED = "LAWYER_REVIEWED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    SUBMITTED = "SUBMITTED"
    REGISTERED = "REGISTERED"
    STALE_TEMPLATE = "STALE_TEMPLATE"
    STALE_AFTER_APPROVAL = "STALE_AFTER_APPROVAL"


class UnresolvedReason(str, enum.Enum):
    """Why a form field could not be populated (§9.4).

    A missing value renders a named token such as
    ``[[UNRESOLVED: transferee_nic]]`` — never blank space or invented text.
    """

    NO_FACT = "NO_FACT"
    FACT_NOT_CONFIRMED = "FACT_NOT_CONFIRMED"
    FACT_CONFLICTED = "FACT_CONFLICTED"
    FACT_SUPERSEDED = "FACT_SUPERSEDED"
    BLOCKED_BY_ISSUE = "BLOCKED_BY_ISSUE"


class RegistrationEventType(str, enum.Enum):
    """§9.6 — attestation, presentation, and registration are separate events.

    Export is none of them.
    """

    ATTESTED = "ATTESTED"
    PRESENTED = "PRESENTED"
    DAY_BOOK_ENTERED = "DAY_BOOK_ENTERED"
    REGISTERED = "REGISTERED"
    REFUSED = "REFUSED"
    RETURNED = "RETURNED"


class RtaWorkflowRole(str, enum.Enum):
    """The six workflow roles the RTA spec §12.5 requires Draftly to separate.

    These are **matter-scoped workflow roles**, not new account roles. The
    account role vocabulary is fixed by `auth-service.md` §10.6 and is not
    extended here; `rta_roles.py` maps an account role plus matter assignment
    onto one of these.
    """

    CASE_ASSISTANT = "CASE_ASSISTANT"
    LAWYER_REVIEWER = "LAWYER_REVIEWER"
    RESPONSIBLE_LAWYER = "RESPONSIBLE_LAWYER"
    TEMPLATE_COUNSEL = "TEMPLATE_COUNSEL"
    OFFICE_ADMIN = "OFFICE_ADMIN"
    AUDITOR = "AUDITOR"


class ReviewTargetType(str, enum.Enum):
    """§12.2 ``ReviewDecision`` — what a recorded human decision was about."""

    DOCUMENT_BOUNDARY = "DOCUMENT_BOUNDARY"
    DOCUMENT_CLASS = "DOCUMENT_CLASS"
    FACT = "FACT"
    CHECKLIST_ITEM = "CHECKLIST_ITEM"
    ISSUE = "ISSUE"
    FORM_FIELD = "FORM_FIELD"
    TEMPLATE = "TEMPLATE"
    INTAKE_ANSWER = "INTAKE_ANSWER"


class ApprovalTargetType(str, enum.Enum):
    """§12.2 ``Approval`` — what was approved."""

    GENERATED_FORM = "GENERATED_FORM"
    MATTER_PREFLIGHT = "MATTER_PREFLIGHT"
    PHYSICAL_ORIGINAL_INSPECTION = "PHYSICAL_ORIGINAL_INSPECTION"
