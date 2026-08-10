"""Party module port definitions."""

from __future__ import annotations

from dataclasses import dataclass
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

__all__ = [
    "AuditPort",
    "PartyRepository",
    "IdentityEvidenceRepository",
    "ScreeningPort",
    "FieldEncryptionPort",
    "MatterAccessPort",
    "CreatePartyInput",
    "RecordIdentityEvidenceInput",
    "RecordCddInput",
    "RecordScreeningInput",
    "PartyListFilter",
]


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
    limit: int = 50
    offset: int = 0


class PartyRepository(Protocol):
    async def create(self, party: Party) -> Party: ...

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None: ...

    async def list_for_user(
        self,
        user_id: str,
        filter_: PartyListFilter,
    ) -> list[Party]: ...

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


class IdentityEvidenceRepository(Protocol):
    async def append_evidence(
        self,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence: ...

    async def get_evidence(self, party_id: str, evidence_id: str) -> IdentityEvidence | None: ...

    async def list_evidence_for_party(self, party_id: str) -> list[IdentityEvidence]: ...

    async def find_by_blind_index(
        self,
        user_id: str,
        blind_index: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[tuple[Party, IdentityEvidence]]: ...

    async def decrypt_identifier(self, evidence_id: str) -> str: ...

    async def add_beneficial_owner(self, owner: BeneficialOwner) -> BeneficialOwner: ...

    async def list_beneficial_owners(self, party_id: str) -> list[BeneficialOwner]: ...

    async def append_cdd(self, assessment: CddAssessment) -> CddAssessment: ...

    async def append_screening(
        self,
        result: ScreeningResult,
        match_detail: ScreeningMatchDetail | None,
    ) -> ScreeningResult: ...

    async def list_screenings(self, party_id: str) -> list[ScreeningResult]: ...

    async def get_screening_match_detail(
        self,
        screening_id: str,
    ) -> ScreeningMatchDetail | None: ...


class ScreeningPort(Protocol):
    """Provider-neutral screening; V0 may be manual entry via record_screening."""

    async def screen(
        self, party_snapshot: dict[str, Any], list_version: str
    ) -> ScreeningResult: ...


class FieldEncryptionPort(Protocol):
    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...

    def blind_index(self, plaintext: str) -> str: ...


class MatterAccessPort(Protocol):
    async def assert_matter_access(self, actor_id: str, matter_id: str) -> None: ...

    async def list_party_ids_for_matter(self, actor_id: str, matter_id: str) -> list[str]: ...
