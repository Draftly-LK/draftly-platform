"""Unit tests for PartyService — in-memory fakes, no database."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.modules.auth.domain.models import Role
from src.modules.auth.ports import AuditEventInput
from src.modules.party.application.party_service import PartyService
from src.modules.party.domain.errors import (
    BeneficialOwnerCycleError,
    CrossUserPartyError,
    IdentityPurposeRequiredError,
)
from src.modules.party.domain.models import (
    BeneficialOwner,
    BeneficialOwnerState,
    ConfidentialityLevel,
    IdentityEvidence,
    OwnershipKind,
    Party,
    PartyKind,
    RiskRating,
    ScreeningStatus,
)
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.matter_access_stub import StubMatterAccessAdapter
from src.modules.party.infrastructure.stub_screening import ManualScreeningAdapter
from src.modules.party.ports import (
    CreatePartyInput,
    PartyListFilter,
    RecordCddInput,
    RecordIdentityEvidenceInput,
)
from src.platform.errors import CapabilityDeniedError
from src.platform.request_context import RequestContext
from tests.fixtures.party_synthetic import SYNTHETIC_NIC, SYNTHETIC_PARTY_A


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


class FakePartyRepo:
    def __init__(self) -> None:
        self._parties: dict[str, Party] = {}

    async def create(self, party: Party) -> Party:
        self._parties[party.id] = party
        return party

    async def get_for_user(self, user_id: str, party_id: str) -> Party | None:
        party = self._parties.get(party_id)
        if party is None or party.user_id != user_id:
            return None
        return party

    async def list_for_user(self, user_id: str, filter_: PartyListFilter) -> list[Party]:
        items = [p for p in self._parties.values() if p.user_id == user_id]
        if filter_.query:
            items = [p for p in items if filter_.query.lower() in p.display_name.lower()]
        return items

    async def update(self, party: Party, expected_version: int) -> Party:
        current = self._parties[party.id]
        if current.version != expected_version:
            from src.platform.errors import PreconditionFailedError

            raise PreconditionFailedError()
        party.version = expected_version + 1
        self._parties[party.id] = party
        return party

    async def find_by_registration_number(
        self, user_id: str, registration_number: str, *, exclude_party_id: str | None = None
    ) -> list[Party]:
        out = [
            p
            for p in self._parties.values()
            if p.user_id == user_id and p.registration_number == registration_number
        ]
        if exclude_party_id:
            out = [p for p in out if p.id != exclude_party_id]
        return out

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
        if exclude_party_id:
            out = [p for p in out if p.id != exclude_party_id]
        return out

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
        if exclude_party_id:
            out = [p for p in out if p.id != exclude_party_id]
        return out


class FakeIdentityRepo:
    def __init__(
        self,
        encryption: StubFieldEncryptionAdapter,
        party_repo: FakePartyRepo | None = None,
    ) -> None:
        self._encryption = encryption
        self._party_repo = party_repo
        self._evidence: dict[str, IdentityEvidence] = {}
        self._ciphertext: dict[str, bytes] = {}
        self._blind: dict[str, str] = {}
        self._owners: list[BeneficialOwner] = []
        self._screenings: list = []

    async def append_evidence(
        self,
        party_id: str,
        evidence: IdentityEvidence,
        *,
        encrypted_identifier: bytes,
        identifier_blind_index: str,
    ) -> IdentityEvidence:
        self._evidence[evidence.id] = evidence
        self._ciphertext[evidence.id] = encrypted_identifier
        self._blind[evidence.id] = identifier_blind_index
        return evidence

    async def get_evidence(self, party_id: str, evidence_id: str) -> IdentityEvidence | None:
        ev = self._evidence.get(evidence_id)
        if ev is None or ev.party_id != party_id:
            return None
        return ev

    async def list_evidence_for_party(self, party_id: str) -> list[IdentityEvidence]:
        return [e for e in self._evidence.values() if e.party_id == party_id]

    async def find_by_blind_index(
        self, user_id: str, blind_index: str, *, exclude_party_id: str | None = None
    ) -> list[tuple[Party, IdentityEvidence]]:
        pairs: list[tuple[Party, IdentityEvidence]] = []
        for ev_id, blind in self._blind.items():
            if blind != blind_index:
                continue
            ev = self._evidence[ev_id]
            if exclude_party_id and ev.party_id == exclude_party_id:
                continue
            if self._party_repo is None:
                continue
            party = await self._party_repo.get_for_user(user_id, ev.party_id)
            if party is not None:
                pairs.append((party, ev))
        return pairs

    async def decrypt_identifier(self, evidence_id: str) -> str:
        return self._encryption.decrypt(self._ciphertext[evidence_id])

    async def add_beneficial_owner(self, owner: BeneficialOwner) -> BeneficialOwner:
        self._owners.append(owner)
        return owner

    async def list_beneficial_owners(self, party_id: str) -> list[BeneficialOwner]:
        return [o for o in self._owners if o.party_id == party_id]

    async def append_cdd(self, assessment):
        return assessment

    async def append_screening(self, result, match_detail):
        self._screenings.append((result, match_detail))
        return result

    async def list_screenings(self, party_id: str):
        return [r for r, _ in self._screenings if r.party_id == party_id]

    async def get_screening_match_detail(self, screening_id: str):
        for result, detail in self._screenings:
            if result.id == screening_id:
                return detail
        return None


def _ctx(role: Role = Role.REVIEWER, actor: str = "usr_synthetic_a") -> RequestContext:
    return RequestContext(actor_id=actor, account_role=role, correlation_id="corr_party")


def _party(user_id: str, party_id: str) -> Party:
    now = datetime.now(tz=UTC)
    return Party(
        id=party_id,
        user_id=user_id,
        party_kind=PartyKind.NATURAL_PERSON,
        display_name=SYNTHETIC_PARTY_A["display_name"],
        name_parts=dict(SYNTHETIC_PARTY_A["name_parts"]),
        former_names=[],
        date_of_birth=SYNTHETIC_PARTY_A["date_of_birth"],
        registration_number=None,
        nationality="LK",
        residency_status="resident",
        addresses=list(SYNTHETIC_PARTY_A["addresses"]),
        contact_points=[],
        risk_rating=RiskRating.UNASSESSED,
        screening_status=ScreeningStatus.NOT_RUN,
        confidentiality_level=ConfidentialityLevel.STANDARD,
        merged_into_party_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _service(
    party_repo: FakePartyRepo | None = None,
    identity_repo: FakeIdentityRepo | None = None,
    audit: FakeAudit | None = None,
) -> PartyService:
    enc = StubFieldEncryptionAdapter()
    parties = party_repo or FakePartyRepo()
    identity = identity_repo or FakeIdentityRepo(enc, parties)
    return PartyService(
        party_repo=parties,
        identity_repo=identity,
        screening_port=ManualScreeningAdapter(),
        field_encryption=enc,
        matter_access=StubMatterAccessAdapter(),
        audit_port=audit or FakeAudit(),
    )


class TestPartyService:
    async def test_create_party_audits_without_identifier(self):
        audit = FakeAudit()
        service = _service(audit=audit)
        read = await service.create_party(
            _ctx(),
            CreatePartyInput(**{**SYNTHETIC_PARTY_A}),
        )
        assert read.party.display_name.startswith("N. M. Silva")
        assert all("identifier" not in (e.reason or "").lower() for e in audit.events)
        assert audit.events[0].action == "party.created"

    async def test_cross_user_get_is_not_found(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_other", "pty_other"))
        service = _service(party_repo=parties)
        with pytest.raises(CrossUserPartyError):
            await service.get_party(_ctx(actor="usr_synthetic_a"), "pty_other")

    async def test_record_identity_stores_last4_only_in_read_model(self):
        parties = FakePartyRepo()
        party = _party("usr_synthetic_a", "pty_one")
        await parties.create(party)
        enc = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(enc, parties)
        service = _service(party_repo=parties, identity_repo=identity)
        result = await service.record_identity_evidence(
            _ctx(),
            "pty_one",
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=None,
                expires_on=None,
                issuing_authority=None,
                document_id=None,
                document_version_id=None,
                evidence_span=None,
                supersedes_evidence_id=None,
            ),
        )
        assert result.evidence.identifier_last4 == SYNTHETIC_NIC[-4:]
        assert result.evidence.identifier_value == ""

    async def test_read_identity_requires_purpose_and_capability(self):
        parties = FakePartyRepo()
        party = _party("usr_synthetic_a", "pty_one")
        await parties.create(party)
        enc = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(enc, parties)
        service = _service(party_repo=parties, identity_repo=identity)
        recorded = await service.record_identity_evidence(
            _ctx(role=Role.REVIEWER),
            "pty_one",
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=None,
                expires_on=None,
                issuing_authority=None,
                document_id=None,
                document_version_id=None,
                evidence_span=None,
                supersedes_evidence_id=None,
            ),
        )
        with pytest.raises(IdentityPurposeRequiredError):
            await service.read_identity_value(
                _ctx(),
                "pty_one",
                recorded.evidence.id,
                purpose="  ",
            )
        with pytest.raises(CapabilityDeniedError):
            await service.read_identity_value(
                _ctx(role=Role.MAINTAINER),
                "pty_one",
                recorded.evidence.id,
                purpose="cdd-review",
            )

    async def test_read_identity_audits_with_purpose(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_synthetic_a", "pty_one"))
        enc = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(enc, parties)
        audit = FakeAudit()
        service = _service(party_repo=parties, identity_repo=identity, audit=audit)
        recorded = await service.record_identity_evidence(
            _ctx(),
            "pty_one",
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=None,
                expires_on=None,
                issuing_authority=None,
                document_id=None,
                document_version_id=None,
                evidence_span=None,
                supersedes_evidence_id=None,
            ),
        )
        value = await service.read_identity_value(
            _ctx(),
            "pty_one",
            recorded.evidence.id,
            purpose="attestation-check",
        )
        assert value.identifier_value == SYNTHETIC_NIC
        read_events = [e for e in audit.events if e.action == "party.identity-value-read"]
        assert read_events and read_events[-1].reason == "attestation-check"

    async def test_beneficial_owner_cycle_rejected(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_synthetic_a", "pty_entity"))
        await parties.create(_party("usr_synthetic_a", "pty_owner"))
        enc = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(enc, parties)
        await identity.add_beneficial_owner(
            BeneficialOwner(
                id="bo_1",
                party_id="pty_owner",
                owner_party_id="pty_entity",
                ownership_kind=OwnershipKind.SHAREHOLDING,
                percentage=50.0,
                evidence_refs=[],
                determined_by="usr_synthetic_a",
                determined_at=datetime.now(tz=UTC),
                state=BeneficialOwnerState.RECORDED,
            )
        )
        service = _service(party_repo=parties, identity_repo=identity)
        with pytest.raises(BeneficialOwnerCycleError):
            await service.record_beneficial_owner(
                _ctx(),
                "pty_entity",
                owner_party_id="pty_owner",
                ownership_kind="shareholding",
                percentage=25.0,
                evidence_refs=[],
            )

    async def test_detect_duplicates_never_merges(self):
        parties = FakePartyRepo()
        p1 = _party("usr_synthetic_a", "pty_1")
        p1.registration_number = "BR-SYN-001"
        p2 = _party("usr_synthetic_a", "pty_2")
        p2.registration_number = "BR-SYN-001"
        p2.display_name = "Synthetic Holdings (demo)"
        await parties.create(p1)
        await parties.create(p2)
        service = _service(party_repo=parties)
        result = await service.detect_duplicates(_ctx(), "pty_1")
        assert any(c.party_id == "pty_2" for c in result.candidates)
        assert await parties.get_for_user("usr_synthetic_a", "pty_1") is not None
        assert await parties.get_for_user("usr_synthetic_a", "pty_2") is not None

    async def test_record_cdd_pins_policy_version(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_synthetic_a", "pty_one"))
        service = _service(party_repo=parties)
        assessment = await service.record_cdd(
            _ctx(),
            "pty_one",
            RecordCddInput(
                matter_id="matter-usr_synthetic_a",
                level="standard",
                risk_factors=["synthetic-demo"],
                outcome="complete",
                review_due_on=None,
                policy_version="cdd-policy-v1",
            ),
        )
        assert assessment.policy_version == "cdd-policy-v1"
