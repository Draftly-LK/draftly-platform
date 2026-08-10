"""Notarial register domain models — attestations, protocol, Form F, returns."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime


class InstrumentKind(str, enum.Enum):
    TRANSFER = "transfer"
    GIFT = "gift"
    LEASE = "lease"
    MORTGAGE = "mortgage"
    POA = "poa"
    OTHER = "other"


class RegistrationRegime(str, enum.Enum):
    DEED = "deed"
    RTA = "rta"
    CONDOMINIUM = "condominium"
    SPECIAL_AREA = "special-area"


class SourceKind(str, enum.Enum):
    EXPORT = "export"
    EXTERNAL = "external"


class AttestationCondition(str, enum.Enum):
    READ = "read"
    READ_AND_EXPLAINED = "read-and-explained"
    ATTORNEY = "attorney"
    ILLITERATE = "illiterate"
    IMPRESSION = "impression"
    CORPORATE = "corporate"
    MULTIPLE_NOTARIES = "multiple-notaries"


class AttestationState(str, enum.Enum):
    DRAFT = "draft"
    ATTESTED = "attested"
    REGISTRATION_SUBMITTED = "registration-submitted"
    REGISTRATION_ACKNOWLEDGED = "registration-acknowledged"
    REGISTRATION_DEFECTIVE = "registration-defective"
    REGISTERED = "registered"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


class RegisterEntryState(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class ProtocolCopyKind(str, enum.Enum):
    ORIGINAL = "original"
    DUPLICATE = "duplicate"
    CERTIFIED_COPY = "certified-copy"
    OFFICE_COPY = "office-copy"


class ProtocolState(str, enum.Enum):
    HELD = "held"
    ISSUED = "issued"
    RETURNED = "returned"
    TRANSFERRED = "transferred"
    DESTROYED = "destroyed"


class MonthlyReturnState(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CERTIFIED = "certified"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"


class RegistrationSubmissionState(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    DEFECTIVE = "defective"


@dataclass
class PartyRef:
    party_id: str
    capacity: str | None = None
    evidence_ref: str | None = None


@dataclass
class Attestation:
    id: str
    user_id: str
    matter_id: str
    instrument_kind: InstrumentKind
    registration_regime: RegistrationRegime
    source_kind: SourceKind
    export_id: str | None
    draft_version_id: str | None
    content_hash: str | None
    attestation_clause_definition_id: str
    attestation_clause_version: str
    attestation_conditions: list[AttestationCondition]
    notary_user_id: str
    practising_jurisdiction_id: str
    registration_jurisdiction_id: str
    instrument_language: str
    attested_at: datetime
    place_of_execution: str
    executants: list[PartyRef]
    witnesses: list[PartyRef]
    consideration_recorded: bool | None
    state: AttestationState
    version: int
    external_reason: str | None = None


@dataclass
class RegisterEntry:
    id: str
    user_id: str
    notary_user_id: str
    register_year: int
    serial_number: int
    attestation_id: str
    entry_date: date
    instrument_kind: InstrumentKind
    party_summary_ref: str
    consideration_ref: str | None
    folio_ref: str | None
    state: RegisterEntryState
    cancellation_reason: str | None
    created_at: datetime


@dataclass
class ProtocolRecord:
    id: str
    attestation_id: str
    copy_kind: ProtocolCopyKind
    storage_ref: str | None
    physical_location: str | None
    custodian_user_id: str
    issued_to: str | None
    issued_at: datetime | None
    returned_at: datetime | None
    retention_class: str
    state: ProtocolState


@dataclass
class RegistrationSubmission:
    id: str
    attestation_id: str
    user_id: str
    state: RegistrationSubmissionState
    registry_id: str | None
    submitted_at: datetime | None
    acknowledged_at: datetime | None
    defect_notes: str | None
    version: int


@dataclass
class MonthlyReturnPeriod:
    id: str
    user_id: str
    notary_user_id: str
    period_start: date
    period_end: date
    instrument_ids: list[str]
    is_nil_return: bool
    components: list[str]
    component_states: dict[str, str]
    certified_by: str | None
    certified_at: datetime | None
    submitted_at: datetime | None
    acknowledged_at: datetime | None
    state: MonthlyReturnState
    version: int = 1


@dataclass
class ApprovedInstrumentSnapshot:
    """Pinned export approval used when attesting."""

    export_id: str
    draft_version_id: str
    content_hash: str
    matter_id: str


@dataclass
class CreateAttestationInput:
    matter_id: str
    instrument_kind: InstrumentKind
    registration_regime: RegistrationRegime
    source_kind: SourceKind
    export_id: str | None
    attestation_clause_definition_id: str
    attestation_clause_version: str
    attestation_conditions: list[AttestationCondition]
    practising_jurisdiction_id: str
    registration_jurisdiction_id: str
    instrument_language: str
    attested_at: datetime
    place_of_execution: str
    executants: list[PartyRef]
    witnesses: list[PartyRef]
    consideration_recorded: bool | None
    party_summary_ref: str
    consideration_ref: str | None = None
    folio_ref: str | None = None
    external_reason: str | None = None
    approved_instrument_fixture: bool = False


@dataclass
class AddProtocolInput:
    copy_kind: ProtocolCopyKind
    storage_ref: str | None = None
    physical_location: str | None = None
    custodian_user_id: str | None = None
    retention_class: str = "notarial-protocol"


@dataclass
class RegistrationSubmissionInput:
    registry_id: str


@dataclass
class RegistrationAcknowledgementInput:
    outcome: str
    registry_reference: str | None = None


@dataclass
class RegistrationDefectInput:
    defect_notes: str


@dataclass
class CollectionInput:
    ready_at: datetime | None = None


@dataclass
class RegisterEntryFilters:
    notary_user_id: str | None = None
    register_year: int | None = None
    limit: int = 50
    offset: int = 0


@dataclass
class OutboxEvent:
    event_type: str
    payload: dict[str, str | int | bool | list[str] | None]
    aggregate_id: str


@dataclass
class MonthlyReturnPeriodRead:
    period: MonthlyReturnPeriod
    attestation_count: int = 0


@dataclass
class RegisterEntriesPage:
    items: list[RegisterEntry]
    total: int


@dataclass
class AttestationBundle:
    attestation: Attestation
    register_entry: RegisterEntry
    protocol: ProtocolRecord | None = None
    registration: RegistrationSubmission | None = None
