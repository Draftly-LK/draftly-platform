"""Party domain models — protected identity tier (no FastAPI/SQLAlchemy imports)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


class PartyKind(str, enum.Enum):
    NATURAL_PERSON = "natural-person"
    COMPANY = "company"
    PARTNERSHIP = "partnership"
    TRUST = "trust"
    STATUTORY_BODY = "statutory-body"
    OTHER = "other"


class RiskRating(str, enum.Enum):
    UNASSESSED = "unassessed"
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class ScreeningStatus(str, enum.Enum):
    NOT_RUN = "not-run"
    CLEAR = "clear"
    POTENTIAL_MATCH = "potential-match"
    CONFIRMED_MATCH = "confirmed-match"


class ConfidentialityLevel(str, enum.Enum):
    STANDARD = "standard"
    PRIVATE_MATTER = "private-matter"
    RESTRICTED_COMPLIANCE = "restricted-compliance"


class EvidenceKind(str, enum.Enum):
    NIC = "nic"
    PASSPORT = "passport"
    DRIVING_LICENCE = "driving-licence"
    BIRTH_CERTIFICATE = "birth-certificate"
    COMPANY_REGISTRATION = "company-registration"
    BOARD_RESOLUTION = "board-resolution"
    POWER_OF_ATTORNEY = "power-of-attorney"
    UTILITY_BILL = "utility-bill"
    OTHER = "other"


class EvidenceState(str, enum.Enum):
    RECORDED = "recorded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class OwnershipKind(str, enum.Enum):
    SHAREHOLDING = "shareholding"
    VOTING_RIGHTS = "voting-rights"
    CONTROL_OTHER = "control-other"
    SENIOR_MANAGING = "senior-managing"


class BeneficialOwnerState(str, enum.Enum):
    RECORDED = "recorded"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"


class CddLevel(str, enum.Enum):
    STANDARD = "standard"
    SIMPLIFIED = "simplified"
    ENHANCED = "enhanced"


class CddOutcome(str, enum.Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class ScreeningOutcome(str, enum.Enum):
    CLEAR = "clear"
    POTENTIAL_MATCH = "potential-match"
    CONFIRMED_MATCH = "confirmed-match"


@dataclass
class Party:
    id: str
    user_id: str
    party_kind: PartyKind
    display_name: str
    name_parts: dict[str, Any]
    former_names: list[str]
    date_of_birth: date | None
    registration_number: str | None
    nationality: str | None
    residency_status: str | None
    addresses: list[dict[str, Any]]
    contact_points: list[dict[str, Any]]
    risk_rating: RiskRating
    screening_status: ScreeningStatus
    confidentiality_level: ConfidentialityLevel
    merged_into_party_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass
class IdentityEvidence:
    id: str
    party_id: str
    evidence_kind: EvidenceKind
    identifier_value: str
    identifier_last4: str
    issued_on: date | None
    expires_on: date | None
    issuing_authority: str | None
    document_id: str | None
    document_version_id: str | None
    evidence_span: dict[str, Any] | None
    verified_by: str | None
    verified_at: datetime | None
    state: EvidenceState
    supersedes_evidence_id: str | None
    version: int


@dataclass
class BeneficialOwner:
    id: str
    party_id: str
    owner_party_id: str
    ownership_kind: OwnershipKind
    percentage: float | None
    evidence_refs: list[str]
    determined_by: str
    determined_at: datetime
    state: BeneficialOwnerState


@dataclass
class CddAssessment:
    id: str
    party_id: str
    matter_id: str | None
    level: CddLevel
    risk_factors: list[str]
    outcome: CddOutcome
    assessed_by: str
    assessed_at: datetime
    review_due_on: date | None
    policy_version: str
    version: int


@dataclass
class ScreeningResult:
    id: str
    party_id: str
    list_version: str
    provider_ref: str
    outcome: ScreeningOutcome
    match_count: int
    reviewed_by: str | None
    reviewed_at: datetime | None
    disposition_reason: str | None
    confidentiality_level: ConfidentialityLevel
    created_at: datetime


@dataclass
class ScreeningMatchDetail:
    """Restricted-compliance payload — never joined into ordinary party reads."""

    screening_result_id: str
    provider_payload: dict[str, Any] = field(default_factory=dict)
    match_narrative: str | None = None
    list_entry_ref: str | None = None


@dataclass
class DuplicateCandidate:
    party_id: str
    display_name: str
    match_reason: str
    strength: str
