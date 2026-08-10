"""party_service — protected identity tier application service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.party.domain.errors import (
    BeneficialOwnerCycleError,
    CrossUserPartyError,
    IdentityPurposeRequiredError,
    NotFoundError,
)
from src.modules.party.domain.models import (
    BeneficialOwner,
    BeneficialOwnerState,
    CddAssessment,
    CddLevel,
    CddOutcome,
    ConfidentialityLevel,
    DuplicateCandidate,
    EvidenceKind,
    EvidenceState,
    IdentityEvidence,
    OwnershipKind,
    Party,
    PartyKind,
    RiskRating,
    ScreeningOutcome,
    ScreeningResult,
    ScreeningStatus,
)
from src.modules.party.domain.policies import (
    effective_confidentiality,
    identifier_last4,
    normalise_name_for_probe,
    require_capability,
)
from src.modules.party.ports import (
    CreatePartyInput,
    FieldEncryptionPort,
    IdentityEvidenceRepository,
    MatterAccessPort,
    PartyListFilter,
    PartyRepository,
    RecordCddInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
    ScreeningPort,
)
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)


@dataclass
class PartyRead:
    party: Party
    duplicate_candidates: list[DuplicateCandidate]
    effective_confidentiality: ConfidentialityLevel


@dataclass
class IdentityEvidenceRead:
    evidence: IdentityEvidence


@dataclass
class IdentityValueRead:
    evidence_id: str
    identifier_value: str


@dataclass
class DuplicateProbeResult:
    candidates: list[DuplicateCandidate]


class PartyService:
    def __init__(
        self,
        *,
        party_repo: PartyRepository,
        identity_repo: IdentityEvidenceRepository,
        screening_port: ScreeningPort,
        field_encryption: FieldEncryptionPort,
        matter_access: MatterAccessPort,
        audit_port: AuditPort,
    ) -> None:
        self._parties = party_repo
        self._identity = identity_repo
        self._screening = screening_port
        self._encryption = field_encryption
        self._matter_access = matter_access
        self._audit = audit_port

    async def _load_party(self, ctx: RequestContext, party_id: str) -> Party:
        party = await self._parties.get_for_user(ctx.actor_id, party_id)
        if party is None:
            raise CrossUserPartyError()
        if party.merged_into_party_id:
            raise NotFoundError("The requested resource was not found.")
        return party

    async def create_party(self, ctx: RequestContext, input_: CreatePartyInput) -> PartyRead:
        require_capability(ctx.account_role, "party.record-identity")
        now = datetime.now(tz=UTC)
        party_id = f"pty_{uuid.uuid4().hex}"
        party = Party(
            id=party_id,
            user_id=ctx.actor_id,
            party_kind=PartyKind(input_.party_kind),
            display_name=input_.display_name,
            name_parts=input_.name_parts,
            former_names=input_.former_names,
            date_of_birth=input_.date_of_birth,
            registration_number=input_.registration_number,
            nationality=input_.nationality,
            residency_status=input_.residency_status,
            addresses=input_.addresses,
            contact_points=input_.contact_points,
            risk_rating=RiskRating.UNASSESSED,
            screening_status=ScreeningStatus.NOT_RUN,
            confidentiality_level=ConfidentialityLevel(input_.confidentiality_level),
            merged_into_party_id=None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        created = await self._parties.create(party)
        candidates = await self.detect_duplicates(ctx, created.id, probe_only=True)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.created",
                target_type="party",
                target_id=created.id,
                correlation_id=ctx.correlation_id,
            )
        )
        screenings = await self._identity.list_screenings(created.id)
        return PartyRead(
            party=created,
            duplicate_candidates=candidates.candidates,
            effective_confidentiality=effective_confidentiality(
                created.confidentiality_level, screenings
            ),
        )

    async def get_party(self, ctx: RequestContext, party_id: str) -> PartyRead:
        party = await self._load_party(ctx, party_id)
        screenings = await self._identity.list_screenings(party.id)
        return PartyRead(
            party=party,
            duplicate_candidates=[],
            effective_confidentiality=effective_confidentiality(
                party.confidentiality_level, screenings
            ),
        )

    async def list_parties(
        self,
        ctx: RequestContext,
        filter_: PartyListFilter | None = None,
    ) -> list[Party]:
        _ = ctx
        require_capability(ctx.account_role, "party.record-identity")
        filter_ = filter_ or PartyListFilter()
        return await self._parties.list_for_user(ctx.actor_id, filter_)

    async def update_party(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        display_name: str | None,
        expected_version: int,
    ) -> PartyRead:
        require_capability(ctx.account_role, "party.record-identity")
        party = await self._load_party(ctx, party_id)
        if display_name is not None:
            party.display_name = display_name
        updated = await self._parties.update(party, expected_version)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.updated",
                target_type="party",
                target_id=party_id,
                correlation_id=ctx.correlation_id,
            )
        )
        screenings = await self._identity.list_screenings(party_id)
        return PartyRead(
            party=updated,
            duplicate_candidates=[],
            effective_confidentiality=effective_confidentiality(
                updated.confidentiality_level, screenings
            ),
        )

    async def record_identity_evidence(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordIdentityEvidenceInput,
    ) -> IdentityEvidenceRead:
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_party(ctx, party_id)
        evidence_id = f"ide_{uuid.uuid4().hex}"
        last4 = identifier_last4(input_.identifier_value)
        encrypted = self._encryption.encrypt(input_.identifier_value)
        blind = self._encryption.blind_index(input_.identifier_value)
        evidence = IdentityEvidence(
            id=evidence_id,
            party_id=party_id,
            evidence_kind=EvidenceKind(input_.evidence_kind),
            identifier_value="",
            identifier_last4=last4,
            issued_on=input_.issued_on,
            expires_on=input_.expires_on,
            issuing_authority=input_.issuing_authority,
            document_id=input_.document_id,
            document_version_id=input_.document_version_id,
            evidence_span=input_.evidence_span,
            verified_by=None,
            verified_at=None,
            state=EvidenceState.RECORDED,
            supersedes_evidence_id=input_.supersedes_evidence_id,
            version=1,
        )
        stored = await self._identity.append_evidence(
            party_id,
            evidence,
            encrypted_identifier=encrypted,
            identifier_blind_index=blind,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.identity-evidence-recorded",
                target_type="party",
                target_id=party_id,
                after_ref=evidence_id,
                correlation_id=ctx.correlation_id,
            )
        )
        if input_.expires_on is not None:
            await self._audit.record(
                AuditEventInput(
                    user_id=ctx.actor_id,
                    actor=ctx.actor_id,
                    action="party.identity-document-expiry-recorded",
                    target_type="party",
                    target_id=party_id,
                    after_ref=evidence_id,
                    correlation_id=ctx.correlation_id,
                )
            )
        log.debug("identity_evidence_recorded", party_id=party_id, evidence_id=evidence_id)
        return IdentityEvidenceRead(evidence=stored)

    async def read_identity_value(
        self,
        ctx: RequestContext,
        party_id: str,
        evidence_id: str,
        *,
        purpose: str,
    ) -> IdentityValueRead:
        if not purpose.strip():
            raise IdentityPurposeRequiredError()
        require_capability(ctx.account_role, "party.read-identity")
        await self._load_party(ctx, party_id)
        evidence = await self._identity.get_evidence(party_id, evidence_id)
        if evidence is None:
            raise NotFoundError("The requested resource was not found.")
        value = await self._identity.decrypt_identifier(evidence_id)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.identity-value-read",
                target_type="party",
                target_id=party_id,
                reason=purpose,
                after_ref=evidence_id,
                correlation_id=ctx.correlation_id,
            )
        )
        return IdentityValueRead(evidence_id=evidence_id, identifier_value=value)

    async def record_beneficial_owner(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        owner_party_id: str,
        ownership_kind: str,
        percentage: float | None,
        evidence_refs: list[str],
    ) -> BeneficialOwner:
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_party(ctx, party_id)
        owner_party = await self._parties.get_for_user(ctx.actor_id, owner_party_id)
        if owner_party is None:
            raise CrossUserPartyError()
        if await self._would_create_cycle(party_id, owner_party_id):
            raise BeneficialOwnerCycleError()
        now = datetime.now(tz=UTC)
        owner = BeneficialOwner(
            id=f"bo_{uuid.uuid4().hex}",
            party_id=party_id,
            owner_party_id=owner_party_id,
            ownership_kind=OwnershipKind(ownership_kind),
            percentage=percentage,
            evidence_refs=evidence_refs,
            determined_by=ctx.actor_id,
            determined_at=now,
            state=BeneficialOwnerState.RECORDED,
        )
        saved = await self._identity.add_beneficial_owner(owner)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.beneficial-owner-recorded",
                target_type="party",
                target_id=party_id,
                after_ref=saved.id,
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    async def _would_create_cycle(self, entity_party_id: str, owner_party_id: str) -> bool:
        if entity_party_id == owner_party_id:
            return True
        visited: set[str] = {entity_party_id}
        frontier = [owner_party_id]
        while frontier:
            current = frontier.pop()
            if current in visited:
                return True
            visited.add(current)
            owners = await self._identity.list_beneficial_owners(current)
            frontier.extend(o.owner_party_id for o in owners)
        return False

    async def record_cdd(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordCddInput,
    ) -> CddAssessment:
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_party(ctx, party_id)
        now = datetime.now(tz=UTC)
        assessment = CddAssessment(
            id=f"cdd_{uuid.uuid4().hex}",
            party_id=party_id,
            matter_id=input_.matter_id,
            level=CddLevel(input_.level),
            risk_factors=input_.risk_factors,
            outcome=CddOutcome(input_.outcome),
            assessed_by=ctx.actor_id,
            assessed_at=now,
            review_due_on=input_.review_due_on,
            policy_version=input_.policy_version,
            version=1,
        )
        saved = await self._identity.append_cdd(assessment)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.cdd-recorded",
                target_type="party",
                target_id=party_id,
                after_ref=saved.id,
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    async def record_screening(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordScreeningInput,
    ) -> ScreeningResult:
        require_capability(ctx.account_role, "compliance.act")
        party = await self._load_party(ctx, party_id)
        now = datetime.now(tz=UTC)
        outcome = ScreeningOutcome(input_.outcome)
        result = ScreeningResult(
            id=f"scr_{uuid.uuid4().hex}",
            party_id=party_id,
            list_version=input_.list_version,
            provider_ref=input_.provider_ref,
            outcome=outcome,
            match_count=input_.match_count,
            reviewed_by=ctx.actor_id,
            reviewed_at=now,
            disposition_reason=None,
            confidentiality_level=ConfidentialityLevel.RESTRICTED_COMPLIANCE,
            created_at=now,
        )
        saved = await self._identity.append_screening(result, input_.match_detail)
        party.screening_status = ScreeningStatus(outcome.value)
        if outcome in (ScreeningOutcome.POTENTIAL_MATCH, ScreeningOutcome.CONFIRMED_MATCH):
            party.confidentiality_level = ConfidentialityLevel.RESTRICTED_COMPLIANCE
        await self._parties.update(party, party.version)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="party.screening-completed",
                target_type="party",
                target_id=party_id,
                after_ref=saved.id,
                correlation_id=ctx.correlation_id,
            )
        )
        if outcome == ScreeningOutcome.CONFIRMED_MATCH:
            await self._audit.record(
                AuditEventInput(
                    user_id=ctx.actor_id,
                    actor=ctx.actor_id,
                    action="party.designated-person-confirmed",
                    target_type="party",
                    target_id=party_id,
                    after_ref=saved.id,
                    correlation_id=ctx.correlation_id,
                )
            )
            log.info(
                "designated_person_confirmed",
                party_id=party_id,
                user_id=ctx.actor_id,
                confidentiality="restricted-compliance",
            )
        return saved

    async def detect_duplicates(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        identifier_value: str | None = None,
        probe_only: bool = False,
    ) -> DuplicateProbeResult:
        require_capability(ctx.account_role, "party.record-identity")
        party = await self._load_party(ctx, party_id)
        candidates: dict[str, DuplicateCandidate] = {}

        if identifier_value:
            blind = self._encryption.blind_index(identifier_value)
            for match_party, _evidence in await self._identity.find_by_blind_index(
                ctx.actor_id,
                blind,
                exclude_party_id=party_id if probe_only else None,
            ):
                if match_party.id == party_id:
                    continue
                candidates[match_party.id] = DuplicateCandidate(
                    party_id=match_party.id,
                    display_name=match_party.display_name,
                    match_reason="exact-identifier",
                    strength="strong",
                )

        if party.registration_number:
            for match in await self._parties.find_by_registration_number(
                ctx.actor_id,
                party.registration_number,
                exclude_party_id=party_id,
            ):
                candidates[match.id] = DuplicateCandidate(
                    party_id=match.id,
                    display_name=match.display_name,
                    match_reason="registration-number",
                    strength="strong",
                )

        norm_name = normalise_name_for_probe(party.display_name)
        if party.date_of_birth:
            for match in await self._parties.find_by_normalised_name_and_dob(
                ctx.actor_id,
                norm_name,
                party.date_of_birth,
                exclude_party_id=party_id,
            ):
                candidates[match.id] = DuplicateCandidate(
                    party_id=match.id,
                    display_name=match.display_name,
                    match_reason="name-and-dob",
                    strength="moderate",
                )

        if party.addresses:
            fingerprint = str(party.addresses[0]).lower()
            for match in await self._parties.find_by_normalised_name_and_address(
                ctx.actor_id,
                norm_name,
                fingerprint,
                exclude_party_id=party_id,
            ):
                candidates[match.id] = DuplicateCandidate(
                    party_id=match.id,
                    display_name=match.display_name,
                    match_reason="name-and-address",
                    strength="moderate",
                )

        return DuplicateProbeResult(candidates=list(candidates.values()))

    async def list_matter_parties(self, ctx: RequestContext, matter_id: str) -> list[Party]:
        await self._matter_access.assert_matter_access(ctx.actor_id, matter_id)
        party_ids = await self._matter_access.list_party_ids_for_matter(ctx.actor_id, matter_id)
        parties: list[Party] = []
        for party_id in party_ids:
            party = await self._parties.get_for_user(ctx.actor_id, party_id)
            if party is not None:
                parties.append(party)
        return parties

    async def list_identity_evidence(
        self,
        ctx: RequestContext,
        party_id: str,
    ) -> list[IdentityEvidence]:
        await self._load_party(ctx, party_id)
        return await self._identity.list_evidence_for_party(party_id)

    async def list_screening_results(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        include_restricted_detail: bool = False,
    ) -> list[dict[str, Any]]:
        await self._load_party(ctx, party_id)
        results = await self._identity.list_screenings(party_id)
        payload: list[dict[str, Any]] = []
        for result in results:
            item: dict[str, Any] = {
                "id": result.id,
                "outcome": result.outcome.value,
                "match_count": result.match_count,
                "list_version": result.list_version,
                "created_at": result.created_at.isoformat(),
            }
            if include_restricted_detail:
                require_capability(ctx.account_role, "compliance.view")
                detail = await self._identity.get_screening_match_detail(result.id)
                if detail:
                    item["match_detail"] = {
                        "list_entry_ref": detail.list_entry_ref,
                        "match_narrative": detail.match_narrative,
                    }
            payload.append(item)
        return payload
