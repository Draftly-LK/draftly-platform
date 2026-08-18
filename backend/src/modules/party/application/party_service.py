"""party_service — protected identity tier application service.

Trust boundary notes (backend-implementation-plan-v0.md §5.2):

- `user_id` is always `ctx.actor_id`. No method accepts a user id, a role, or a
  capability from a caller-supplied body; a forged one is simply never read.
- Every repository call is user-scoped, and a cross-user hit is reported as 404.
- Restricted-compliance records are invisible — not forbidden — to a caller
  without `compliance.view`, so absence and denial are indistinguishable.
- Exactly one audit event per mutating method, recorded in the same unit of work
  as the mutation. Cross-service notification happens through `EventPort`, whose
  payloads carry identifiers and closed enums only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog

from src.modules.auth.domain.models import Role
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.party.domain.errors import (
    BeneficialOwnerCycleError,
    BeneficialOwnerDepthExceededError,
    CrossUserPartyError,
    EvidenceNotPinnedError,
    EvidenceStateTransitionError,
    IdentityPurposeRequiredError,
    MergedPartyImmutableError,
    MergeTargetInvalidError,
    NotFoundError,
    RestrictedComplianceError,
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
    MAX_BENEFICIAL_OWNERSHIP_DEPTH,
    MAX_BENEFICIAL_OWNERSHIP_NODES,
    effective_confidentiality,
    holds_compliance_view,
    identifier_last4,
    is_evidence_transition_allowed,
    normalise_name_for_probe,
    require_capability,
    require_party_access,
)
from src.modules.party.ports import (
    CreatePartyInput,
    DomainEvent,
    EventPort,
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
from src.platform.errors import CapabilityDeniedError
from src.platform.pagination import Cursor, Page, encode_cursor, normalise_limit
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

MAX_MATTER_PARTIES = 200


class PractisingNotaryPort(Protocol):
    """Practising status is an attribute, not a role (security-model.md §3.3)."""

    async def assert_practising(self, ctx: RequestContext) -> None: ...


@dataclass
class PartyRead:
    party: Party
    duplicate_candidates: list[DuplicateCandidate]
    effective_confidentiality: ConfidentialityLevel
    # None when the caller may not know whether a screening record exists.
    screening_status: ScreeningStatus | None


@dataclass
class PartyListPage:
    items: list[Party]
    page: Page


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
        event_port: EventPort,
        notary_port: PractisingNotaryPort,
    ) -> None:
        self._parties = party_repo
        self._identity = identity_repo
        self._screening = screening_port
        self._encryption = field_encryption
        self._matter_access = matter_access
        self._audit = audit_port
        self._events = event_port
        self._notary = notary_port

    # ── internals ────────────────────────────────────────────────────────────

    async def _load_party(self, ctx: RequestContext, party_id: str) -> Party:
        """Load a party the actor owns, or raise 404. Merged parties still load."""
        require_party_access(ctx.account_role)
        party = await self._parties.get_for_user(ctx.actor_id, party_id)
        if party is None:
            raise CrossUserPartyError()
        return party

    async def _load_writable_party(self, ctx: RequestContext, party_id: str) -> Party:
        party = await self._load_party(ctx, party_id)
        if party.merged_into_party_id:
            raise MergedPartyImmutableError()
        return party

    async def _visible_screenings(
        self,
        ctx: RequestContext,
        party_id: str,
    ) -> list[ScreeningResult]:
        """Screening rows exist only for a caller holding `compliance.view` (§3.5)."""
        if not holds_compliance_view(ctx.account_role):
            return []
        return await self._identity.list_screenings(ctx.actor_id, party_id)

    async def _to_read(
        self,
        ctx: RequestContext,
        party: Party,
        *,
        candidates: list[DuplicateCandidate] | None = None,
    ) -> PartyRead:
        screenings = await self._visible_screenings(ctx, party.id)
        may_see_compliance = holds_compliance_view(ctx.account_role)
        return PartyRead(
            party=party,
            duplicate_candidates=candidates or [],
            effective_confidentiality=effective_confidentiality(
                party.confidentiality_level, screenings
            ),
            screening_status=party.screening_status if may_see_compliance else None,
        )

    async def _audit_once(
        self,
        ctx: RequestContext,
        *,
        action: str,
        target_id: str,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        """The single audit event for a mutating method, in its unit of work.

        `reason` is the only free-text field and is caller-supplied purpose or
        merge justification. No identifier value or party name is ever passed.
        """
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action=action,
                target_type="party",
                target_id=target_id,
                after_ref=after_ref,
                reason=reason,
                correlation_id=ctx.correlation_id,
            )
        )

    async def _publish(
        self,
        ctx: RequestContext,
        name: str,
        party_id: str,
        payload: dict[str, Any],
    ) -> None:
        await self._events.publish(
            DomainEvent(
                name=name,
                user_id=ctx.actor_id,
                aggregate_type="party",
                aggregate_id=party_id,
                payload=payload,
                correlation_id=ctx.correlation_id,
            )
        )

    # ── create / read / update ───────────────────────────────────────────────

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
        probe = await self._probe_duplicates(ctx, created)
        await self._audit_once(ctx, action="party.created", target_id=created.id)
        await self._publish(
            ctx,
            "party.created",
            created.id,
            {"partyId": created.id, "partyKind": created.party_kind.value},
        )
        return await self._to_read(ctx, created, candidates=probe.candidates)

    async def get_party(self, ctx: RequestContext, party_id: str) -> PartyRead:
        party = await self._load_party(ctx, party_id)
        return await self._to_read(ctx, party)

    async def list_parties(
        self,
        ctx: RequestContext,
        filter_: PartyListFilter | None = None,
    ) -> PartyListPage:
        require_party_access(ctx.account_role)
        filter_ = filter_ or PartyListFilter()
        filter_.limit = normalise_limit(filter_.limit)
        result = await self._parties.list_for_user(ctx.actor_id, filter_)
        next_cursor = None
        if result.has_more and result.items:
            last = result.items[-1]
            next_cursor = encode_cursor(Cursor(created_at=last.created_at, id=last.id))
        return PartyListPage(
            items=result.items,
            page=Page(next_cursor=next_cursor, has_more=result.has_more, limit=filter_.limit),
        )

    async def update_party(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        display_name: str | None,
        expected_version: int,
    ) -> PartyRead:
        require_capability(ctx.account_role, "party.record-identity")
        party = await self._load_writable_party(ctx, party_id)
        if display_name is not None:
            party.display_name = display_name
        updated = await self._parties.update(party, expected_version)
        await self._audit_once(ctx, action="party.updated", target_id=party_id)
        return await self._to_read(ctx, updated)

    # ── identity evidence ────────────────────────────────────────────────────

    async def record_identity_evidence(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordIdentityEvidenceInput,
    ) -> IdentityEvidenceRead:
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_writable_party(ctx, party_id)

        predecessor: IdentityEvidence | None = None
        if input_.supersedes_evidence_id:
            predecessor = await self._identity.get_evidence(
                ctx.actor_id, party_id, input_.supersedes_evidence_id
            )
            if predecessor is None:
                raise NotFoundError("The requested resource was not found.")
            if not is_evidence_transition_allowed(predecessor.state, EvidenceState.SUPERSEDED):
                raise EvidenceStateTransitionError()

        evidence_id = f"ide_{uuid.uuid4().hex}"
        encrypted = self._encryption.encrypt(input_.identifier_value)
        blind = self._encryption.blind_index(input_.identifier_value)
        evidence = IdentityEvidence(
            id=evidence_id,
            party_id=party_id,
            evidence_kind=EvidenceKind(input_.evidence_kind),
            identifier_value="",
            identifier_last4=identifier_last4(input_.identifier_value),
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
            ctx.actor_id,
            party_id,
            evidence,
            encrypted_identifier=encrypted,
            identifier_blind_index=blind,
        )
        if predecessor is not None:
            await self._identity.mark_evidence_state(
                ctx.actor_id,
                party_id,
                predecessor.id,
                state=EvidenceState.SUPERSEDED.value,
                expected_version=predecessor.version,
            )
        await self._audit_once(
            ctx,
            action="party.identity-evidence-recorded",
            target_id=party_id,
            after_ref=evidence_id,
        )
        await self._publish(
            ctx,
            "party.identity-evidence-recorded",
            party_id,
            {
                "partyId": party_id,
                "evidenceKind": stored.evidence_kind.value,
                "documentVersionId": stored.document_version_id,
            },
        )
        if input_.expires_on is not None:
            await self._publish(
                ctx,
                "party.identity-document-expiry-recorded",
                party_id,
                {
                    "partyId": party_id,
                    "documentKind": stored.evidence_kind.value,
                    "expiresOn": input_.expires_on.isoformat(),
                },
            )
        return IdentityEvidenceRead(evidence=stored)

    async def verify_identity_evidence(
        self,
        ctx: RequestContext,
        party_id: str,
        evidence_id: str,
        *,
        expected_version: int,
    ) -> IdentityEvidenceRead:
        """Move evidence to `verified`. Requires a practising notary and a pin.

        Identity evidence cannot be verified against nothing: both an immutable
        `documentVersionId` and an `evidenceSpan` must already be recorded
        (party-service.md §3.2, invariant 1).
        """
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_writable_party(ctx, party_id)
        await self._notary.assert_practising(ctx)

        evidence = await self._identity.get_evidence(ctx.actor_id, party_id, evidence_id)
        if evidence is None:
            raise NotFoundError("The requested resource was not found.")
        if not is_evidence_transition_allowed(evidence.state, EvidenceState.VERIFIED):
            raise EvidenceStateTransitionError()
        if not evidence.document_version_id or not evidence.evidence_span:
            raise EvidenceNotPinnedError()

        updated = await self._identity.mark_evidence_state(
            ctx.actor_id,
            party_id,
            evidence_id,
            state=EvidenceState.VERIFIED.value,
            expected_version=expected_version,
            verified_by=ctx.actor_id,
            verified_at=datetime.now(tz=UTC),
        )
        await self._audit_once(
            ctx,
            action="party.identity-evidence-verified",
            target_id=party_id,
            after_ref=evidence_id,
        )
        return IdentityEvidenceRead(evidence=updated)

    async def read_identity_value(
        self,
        ctx: RequestContext,
        party_id: str,
        evidence_id: str,
        *,
        purpose: str,
    ) -> IdentityValueRead:
        """The one audited read in Draftly (§8). No purpose, no identifier."""
        require_capability(ctx.account_role, "party.read-identity")
        if not purpose.strip():
            raise IdentityPurposeRequiredError()
        await self._load_party(ctx, party_id)
        evidence = await self._identity.get_evidence(ctx.actor_id, party_id, evidence_id)
        if evidence is None:
            raise NotFoundError("The requested resource was not found.")
        await self._audit_once(
            ctx,
            action="party.identity-value-read",
            target_id=party_id,
            after_ref=evidence_id,
            reason=purpose.strip(),
        )
        value = await self._identity.decrypt_identifier(ctx.actor_id, party_id, evidence_id)
        return IdentityValueRead(evidence_id=evidence_id, identifier_value=value)

    async def list_identity_evidence(
        self,
        ctx: RequestContext,
        party_id: str,
    ) -> list[IdentityEvidence]:
        await self._load_party(ctx, party_id)
        return await self._identity.list_evidence_for_party(ctx.actor_id, party_id)

    # ── beneficial ownership ─────────────────────────────────────────────────

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
        await self._load_writable_party(ctx, party_id)
        owner_party = await self._parties.get_for_user(ctx.actor_id, owner_party_id)
        if owner_party is None:
            raise CrossUserPartyError()
        await self._assert_no_cycle(ctx, party_id, owner_party_id)

        owner = BeneficialOwner(
            id=f"bo_{uuid.uuid4().hex}",
            party_id=party_id,
            owner_party_id=owner_party_id,
            ownership_kind=OwnershipKind(ownership_kind),
            percentage=percentage,
            evidence_refs=evidence_refs,
            determined_by=ctx.actor_id,
            determined_at=datetime.now(tz=UTC),
            state=BeneficialOwnerState.RECORDED,
        )
        saved = await self._identity.add_beneficial_owner(ctx.actor_id, owner)
        await self._audit_once(
            ctx,
            action="party.beneficial-owner-recorded",
            target_id=party_id,
            after_ref=saved.id,
        )
        return saved

    async def _assert_no_cycle(
        self,
        ctx: RequestContext,
        entity_party_id: str,
        owner_party_id: str,
    ) -> None:
        """Breadth-first walk up the ownership chain, bounded in depth and nodes."""
        if entity_party_id == owner_party_id:
            raise BeneficialOwnerCycleError()
        visited: set[str] = {entity_party_id}
        frontier = [owner_party_id]
        depth = 0
        while frontier:
            depth += 1
            if depth > MAX_BENEFICIAL_OWNERSHIP_DEPTH:
                raise BeneficialOwnerDepthExceededError()
            next_frontier: list[str] = []
            for current in frontier:
                if current in visited:
                    raise BeneficialOwnerCycleError()
                visited.add(current)
                if len(visited) > MAX_BENEFICIAL_OWNERSHIP_NODES:
                    raise BeneficialOwnerDepthExceededError()
                owners = await self._identity.list_beneficial_owners(ctx.actor_id, current)
                next_frontier.extend(o.owner_party_id for o in owners)
            frontier = next_frontier

    async def list_beneficial_owners(
        self,
        ctx: RequestContext,
        party_id: str,
    ) -> list[BeneficialOwner]:
        await self._load_party(ctx, party_id)
        return await self._identity.list_beneficial_owners(ctx.actor_id, party_id)

    # ── CDD ──────────────────────────────────────────────────────────────────

    async def record_cdd(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordCddInput,
    ) -> CddAssessment:
        require_capability(ctx.account_role, "party.record-identity")
        await self._load_writable_party(ctx, party_id)
        assessment = CddAssessment(
            id=f"cdd_{uuid.uuid4().hex}",
            party_id=party_id,
            matter_id=input_.matter_id,
            level=CddLevel(input_.level),
            risk_factors=input_.risk_factors,
            outcome=CddOutcome(input_.outcome),
            assessed_by=ctx.actor_id,
            assessed_at=datetime.now(tz=UTC),
            review_due_on=input_.review_due_on,
            policy_version=input_.policy_version,
            version=1,
        )
        saved = await self._identity.append_cdd(ctx.actor_id, assessment)
        await self._audit_once(
            ctx,
            action="party.cdd-recorded",
            target_id=party_id,
            after_ref=saved.id,
        )
        return saved

    # ── screening ────────────────────────────────────────────────────────────

    async def record_screening(
        self,
        ctx: RequestContext,
        party_id: str,
        input_: RecordScreeningInput,
    ) -> ScreeningResult:
        require_capability(ctx.account_role, "compliance.act")
        party = await self._load_writable_party(ctx, party_id)
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
        saved = await self._identity.append_screening(ctx.actor_id, result, input_.match_detail)
        party.screening_status = ScreeningStatus(outcome.value)
        if outcome in (ScreeningOutcome.POTENTIAL_MATCH, ScreeningOutcome.CONFIRMED_MATCH):
            party.confidentiality_level = ConfidentialityLevel.RESTRICTED_COMPLIANCE
        await self._parties.update(party, party.version)

        await self._audit_once(
            ctx,
            action="party.screening-completed",
            target_id=party_id,
            after_ref=saved.id,
        )
        await self._publish(
            ctx,
            "party.screening-completed",
            party_id,
            {
                "partyId": party_id,
                "outcome": outcome.value,
                "confidentialityLevel": ConfidentialityLevel.RESTRICTED_COMPLIANCE.value,
            },
        )
        if outcome == ScreeningOutcome.CONFIRMED_MATCH:
            await self._publish(
                ctx,
                "party.designated-person-confirmed",
                party_id,
                {
                    "partyId": party_id,
                    "confidentialityLevel": (ConfidentialityLevel.RESTRICTED_COMPLIANCE.value),
                },
            )
        return saved

    async def list_screening_results(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        include_restricted_detail: bool = False,
    ) -> list[dict[str, Any]]:
        """Restricted-compliance (§3.5): a caller without `compliance.view` gets 404.

        The refusal is `RestrictedComplianceError`, identical on the wire to a
        genuinely absent record, and it is raised before the party is loaded so
        that neither the response body nor the work done reveals existence.
        """
        if not holds_compliance_view(ctx.account_role):
            raise RestrictedComplianceError()
        require_capability(ctx.account_role, "compliance.view")
        await self._load_party(ctx, party_id)
        results = await self._identity.list_screenings(ctx.actor_id, party_id)
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
                detail = await self._identity.get_screening_match_detail(ctx.actor_id, result.id)
                if detail:
                    item["match_detail"] = {
                        "list_entry_ref": detail.list_entry_ref,
                        "match_narrative": detail.match_narrative,
                    }
            payload.append(item)
        return payload

    # ── duplicates and merge ─────────────────────────────────────────────────

    async def detect_duplicates(
        self,
        ctx: RequestContext,
        party_id: str,
        *,
        identifier_value: str | None = None,
    ) -> DuplicateProbeResult:
        require_capability(ctx.account_role, "party.record-identity")
        party = await self._load_party(ctx, party_id)
        return await self._probe_duplicates(ctx, party, identifier_value=identifier_value)

    async def _probe_duplicates(
        self,
        ctx: RequestContext,
        party: Party,
        *,
        identifier_value: str | None = None,
    ) -> DuplicateProbeResult:
        """Surface candidates only (§7). Nothing here ever writes."""
        candidates: dict[str, DuplicateCandidate] = {}

        def add(match: Party, reason: str, strength: str) -> None:
            if match.id == party.id or match.merged_into_party_id:
                return
            candidates.setdefault(
                match.id,
                DuplicateCandidate(
                    party_id=match.id,
                    display_name=match.display_name,
                    match_reason=reason,
                    strength=strength,
                ),
            )

        if identifier_value:
            blind = self._encryption.blind_index(identifier_value)
            for match_party, _evidence in await self._identity.find_by_blind_index(
                ctx.actor_id,
                blind,
                exclude_party_id=party.id,
            ):
                add(match_party, "exact-identifier", "strong")

        if party.registration_number:
            for match in await self._parties.find_by_registration_number(
                ctx.actor_id,
                party.registration_number,
                exclude_party_id=party.id,
            ):
                add(match, "registration-number", "strong")

        norm_name = normalise_name_for_probe(party.display_name)
        if party.date_of_birth:
            for match in await self._parties.find_by_normalised_name_and_dob(
                ctx.actor_id,
                norm_name,
                party.date_of_birth,
                exclude_party_id=party.id,
            ):
                add(match, "name-and-dob", "moderate")

        if party.addresses:
            fingerprint = str(party.addresses[0]).lower()
            for match in await self._parties.find_by_normalised_name_and_address(
                ctx.actor_id,
                norm_name,
                fingerprint,
                exclude_party_id=party.id,
            ):
                add(match, "name-and-address", "moderate")

        return DuplicateProbeResult(candidates=list(candidates.values()))

    async def merge_parties(
        self,
        ctx: RequestContext,
        source_id: str,
        target_id: str,
        reason: str,
        *,
        expected_version: int,
    ) -> PartyRead:
        """Pointer-based, administrator-only, never a delete (§5, invariant table).

        A merge is only ever an explicit human decision; the duplicate probe
        surfaces candidates and this method is the only thing that acts on them.
        """
        if ctx.account_role != Role.ADMINISTRATOR:
            raise CapabilityDeniedError(
                "Merging party records requires the administrator role.",
                capability="administrator",
            )
        if not reason.strip():
            raise MergeTargetInvalidError("A merge requires a recorded reason.")
        if source_id == target_id:
            raise MergeTargetInvalidError()

        source = await self._load_writable_party(ctx, source_id)
        target = await self._load_writable_party(ctx, target_id)

        source.merged_into_party_id = target.id
        await self._parties.update(source, expected_version)
        await self._parties.repoint_dependents(ctx.actor_id, source.id, target.id)
        await self._audit_once(
            ctx,
            action="party.merged",
            target_id=source.id,
            after_ref=target.id,
            reason=reason.strip(),
        )
        refreshed = await self._parties.get_for_user(ctx.actor_id, target.id)
        return await self._to_read(ctx, refreshed or target)

    # ── matter parties ───────────────────────────────────────────────────────

    async def list_matter_parties(self, ctx: RequestContext, matter_id: str) -> list[Party]:
        require_party_access(ctx.account_role)
        await self._matter_access.assert_matter_access(ctx.actor_id, matter_id)
        party_ids = await self._matter_access.list_party_ids_for_matter(ctx.actor_id, matter_id)
        parties: list[Party] = []
        for party_id in party_ids[:MAX_MATTER_PARTIES]:
            party = await self._parties.get_for_user(ctx.actor_id, party_id)
            if party is not None:
                parties.append(party)
        return parties
