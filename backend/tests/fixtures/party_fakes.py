"""In-memory doubles for the party ports.

Every fake enforces the same user scoping the SQL repositories do, so a test
that passes here would also fail if the service stopped passing `ctx.actor_id`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from src.modules.auth.domain.models import Role
from src.modules.party.application.party_service import PartyService
from src.modules.party.domain.models import (
    BeneficialOwner,
    CddAssessment,
    ConfidentialityLevel,
    IdentityEvidence,
    Party,
    PartyKind,
    RiskRating,
    ScreeningMatchDetail,
    ScreeningResult,
    ScreeningStatus,
)
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.matter_access_stub import StubMatterAccessAdapter
from src.modules.party.infrastructure.stub_screening import ManualScreeningAdapter
from src.modules.party.ports import DomainEvent, PartyListFilter, PartyPage
from src.platform.errors import NotFoundError, PreconditionFailedError
from src.platform.request_context import RequestContext
from tests.factories.audit import FakeAudit
from tests.factories.party import SYNTHETIC_PARTY_A

ACTOR_A = "usr_synthetic_a"
ACTOR_B = "usr_synthetic_b"


class FakeEvents:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)

    def named(self, name: str) -> list[DomainEvent]:
        return [e for e in self.published if e.name == name]


class FakeNotary:
    """Practising-status double. Refuses by default so the check cannot pass by accident."""

    def __init__(self, *, practising: bool = True) -> None:
        self.practising = practising
        self.calls = 0

    async def assert_practising(self, ctx: RequestContext) -> None:
        self.calls += 1
        if not self.practising:
            from src.modules.auth.domain.errors import PracticeStatusError

            raise PracticeStatusError("A current notary practice certificate is required.")


class FakePartyRepo:
    def __init__(self) -> None:
        self._parties: dict[str, Party] = {}
        self.repointed: list[tuple[str, str]] = []

    async def create(self, party: Party) -> Party:
        self._parties[party.id] = party
        return party

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None:
        party = self._parties.get(party_id)
        if party is None or party.user_id != user_id:
            return None
        return party

    async def list_for_user(self, user_id: str, filter_: PartyListFilter) -> PartyPage:
        items = [p for p in self._parties.values() if p.user_id == user_id]
        if filter_.query:
            items = [p for p in items if filter_.query.lower() in p.display_name.lower()]
        items.sort(key=lambda p: (p.created_at, p.id), reverse=True)
        if filter_.cursor is not None:
            key = (filter_.cursor.created_at, filter_.cursor.id)
            items = [p for p in items if (p.created_at, p.id) < key]
        window = items[: filter_.limit]
        return PartyPage(items=window, has_more=len(items) > filter_.limit)

    async def update(self, party: Party, expected_version: int) -> Party:
        current = self._parties.get(party.id)
        if current is None or current.user_id != party.user_id:
            raise NotFoundError("The requested resource was not found.")
        if current.version != expected_version:
            raise PreconditionFailedError("Party version conflict.")
        party.version = expected_version + 1
        self._parties[party.id] = party
        return party

    async def find_by_registration_number(
        self,
        user_id: str,
        registration_number: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        out = [
            p
            for p in self._parties.values()
            if p.user_id == user_id
            and p.registration_number
            and p.registration_number == registration_number
        ]
        return [p for p in out if p.id != exclude_party_id]

    async def find_by_normalised_name_and_dob(
        self,
        user_id: str,
        normalised_name: str,
        date_of_birth: date,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        out = [
            p
            for p in self._parties.values()
            if p.user_id == user_id
            and p.date_of_birth == date_of_birth
            and normalised_name in p.display_name.lower()
        ]
        return [p for p in out if p.id != exclude_party_id]

    async def find_by_normalised_name_and_address(
        self,
        user_id: str,
        normalised_name: str,
        address_fingerprint: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[Party]:
        out: list[Party] = []
        for p in self._parties.values():
            if p.user_id != user_id or normalised_name not in p.display_name.lower():
                continue
            if any(address_fingerprint in str(a).lower() for a in p.addresses):
                out.append(p)
        return [p for p in out if p.id != exclude_party_id]

    async def repoint_dependents(
        self,
        user_id: str,
        source_party_id: str,
        target_party_id: str,
    ) -> int:
        self.repointed.append((source_party_id, target_party_id))
        return 0


class FakeIdentityRepo:
    def __init__(
        self,
        encryption: StubFieldEncryptionAdapter,
        party_repo: FakePartyRepo | None = None,
    ) -> None:
        self._encryption = encryption
        self._party_repo = party_repo
        self._evidence: dict[str, tuple[str, IdentityEvidence]] = {}
        self._ciphertext: dict[str, bytes] = {}
        self._blind: dict[str, str] = {}
        self._owners: list[tuple[str, BeneficialOwner]] = []
        self._cdd: list[tuple[str, CddAssessment]] = []
        self._screenings: list[tuple[str, ScreeningResult, ScreeningMatchDetail | None]] = []

    async def append_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence:
        self._evidence[evidence.id] = (user_id, evidence)
        self._ciphertext[evidence.id] = encrypted_identifier
        self._blind[evidence.id] = identifier_blind_index
        return evidence

    async def get_evidence(
        self,
        user_id: str,
        party_id: str,
        evidence_id: str,
    ) -> IdentityEvidence | None:
        entry = self._evidence.get(evidence_id)
        if entry is None:
            return None
        owner, evidence = entry
        if owner != user_id or evidence.party_id != party_id:
            return None
        return evidence

    async def list_evidence_for_party(
        self,
        user_id: str,
        party_id: str,
    ) -> list[IdentityEvidence]:
        return [
            e for owner, e in self._evidence.values() if owner == user_id and e.party_id == party_id
        ]

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
    ) -> IdentityEvidence:
        from src.modules.party.domain.models import EvidenceState

        evidence = await self.get_evidence(user_id, party_id, evidence_id)
        if evidence is None:
            raise NotFoundError("The requested resource was not found.")
        if evidence.version != expected_version:
            raise PreconditionFailedError("Identity evidence version conflict.")
        evidence.state = EvidenceState(state)
        evidence.verified_by = verified_by or evidence.verified_by
        evidence.verified_at = verified_at or evidence.verified_at
        evidence.version = expected_version + 1
        return evidence

    async def find_by_blind_index(
        self,
        user_id: str,
        blind_index: str,
        *,
        exclude_party_id: str | None = None,
    ) -> list[tuple[Party, IdentityEvidence]]:
        pairs: list[tuple[Party, IdentityEvidence]] = []
        for evidence_id, blind in self._blind.items():
            if blind != blind_index:
                continue
            owner, evidence = self._evidence[evidence_id]
            if owner != user_id or evidence.party_id == exclude_party_id:
                continue
            if self._party_repo is None:
                continue
            party = await self._party_repo.get_for_user(user_id, evidence.party_id)
            if party is not None:
                pairs.append((party, evidence))
        return pairs

    async def decrypt_identifier(self, user_id: str, party_id: str, evidence_id: str) -> str:
        evidence = await self.get_evidence(user_id, party_id, evidence_id)
        if evidence is None:
            raise NotFoundError("The requested resource was not found.")
        return self._encryption.decrypt(self._ciphertext[evidence_id])

    async def add_beneficial_owner(self, user_id: str, owner: BeneficialOwner) -> BeneficialOwner:
        self._owners.append((user_id, owner))
        return owner

    async def list_beneficial_owners(
        self,
        user_id: str,
        party_id: str,
    ) -> list[BeneficialOwner]:
        return [o for u, o in self._owners if u == user_id and o.party_id == party_id]

    async def append_cdd(self, user_id: str, assessment: CddAssessment) -> CddAssessment:
        self._cdd.append((user_id, assessment))
        return assessment

    async def append_screening(
        self,
        user_id: str,
        result: ScreeningResult,
        match_detail: ScreeningMatchDetail | None,
    ) -> ScreeningResult:
        self._screenings.append((user_id, result, match_detail))
        return result

    async def list_screenings(self, user_id: str, party_id: str) -> list[ScreeningResult]:
        return [r for u, r, _ in self._screenings if u == user_id and r.party_id == party_id]

    async def get_screening_match_detail(
        self,
        user_id: str,
        screening_id: str,
    ) -> ScreeningMatchDetail | None:
        for user, result, detail in self._screenings:
            if user == user_id and result.id == screening_id:
                return detail
        return None


def ctx(role: Role = Role.REVIEWER, actor: str = ACTOR_A) -> RequestContext:
    return RequestContext(actor_id=actor, account_role=role, correlation_id="corr_party_test")


def synthetic_party(
    user_id: str,
    party_id: str,
    *,
    created_at: datetime | None = None,
    display_name: str | None = None,
) -> Party:
    """Fixed timestamps by default — no Date.now in a fixture."""
    when = created_at or datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    return Party(
        id=party_id,
        user_id=user_id,
        party_kind=PartyKind.NATURAL_PERSON,
        display_name=display_name or str(SYNTHETIC_PARTY_A["display_name"]),
        name_parts=dict(SYNTHETIC_PARTY_A["name_parts"]),  # type: ignore[arg-type]
        former_names=[],
        date_of_birth=SYNTHETIC_PARTY_A["date_of_birth"],  # type: ignore[arg-type]
        registration_number=None,
        nationality="LK",
        residency_status="resident",
        addresses=list(SYNTHETIC_PARTY_A["addresses"]),  # type: ignore[arg-type]
        contact_points=[],
        risk_rating=RiskRating.UNASSESSED,
        screening_status=ScreeningStatus.NOT_RUN,
        confidentiality_level=ConfidentialityLevel.STANDARD,
        merged_into_party_id=None,
        version=1,
        created_at=when,
        updated_at=when,
    )


def build_service(
    *,
    party_repo: FakePartyRepo | None = None,
    identity_repo: FakeIdentityRepo | None = None,
    audit: FakeAudit | None = None,
    events: FakeEvents | None = None,
    notary: FakeNotary | None = None,
    matter_access: StubMatterAccessAdapter | None = None,
) -> PartyService:
    encryption = StubFieldEncryptionAdapter()
    parties = party_repo or FakePartyRepo()
    identity = identity_repo or FakeIdentityRepo(encryption, parties)
    return PartyService(
        party_repo=parties,
        identity_repo=identity,
        screening_port=ManualScreeningAdapter(),
        field_encryption=encryption,
        matter_access=matter_access or StubMatterAccessAdapter(),
        audit_port=audit or FakeAudit(),
        event_port=events or FakeEvents(),
        notary_port=notary or FakeNotary(),
    )
