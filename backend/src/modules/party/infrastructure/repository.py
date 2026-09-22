"""SQLAlchemy repositories for the party module.

Every statement filters on `user_id` first. A child row is never reached
through its parent alone: each party-owned table carries the tenant key so a
missing join condition cannot silently widen the scope (party-service.md §9).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.party.domain.models import (
    BeneficialOwner,
    BeneficialOwnerState,
    CddAssessment,
    CddLevel,
    CddOutcome,
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
from src.modules.party.infrastructure.field_encryption import LocalFieldEncryptionAdapter
from src.modules.party.infrastructure.orm import (
    BeneficialOwnerRow,
    CddAssessmentRow,
    IdentityEvidenceRow,
    PartyRow,
    ScreeningMatchDetailRow,
    ScreeningResultRow,
)
from src.modules.party.ports import PartyListFilter, PartyPage
from src.platform.errors import NotFoundError, PreconditionFailedError

# Guard against an unbounded in-memory scan in the duplicate probe (§7).
_PROBE_SCAN_LIMIT = 500


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


def _row_to_evidence(row: IdentityEvidenceRow) -> IdentityEvidence:
    """Never carries the plaintext identifier — that is a separate audited read."""
    return IdentityEvidence(
        id=row.id,
        party_id=row.party_id,
        evidence_kind=EvidenceKind(row.evidence_kind),
        identifier_value="",
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


def _row_to_owner(row: BeneficialOwnerRow) -> BeneficialOwner:
    return BeneficialOwner(
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


def _row_to_screening(row: ScreeningResultRow) -> ScreeningResult:
    return ScreeningResult(
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
            created_at=party.created_at,
            updated_at=party.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return party

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None:
        stmt = select(PartyRow).where(PartyRow.user_id == user_id, PartyRow.id == party_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_party(row) if row else None

    async def list_for_user(self, user_id: str, filter_: PartyListFilter) -> PartyPage:
        stmt = select(PartyRow).where(PartyRow.user_id == user_id)
        if filter_.query:
            stmt = stmt.where(PartyRow.display_name.ilike(f"%{filter_.query}%"))
        if filter_.cursor is not None:
            # createdAt descending with id as the tie-breaker (api-conventions.md §2)
            stmt = stmt.where(
                or_(
                    PartyRow.created_at < filter_.cursor.created_at,
                    (PartyRow.created_at == filter_.cursor.created_at)
                    & (PartyRow.id < filter_.cursor.id),
                )
            )
        stmt = stmt.order_by(PartyRow.created_at.desc(), PartyRow.id.desc()).limit(
            filter_.limit + 1
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > filter_.limit
        return PartyPage(items=[_row_to_party(r) for r in rows[: filter_.limit]], has_more=has_more)

    async def update(self, party: Party, expected_version: int) -> Party:
        stmt = select(PartyRow).where(
            PartyRow.user_id == party.user_id,
            PartyRow.id == party.id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("The requested resource was not found.")
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
        result = await self._session.execute(stmt.limit(_PROBE_SCAN_LIMIT))
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
        result = await self._session.execute(stmt.limit(_PROBE_SCAN_LIMIT))
        return [
            _row_to_party(row)
            for row in result.scalars().all()
            if normalised_name in row.display_name.lower()
        ]

    async def find_by_normalised_name_and_address(
        self,
        user_id: str,
        normalised_name: str,
        address_fingerprint: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        stmt = select(PartyRow).where(
            PartyRow.user_id == user_id,
            PartyRow.display_name.ilike(f"%{normalised_name}%"),
        )
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt.limit(_PROBE_SCAN_LIMIT))
        matches: list[Party] = []
        for row in result.scalars().all():
            if any(address_fingerprint in str(addr).lower() for addr in row.addresses or []):
                matches.append(_row_to_party(row))
        return matches

    async def repoint_dependents(
        self,
        user_id: str,
        source_party_id: str,
        target_party_id: str,
    ) -> int:
        """Repoint every dependent row from source to target. Nothing is deleted."""
        moved = 0
        for table in (IdentityEvidenceRow, BeneficialOwnerRow, CddAssessmentRow):
            stmt = (
                update(table)
                .where(table.user_id == user_id, table.party_id == source_party_id)
                .values(party_id=target_party_id)
            )
            moved += (await self._session.execute(stmt)).rowcount  # type: ignore[attr-defined]
        owner_stmt = (
            update(BeneficialOwnerRow)
            .where(
                BeneficialOwnerRow.user_id == user_id,
                BeneficialOwnerRow.owner_party_id == source_party_id,
            )
            .values(owner_party_id=target_party_id)
        )
        moved += (await self._session.execute(owner_stmt)).rowcount  # type: ignore[attr-defined]
        # Screening results stay with the record that was actually screened.
        await self._session.flush()
        return int(moved)


class SqlIdentityEvidenceRepository:
    def __init__(
        self,
        session: AsyncSession,
        encryption: LocalFieldEncryptionAdapter,
    ) -> None:
        self._session = session
        self._encryption = encryption

    async def append_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence:
        row = IdentityEvidenceRow(
            id=evidence.id,
            party_id=party_id,
            user_id=user_id,
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
        return _row_to_evidence(row)

    async def _evidence_row(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> IdentityEvidenceRow | None:
        stmt = select(IdentityEvidenceRow).where(
            IdentityEvidenceRow.user_id == user_id,
            IdentityEvidenceRow.party_id == party_id,
            IdentityEvidenceRow.id == evidence_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> IdentityEvidence | None:
        row = await self._evidence_row(user_id, party_id, evidence_id)
        return _row_to_evidence(row) if row else None

    async def list_evidence_for_party(
        self,
        user_id: str,
        party_id: str,
    ) -> list[IdentityEvidence]:
        stmt = select(IdentityEvidenceRow).where(
            IdentityEvidenceRow.user_id == user_id,
            IdentityEvidenceRow.party_id == party_id,
        )
        result = await self._session.execute(stmt)
        return [_row_to_evidence(row) for row in result.scalars().all()]

    async def mark_evidence_state(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
        *,
        state: str,
        expected_version: int,
        verified_by: str | None = None,
        verified_at: datetime | None = None,
    ) -> IdentityEvidence:
        row = await self._evidence_row(user_id, party_id, evidence_id)
        if row is None:
            raise NotFoundError("The requested resource was not found.")
        if row.version != expected_version:
            raise PreconditionFailedError("Identity evidence version conflict.")
        row.state = state
        if verified_by is not None:
            row.verified_by = verified_by
        if verified_at is not None:
            row.verified_at = verified_at
        row.version = expected_version + 1
        await self._session.flush()
        return _row_to_evidence(row)

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
                IdentityEvidenceRow.user_id == user_id,
                PartyRow.user_id == user_id,
                IdentityEvidenceRow.identifier_blind_index == blind_index,
            )
        )
        if exclude_party_id:
            stmt = stmt.where(PartyRow.id != exclude_party_id)
        result = await self._session.execute(stmt.limit(_PROBE_SCAN_LIMIT))
        return [
            (_row_to_party(party_row), _row_to_evidence(evidence_row))
            for evidence_row, party_row in result.all()
        ]

    async def decrypt_identifier(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> str:
        row = await self._evidence_row(user_id, party_id, evidence_id)
        if row is None:
            raise NotFoundError("The requested resource was not found.")
        return self._encryption.decrypt(row.identifier_ciphertext)

    async def add_beneficial_owner(self, user_id: str, owner: BeneficialOwner) -> BeneficialOwner:
        row = BeneficialOwnerRow(
            id=owner.id,
            party_id=owner.party_id,
            user_id=user_id,
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

    async def list_beneficial_owners(
        self,
        user_id: str,
        party_id: str,
    ) -> list[BeneficialOwner]:
        stmt = select(BeneficialOwnerRow).where(
            BeneficialOwnerRow.user_id == user_id,
            BeneficialOwnerRow.party_id == party_id,
        )
        result = await self._session.execute(stmt)
        return [_row_to_owner(row) for row in result.scalars().all()]

    async def append_cdd(self, user_id: str, assessment: CddAssessment) -> CddAssessment:
        row = CddAssessmentRow(
            id=assessment.id,
            party_id=assessment.party_id,
            user_id=user_id,
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

    async def list_cdd_assessments(self, user_id: str, party_id: str) -> list[CddAssessment]:
        stmt = select(CddAssessmentRow).where(
            CddAssessmentRow.user_id == user_id,
            CddAssessmentRow.party_id == party_id,
        )
        result = await self._session.execute(stmt)
        return [
            CddAssessment(
                id=row.id,
                party_id=row.party_id,
                matter_id=row.matter_id,
                level=CddLevel(row.level),
                risk_factors=list(row.risk_factors or []),
                outcome=CddOutcome(row.outcome),
                assessed_by=row.assessed_by,
                assessed_at=row.assessed_at,
                review_due_on=row.review_due_on,
                policy_version=row.policy_version,
                version=row.version,
            )
            for row in result.scalars().all()
        ]

    async def append_screening(
        self,
        user_id: str,
        result: ScreeningResult,
        match_detail: ScreeningMatchDetail | None,
    ) -> ScreeningResult:
        row = ScreeningResultRow(
            id=result.id,
            party_id=result.party_id,
            user_id=user_id,
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
            # The detail's foreign key points at this result, and there is no ORM
            # relationship to order the inserts, so the result must reach Postgres first.
            await self._session.flush()
            self._session.add(
                ScreeningMatchDetailRow(
                    screening_result_id=result.id,
                    user_id=user_id,
                    provider_payload=match_detail.provider_payload,
                    match_narrative=match_detail.match_narrative,
                    list_entry_ref=match_detail.list_entry_ref,
                )
            )
        await self._session.flush()
        return result

    async def list_screenings(self, user_id: str, party_id: str) -> list[ScreeningResult]:
        stmt = select(ScreeningResultRow).where(
            ScreeningResultRow.user_id == user_id,
            ScreeningResultRow.party_id == party_id,
        )
        result = await self._session.execute(stmt)
        return [_row_to_screening(row) for row in result.scalars().all()]

    async def get_screening_match_detail(
        self,
        user_id: str,
        screening_id: str,
    ) -> ScreeningMatchDetail | None:
        stmt = select(ScreeningMatchDetailRow).where(
            ScreeningMatchDetailRow.user_id == user_id,
            ScreeningMatchDetailRow.screening_result_id == screening_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ScreeningMatchDetail(
            screening_result_id=row.screening_result_id,
            provider_payload=dict(row.provider_payload or {}),
            match_narrative=row.match_narrative,
            list_entry_ref=row.list_entry_ref,
        )
