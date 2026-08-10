"""Party module port definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from src.modules.auth.ports import AuditPort
from src.modules.party.domain.models import (
    BeneficialOwner,
    CddAssessment,
    IdentityEvidence,
    Party,
    ScreeningMatchDetail,
    ScreeningResult,
)
from src.platform.pagination import DEFAULT_PAGE_LIMIT, Cursor

__all__ = [
    "AuditPort",
    "PartyRepository",
    "IdentityEvidenceRepository",
    "ScreeningPort",
    "FieldEncryptionPort",
    "MatterAccessPort",
    "EventPort",
    "DomainEvent",
    "CreatePartyInput",
    "RecordIdentityEvidenceInput",
    "RecordCddInput",
    "RecordScreeningInput",
    "PartyListFilter",
]


@dataclass(frozen=True)
class DomainEvent:
    """An event published to the registry in events.md §5.

    The payload is asserted against the registry in the contract tests. It
    carries identifiers and closed enums only — never a name, an identifier
    value, a list entry, or a suspicion narrative (events.md §2).
    """

    name: str
    user_id: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    correlation_id: str = ""


@dataclass
class CreatePartyInput:
    party_kind: str
    display_name: str
    name_parts: dict[str, Any]
    former_names: list[str]
    date_of_birth: date | None
    registration_number: str | None
    nationality: str | None
    residency_status: str | None
    addresses: list[dict[str, Any]]
    contact_points: list[dict[str, Any]]
    confidentiality_level: str


@dataclass
class RecordIdentityEvidenceInput:
    evidence_kind: str
    identifier_value: str
    issued_on: date | None
    expires_on: date | None
    issuing_authority: str | None
    document_id: str | None
    document_version_id: str | None
    evidence_span: dict[str, Any] | None
    supersedes_evidence_id: str | None


@dataclass
class RecordCddInput:
    matter_id: str | None
    level: str
    risk_factors: list[str]
    outcome: str
    review_due_on: date | None
    policy_version: str


@dataclass
class RecordScreeningInput:
    list_version: str
    provider_ref: str
    outcome: str
    match_count: int
    match_detail: ScreeningMatchDetail | None


@dataclass
class PartyListFilter:
    query: str | None = None
    limit: int = DEFAULT_PAGE_LIMIT
    cursor: Cursor | None = None


@dataclass
class PartyPage:
    items: list[Party] = field(default_factory=list)
    has_more: bool = False


class PartyRepository(Protocol):
    """Every method takes `user_id` first and filters on it first (§9)."""

    async def create(self, party: Party) -> Party: ...

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None: ...

    async def list_for_user(self, user_id: str, filter_: PartyListFilter) -> PartyPage: ...

    async def update(self, party: Party, expected_version: int) -> Party: ...

    async def find_by_registration_number(
        self,
        user_id: str,
        registration_number: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]: ...

    async def find_by_normalised_name_and_dob(
        self,
        user_id: str,
        normalised_name: str,
        date_of_birth: date,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]: ...

    async def find_by_normalised_name_and_address(
        self,
        user_id: str,
        normalised_name: str,
        address_fingerprint: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]: ...

    async def repoint_dependents(
        self,
        user_id: str,
        source_party_id: str,
        target_party_id: str,
    ) -> int: ...


class IdentityEvidenceRepository(Protocol):
    """Every method takes `user_id` first and filters on it first (§9)."""

    async def append_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence: ...

    async def get_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> IdentityEvidence | None: ...

    async def list_evidence_for_party(
        self,
        user_id: str,
        party_id: str,
    ) -> list[IdentityEvidence]: ...

    async def mark_evidence_state(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
        *,
        state: str,
        expected_version: int,
        verified_by: str | None = None,
        verified_at: Any | None = None,
    ) -> IdentityEvidence: ...

    async def find_by_blind_index(
        self,
        user_id: str,
        blind_index: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[tuple[Party, IdentityEvidence]]: ...

    async def decrypt_identifier(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> str: ...

    async def add_beneficial_owner(
        self, user_id: str, owner: BeneficialOwner
    ) -> BeneficialOwner: ...

    async def list_beneficial_owners(
        self,
        user_id: str,
        party_id: str,
    ) -> list[BeneficialOwner]: ...

    async def append_cdd(self, user_id: str, assessment: CddAssessment) -> CddAssessment: ...

    async def append_screening(
        self,
        user_id: str,
        result: ScreeningResult,
        match_detail: ScreeningMatchDetail | None,
    ) -> ScreeningResult: ...

    async def list_screenings(self, user_id: str, party_id: str) -> list[ScreeningResult]: ...

    async def get_screening_match_detail(
        self,
        user_id: str,
        screening_id: str,
    ) -> ScreeningMatchDetail | None: ...


class ScreeningPort(Protocol):
    """Provider-neutral screening; V0 may be manual entry via record_screening."""

    async def screen(
        self, party_snapshot: dict[str, Any], list_version: str
    ) -> ScreeningResult: ...


class FieldEncryptionPort(Protocol):
    """Field-level encryption for `identifierValue`, keyed separately from the DB."""

    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...

    def blind_index(self, plaintext: str) -> str: ...


class MatterAccessPort(Protocol):
    async def assert_matter_access(self, actor_id: str, matter_id: str) -> None: ...

    async def list_party_ids_for_matter(self, actor_id: str, matter_id: str) -> list[str]: ...


class EventPort(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
