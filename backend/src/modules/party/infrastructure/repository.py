"""SQLAlchemy repositories for the party module."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.party.domain.models import (
    BeneficialOwner,
    BeneficialOwnerState,
    CddAssessment,
    ConfidentialityLevel,
    EvidenceKind,
    EvidenceState,
    IdentityEvidence,
    OwnershipKind,
    Party,
    PartyKind,
    RiskRating,
    ScreeningMatchDetail,
    ScreeningOutcome,
    ScreeningResult,
    ScreeningStatus,
)
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.orm import (
    BeneficialOwnerRow,
    CddAssessmentRow,
    IdentityEvidenceRow,
    PartyRow,
    ScreeningMatchDetailRow,
    ScreeningResultRow,
)
from src.modules.party.ports import PartyListFilter
from src.platform.errors import PreconditionFailedError


def _row_to_party(row: PartyRow) -> Party:
    return Party(
        id=row.id,
        user_id=row.user_id,
        party_kind=PartyKind(row.party_kind),
        display_name=row.display_name,
        name_parts=dict(row.name_parts or {}),
        former_names=list(row.former_names or []),
        date_of_birth=row.date_of_birth,
        registration_number=row.registration_number,
        nationality=row.nationality,
        residency_status=row.residency_status,
        addresses=list(row.addresses or []),
        contact_points=list(row.contact_points or []),
        risk_rating=RiskRating(row.risk_rating),
        screening_status=ScreeningStatus(row.screening_status),
        confidentiality_level=ConfidentialityLevel(row.confidentiality_level),
        merged_into_party_id=row.merged_into_party_id,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_evidence(row: IdentityEvidenceRow, *, identifier_value: str = "") -> IdentityEvidence:
    return IdentityEvidence(
        id=row.id,
        party_id=row.party_id,
        evidence_kind=EvidenceKind(row.evidence_kind),
        identifier_value=identifier_value,
        identifier_last4=row.identifier_last4,
        issued_on=row.issued_on,
        expires_on=row.expires_on,
        issuing_authority=row.issuing_authority,
        document_id=row.document_id,
        document_version_id=row.document_version_id,
        evidence_span=dict(row.evidence_span) if row.evidence_span else None,
        verified_by=row.verified_by,
        verified_at=row.verified_at,
        state=EvidenceState(row.state),
        supersedes_evidence_id=row.supersedes_evidence_id,
        version=row.version,
    )


class SqlPartyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, party: Party) -> Party:
        row = PartyRow(
            id=party.id,
            user_id=party.user_id,
            party_kind=party.party_kind.value,
            display_name=party.display_name,
            name_parts=party.name_parts,
            former_names=party.former_names,
            date_of_birth=party.date_of_birth,
            registration_number=party.registration_number,
            nationality=party.nationality,
            residency_status=party.residency_status,
            addresses=party.addresses,
            contact_points=party.contact_points,
            risk_rating=party.risk_rating.value,
            screening_status=party.screening_status.value,
            confidentiality_level=party.confidentiality_level.value,
            merged_into_party_id=party.merged_into_party_id,
            version=party.version,
        )
        self._session.add(row)
        await self._session.flush()
        return party

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None:
        stmt = select(PartyRow).where(PartyRow.id == party_id, PartyRow.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_party(row) if row else None

    async def list_for_user(self, user_id: str, filter_: PartyListFilter) -> list[Party]:
        stmt = select(PartyRow).where(PartyRow.user_id == user_id)
        if filter_.query:
            stmt = stmt.where(PartyRow.display_name.ilike(f"%{filter_.query}%"))
        stmt = stmt.order_by(PartyRow.display_name).limit(filter_.limit).offset(filter_.offset)
        result = await self._session.execute(stmt)
        return [_row_to_party(row) for row in result.scalars().all()]

    async def update(self, party: Party, expected_version: int) -> Party:
        row = await self._session.get(PartyRow, party.id)
        if row is None or row.user_id != party.user_id:
            raise PreconditionFailedError("Party version conflict.")
        if row.version != expected_version:
            raise PreconditionFailedError("Party version conflict.")
        row.display_name = party.display_name
        row.name_parts = party.name_parts
        row.former_names = party.former_names
        row.date_of_birth = party.date_of_birth
        row.registration_number = party.registration_number
        row.nationality = party.nationality
        row.residency_status = party.residency_status
        row.addresses = party.addresses
        row.contact_points = party.contact_points
        row.risk_rating = party.risk_rating.value
        row.screening_status = party.screening_status.value
        row.confidentiality_level = party.confidentiality_level.value
        row.merged_into_party_id = party.merged_into_party_id
        row.version = expected_version + 1
        party.version = row.version
        await self._session.flush()
        return party

    async def find_by_registration_number(
        self,
        user_id: str,
        registration_number: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        stmt = select(PartyRow).where(
            PartyRow.user_id == user_id,
            PartyRow.registration_number == registration_number,
        )
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt)
        return [_row_to_party(row) for row in result.scalars().all()]

    async def find_by_normalised_name_and_dob(
        self,
        user_id: str,
        normalised_name: str,
        date_of_birth: date,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        stmt = select(PartyRow).where(
            PartyRow.user_id == user_id,
            PartyRow.date_of_birth == date_of_birth,
        )
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt)
        matches: list[Party] = []
        for row in result.scalars().all():
            if normalised_name in row.display_name.lower():
                matches.append(_row_to_party(row))
        return matches

    async def find_by_normalised_name_and_address(
        self,
        user_id: str,
        normalised_name: str,
        address_fingerprint: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        stmt = select(PartyRow).where(PartyRow.user_id == user_id)
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt)
        matches: list[Party] = []
        for row in result.scalars().all():
            if normalised_name not in row.display_name.lower():
                continue
            for addr in row.addresses or []:
                if address_fingerprint in str(addr).lower():
                    matches.append(_row_to_party(row))
                    break
        return matches


class SqlIdentityEvidenceRepository:
    def __init__(
        self,
        session: AsyncSession,
        encryption: StubFieldEncryptionAdapter | None = None,
    ) -> None:
        self._session = session
        self._encryption = encryption or StubFieldEncryptionAdapter()

    async def append_evidence(
        self,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence:
        row = IdentityEvidenceRow(
            id=evidence.id,
            party_id=party_id,
            evidence_kind=evidence.evidence_kind.value,
            identifier_ciphertext=encrypted_identifier,
            identifier_blind_index=identifier_blind_index,
            identifier_last4=evidence.identifier_last4,
            issued_on=evidence.issued_on,
            expires_on=evidence.expires_on,
            issuing_authority=evidence.issuing_authority,
            document_id=evidence.document_id,
            document_version_id=evidence.document_version_id,
            evidence_span=evidence.evidence_span,
            verified_by=evidence.verified_by,
            verified_at=evidence.verified_at,
            state=evidence.state.value,
            supersedes_evidence_id=evidence.supersedes_evidence_id,
            version=evidence.version,
        )
        self._session.add(row)
        await self._session.flush()
        stored = _row_to_evidence(row)
        stored.identifier_value = ""
        return stored

    async def get_evidence(self, party_id: str, evidence_id: str) -> IdentityEvidence | None:
        stmt = select(IdentityEvidenceRow).where(
            IdentityEvidenceRow.id == evidence_id,
            IdentityEvidenceRow.party_id == party_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_evidence(row) if row else None

    async def list_evidence_for_party(self, party_id: str) -> list[IdentityEvidence]:
        stmt = select(IdentityEvidenceRow).where(IdentityEvidenceRow.party_id == party_id)
        result = await self._session.execute(stmt)
        return [_row_to_evidence(row) for row in result.scalars().all()]

    async def find_by_blind_index(
        self,
        user_id: str,
        blind_index: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[tuple[Party, IdentityEvidence]]:
        stmt = (
            select(IdentityEvidenceRow, PartyRow)
            .join(PartyRow, PartyRow.id == IdentityEvidenceRow.party_id)
            .where(
                PartyRow.user_id == user_id,
                IdentityEvidenceRow.identifier_blind_index == blind_index,
            )
        )
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt)
        pairs: list[tuple[Party, IdentityEvidence]] = []
        for evidence_row, party_row in result.all():
            pairs.append((_row_to_party(party_row), _row_to_evidence(evidence_row)))
        return pairs

    async def decrypt_identifier(self, evidence_id: str) -> str:
        row = await self._session.get(IdentityEvidenceRow, evidence_id)
        if row is None:
            raise ValueError("Evidence not found")
        return self._encryption.decrypt(row.identifier_ciphertext)

    async def add_beneficial_owner(self, owner: BeneficialOwner) -> BeneficialOwner:
        row = BeneficialOwnerRow(
            id=owner.id,
            party_id=owner.party_id,
            owner_party_id=owner.owner_party_id,
            ownership_kind=owner.ownership_kind.value,
            percentage=owner.percentage,
            evidence_refs=owner.evidence_refs,
            determined_by=owner.determined_by,
            determined_at=owner.determined_at,
            state=owner.state.value,
        )
        self._session.add(row)
        await self._session.flush()
        return owner

    async def list_beneficial_owners(self, party_id: str) -> list[BeneficialOwner]:
        stmt = select(BeneficialOwnerRow).where(BeneficialOwnerRow.party_id == party_id)
        result = await self._session.execute(stmt)
        owners: list[BeneficialOwner] = []
        for row in result.scalars().all():
            owners.append(
                BeneficialOwner(
                    id=row.id,
                    party_id=row.party_id,
                    owner_party_id=row.owner_party_id,
                    ownership_kind=OwnershipKind(row.ownership_kind),
                    percentage=row.percentage,
                    evidence_refs=list(row.evidence_refs or []),
                    determined_by=row.determined_by,
                    determined_at=row.determined_at,
                    state=BeneficialOwnerState(row.state),
                )
            )
        return owners

    async def append_cdd(self, assessment: CddAssessment) -> CddAssessment:
        row = CddAssessmentRow(
            id=assessment.id,
            party_id=assessment.party_id,
            matter_id=assessment.matter_id,
            level=assessment.level.value,
            risk_factors=assessment.risk_factors,
            outcome=assessment.outcome.value,
            assessed_by=assessment.assessed_by,
            assessed_at=assessment.assessed_at,
            review_due_on=assessment.review_due_on,
            policy_version=assessment.policy_version,
            version=assessment.version,
        )
        self._session.add(row)
        await self._session.flush()
        return assessment

    async def append_screening(
        self,
        result: ScreeningResult,
        match_detail: ScreeningMatchDetail | None,
    ) -> ScreeningResult:
        row = ScreeningResultRow(
            id=result.id,
            party_id=result.party_id,
            list_version=result.list_version,
            provider_ref=result.provider_ref,
            outcome=result.outcome.value,
            match_count=result.match_count,
            reviewed_by=result.reviewed_by,
            reviewed_at=result.reviewed_at,
            disposition_reason=result.disposition_reason,
            confidentiality_level=result.confidentiality_level.value,
            created_at=result.created_at,
        )
        self._session.add(row)
        if match_detail is not None:
            detail_row = ScreeningMatchDetailRow(
                screening_result_id=result.id,
                provider_payload=match_detail.provider_payload,
                match_narrative=match_detail.match_narrative,
                list_entry_ref=match_detail.list_entry_ref,
            )
            self._session.add(detail_row)
        await self._session.flush()
        return result

    async def list_screenings(self, party_id: str) -> list[ScreeningResult]:
        stmt = select(ScreeningResultRow).where(ScreeningResultRow.party_id == party_id)
        result = await self._session.execute(stmt)
        screenings: list[ScreeningResult] = []
        for row in result.scalars().all():
            screenings.append(
                ScreeningResult(
                    id=row.id,
                    party_id=row.party_id,
                    list_version=row.list_version,
                    provider_ref=row.provider_ref,
                    outcome=ScreeningOutcome(row.outcome),
                    match_count=row.match_count,
                    reviewed_by=row.reviewed_by,
                    reviewed_at=row.reviewed_at,
                    disposition_reason=row.disposition_reason,
                    confidentiality_level=ConfidentialityLevel(row.confidentiality_level),
                    created_at=row.created_at,
                )
            )
        return screenings

    async def get_screening_match_detail(
        self,
        screening_id: str,
    ) -> ScreeningMatchDetail | None:
        row = await self._session.get(ScreeningMatchDetailRow, screening_id)
        if row is None:
            return None
        return ScreeningMatchDetail(
            screening_result_id=row.screening_result_id,
            provider_payload=dict(row.provider_payload or {}),
            match_narrative=row.match_narrative,
            list_entry_ref=row.list_entry_ref,
        )
