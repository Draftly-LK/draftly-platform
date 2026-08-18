"""API schemas for party_service — camelCase wire shapes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Every legally significant field is a closed enum on the wire, so an unknown
# value is a 422 from the schema rather than a 500 from the domain constructor
# (service-definition-of-done.md §3).
PartyKindLiteral = Literal[
    "natural-person", "company", "partnership", "trust", "statutory-body", "other"
]
ConfidentialityLiteral = Literal["standard", "private-matter", "restricted-compliance"]
EvidenceKindLiteral = Literal[
    "nic",
    "passport",
    "driving-licence",
    "birth-certificate",
    "company-registration",
    "board-resolution",
    "power-of-attorney",
    "utility-bill",
    "other",
]
EvidenceStateLiteral = Literal["recorded", "verified", "rejected", "expired", "superseded"]
OwnershipKindLiteral = Literal["shareholding", "voting-rights", "control-other", "senior-managing"]
CddLevelLiteral = Literal["standard", "simplified", "enhanced"]
CddOutcomeLiteral = Literal["pending", "complete", "blocked"]
ScreeningOutcomeLiteral = Literal["clear", "potential-match", "confirmed-match"]
ScreeningStatusLiteral = Literal["not-run", "clear", "potential-match", "confirmed-match"]
RiskRatingLiteral = Literal["unassessed", "low", "standard", "high"]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PageSchema(CamelModel):
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class PagedResponse[ItemT](CamelModel):
    """The one list envelope (api-conventions.md §2) — no unbounded arrays."""

    items: list[ItemT]
    page: PageSchema


class CreatePartyRequest(CamelModel):
    party_kind: PartyKindLiteral
    display_name: str
    name_parts: dict[str, Any] = Field(default_factory=dict)
    former_names: list[str] = Field(default_factory=list)
    date_of_birth: date | None = None
    registration_number: str | None = None
    nationality: str | None = None
    residency_status: str | None = None
    addresses: list[dict[str, Any]] = Field(default_factory=list)
    contact_points: list[dict[str, Any]] = Field(default_factory=list)
    confidentiality_level: ConfidentialityLiteral = "standard"


class PatchPartyRequest(CamelModel):
    display_name: str | None = None


class PartyReadSchema(CamelModel):
    id: str
    party_kind: PartyKindLiteral
    display_name: str
    name_parts: dict[str, Any]
    former_names: list[str]
    date_of_birth: date | None
    registration_number: str | None
    nationality: str | None
    residency_status: str | None
    addresses: list[dict[str, Any]]
    contact_points: list[dict[str, Any]]
    risk_rating: RiskRatingLiteral
    # Null when the caller may not know whether a screening record exists at all
    # (party-service.md §3.5). Absence and denial are indistinguishable.
    screening_status: ScreeningStatusLiteral | None
    confidentiality_level: ConfidentialityLiteral
    effective_confidentiality: ConfidentialityLiteral
    merged_into_party_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    duplicate_candidates: list[DuplicateCandidateSchema] = Field(default_factory=list)


class DuplicateCandidateSchema(CamelModel):
    party_id: str
    display_name: str
    match_reason: str
    strength: str


class PartyListItemSchema(CamelModel):
    id: str
    display_name: str
    party_kind: PartyKindLiteral
    screening_status: ScreeningStatusLiteral | None
    version: int


class RecordIdentityEvidenceRequest(CamelModel):
    evidence_kind: EvidenceKindLiteral
    identifier_value: str
    issued_on: date | None = None
    expires_on: date | None = None
    issuing_authority: str | None = None
    document_id: str | None = None
    document_version_id: str | None = None
    evidence_span: dict[str, Any] | None = None
    supersedes_evidence_id: str | None = None


class IdentityEvidenceReadSchema(CamelModel):
    id: str
    party_id: str
    evidence_kind: EvidenceKindLiteral
    identifier_last4: str
    issued_on: date | None
    expires_on: date | None
    issuing_authority: str | None
    document_id: str | None
    document_version_id: str | None
    evidence_span: dict[str, Any] | None
    state: EvidenceStateLiteral
    supersedes_evidence_id: str | None
    version: int


class IdentityValueReadSchema(CamelModel):
    evidence_id: str
    identifier_value: str


class RecordBeneficialOwnerRequest(CamelModel):
    owner_party_id: str
    ownership_kind: OwnershipKindLiteral
    percentage: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class BeneficialOwnerReadSchema(CamelModel):
    id: str
    party_id: str
    owner_party_id: str
    ownership_kind: OwnershipKindLiteral
    percentage: float | None
    evidence_refs: list[str]
    state: str


class RecordCddRequest(CamelModel):
    matter_id: str | None = None
    level: CddLevelLiteral
    risk_factors: list[str] = Field(default_factory=list)
    outcome: CddOutcomeLiteral
    review_due_on: date | None = None
    policy_version: str


class CddAssessmentReadSchema(CamelModel):
    id: str
    party_id: str
    matter_id: str | None
    level: CddLevelLiteral
    risk_factors: list[str]
    outcome: CddOutcomeLiteral
    assessed_by: str
    assessed_at: datetime
    review_due_on: date | None
    policy_version: str
    version: int


class ScreeningMatchDetailRequest(CamelModel):
    match_narrative: str | None = None
    list_entry_ref: str | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class RecordScreeningRequest(CamelModel):
    list_version: str
    provider_ref: str
    outcome: ScreeningOutcomeLiteral
    match_count: int = 0
    match_detail: ScreeningMatchDetailRequest | None = None


class ScreeningResultReadSchema(CamelModel):
    id: str
    party_id: str
    list_version: str
    provider_ref: str
    outcome: ScreeningOutcomeLiteral
    match_count: int
    created_at: datetime


class DuplicateProbeRequest(CamelModel):
    party_id: str
    identifier_value: str | None = None


class DuplicateProbeResponse(CamelModel):
    candidates: list[DuplicateCandidateSchema]


class MatterPartyReadSchema(CamelModel):
    id: str
    display_name: str
    party_kind: PartyKindLiteral


class VerifyIdentityEvidenceRequest(CamelModel):
    """No body fields: verification is a state transition, not new content."""


class MergePartiesRequest(CamelModel):
    source_party_id: str
    target_party_id: str
    reason: str = Field(min_length=1)


class ScreeningResultListItemSchema(CamelModel):
    id: str
    outcome: ScreeningOutcomeLiteral
    match_count: int
    list_version: str
    created_at: str
