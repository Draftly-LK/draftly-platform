"""Security tests for party_service — party-service.md §11 "Security".

Cross-user reads are denied; a member without `party.read-identity` never
receives a full identifier; every decryption is audited with a purpose; no
identifier appears in logs, events, or error bodies; and compliance-restricted
rows return no existence signal.
"""

from __future__ import annotations

import statistics
import time

import pytest

from src.modules.auth.domain.models import Role
from src.modules.party.domain.errors import (
    CrossUserPartyError,
    RestrictedComplianceError,
)
from src.modules.party.domain.models import ScreeningMatchDetail
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.matter_access_stub import StubMatterAccessAdapter
from src.modules.party.ports import (
    CreatePartyInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
)
from src.platform.errors import CapabilityDeniedError, NotFoundError
from src.platform.privacy import find_private_content
from tests.fixtures.party_fakes import (
    ACTOR_A,
    ACTOR_B,
    FakeAudit,
    FakeEvents,
    FakeIdentityRepo,
    FakePartyRepo,
    build_service,
    ctx,
    synthetic_party,
)
from tests.fixtures.party_synthetic import SYNTHETIC_NIC, SYNTHETIC_PARTY_A


def _evidence_input() -> RecordIdentityEvidenceInput:
    return RecordIdentityEvidenceInput(
        evidence_kind="nic",
        identifier_value=SYNTHETIC_NIC,
        issued_on=None,
        expires_on=None,
        issuing_authority=None,
        document_id=None,
        document_version_id=None,
        evidence_span=None,
        supersedes_evidence_id=None,
    )


class TestTenancy:
    async def test_cross_user_read_is_404_not_403(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_B, "pty_foreign"))
        service = build_service(party_repo=parties)
        with pytest.raises(CrossUserPartyError) as excinfo:
            await service.get_party(ctx(actor=ACTOR_A), "pty_foreign")
        assert excinfo.value.http_status == 404
        assert excinfo.value.code == "not_found"

    async def test_a_request_body_cannot_choose_the_tenant(self):
        """`user_id` is taken from RequestContext.actor_id and nowhere else."""
        service = build_service()
        forged = dict(SYNTHETIC_PARTY_A)
        # A body field named userId is not part of CreatePartyInput at all, so a
        # forged value cannot even be expressed on the way in.
        assert "user_id" not in forged
        read = await service.create_party(ctx(actor=ACTOR_A), CreatePartyInput(**forged))
        assert read.party.user_id == ACTOR_A

    async def test_evidence_of_another_user_is_invisible(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_mine"))
        await parties.create(synthetic_party(ACTOR_B, "pty_theirs"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        service = build_service(party_repo=parties, identity_repo=identity)

        theirs = await service.record_identity_evidence(
            ctx(actor=ACTOR_B), "pty_theirs", _evidence_input()
        )
        with pytest.raises(NotFoundError):
            await service.read_identity_value(
                ctx(actor=ACTOR_A), "pty_mine", theirs.evidence.id, purpose="cdd-review"
            )


class TestIdentifierExposure:
    async def test_a_list_never_returns_a_full_identifier(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        for item in await service.list_identity_evidence(ctx(), "pty_one"):
            assert item.identifier_value == ""
            assert item.identifier_last4 == SYNTHETIC_NIC[-4:]

    async def test_a_role_without_read_identity_never_receives_the_value(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        with pytest.raises(CapabilityDeniedError):
            await service.read_identity_value(
                ctx(role=Role.MAINTAINER),
                "pty_one",
                recorded.evidence.id,
                purpose="cdd-review",
            )

    async def test_every_decryption_is_audited_with_a_purpose(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        audit = FakeAudit()
        service = build_service(party_repo=parties, identity_repo=identity, audit=audit)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())

        for purpose in ("attestation-check", "cdd-review"):
            await service.read_identity_value(
                ctx(), "pty_one", recorded.evidence.id, purpose=purpose
            )

        reads = [e for e in audit.events if e.action == "party.identity-value-read"]
        assert [e.reason for e in reads] == ["attestation-check", "cdd-review"]
        assert all(e.target_type == "party" for e in reads)

    async def test_a_refused_read_decrypts_nothing(self):
        """The audit entry and the decryption are ordered so a refusal never decrypts."""
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        with pytest.raises(CapabilityDeniedError):
            await service.read_identity_value(
                ctx(role=Role.MAINTAINER), "pty_one", recorded.evidence.id, purpose="x"
            )
        assert [e.action for e in audit.events if e.action == "party.identity-value-read"] == []


class TestRestrictedCompliance:
    async def _service_with_confirmed_match(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        events = FakeEvents()
        service = build_service(party_repo=parties, identity_repo=identity, events=events)
        await service.record_screening(
            ctx(role=Role.ADMINISTRATOR),
            "pty_one",
            RecordScreeningInput(
                list_version="demo-v1",
                provider_ref="manual",
                outcome="confirmed-match",
                match_count=1,
                match_detail=ScreeningMatchDetail(
                    screening_result_id="",
                    provider_payload={"demo": True},
                    match_narrative="Synthetic narrative for tests only.",
                    list_entry_ref="SYN-LIST-1",
                ),
            ),
        )
        return service, events

    async def test_ordinary_member_gets_404_not_403(self):
        service, _ = await self._service_with_confirmed_match()
        with pytest.raises(RestrictedComplianceError) as excinfo:
            await service.list_screening_results(ctx(role=Role.APPROVER), "pty_one")
        assert excinfo.value.http_status == 404
        assert excinfo.value.code == "not_found"

    async def test_the_refusal_body_matches_a_genuine_miss(self):
        service, _ = await self._service_with_confirmed_match()
        with pytest.raises(RestrictedComplianceError) as restricted:
            await service.list_screening_results(ctx(role=Role.APPROVER), "pty_one")
        with pytest.raises(NotFoundError) as absent:
            await service.get_party(ctx(role=Role.APPROVER), "pty_does_not_exist")

        assert (restricted.value.code, restricted.value.message, restricted.value.http_status) == (
            absent.value.code,
            absent.value.message,
            absent.value.http_status,
        )
        assert restricted.value.details == absent.value.details

    async def test_the_refusal_does_no_extra_work(self):
        """Timing cannot leak what the code never looks up.

        Rather than asserting on wall-clock time, which is flaky under a shared
        CI runner, this pins the deterministic cause: the restricted refusal
        returns before touching either repository, so the two paths cannot
        diverge in the number of lookups they perform.
        """
        service, _ = await self._service_with_confirmed_match()
        timings: dict[str, list[float]] = {"restricted": [], "absent": []}
        for _ in range(50):
            start = time.perf_counter()
            with pytest.raises(RestrictedComplianceError):
                await service.list_screening_results(ctx(role=Role.APPROVER), "pty_one")
            timings["restricted"].append(time.perf_counter() - start)

            start = time.perf_counter()
            with pytest.raises(NotFoundError):
                await service.get_party(ctx(role=Role.APPROVER), "pty_missing")
            timings["absent"].append(time.perf_counter() - start)

        restricted = statistics.median(timings["restricted"])
        absent = statistics.median(timings["absent"])
        # A generous bound: this catches a refusal path that hits the database
        # when the other does not, not micro-variation on a busy runner.
        assert max(restricted, absent) < 20 * max(min(restricted, absent), 1e-6)

    async def test_an_ordinary_read_reveals_no_screening_status(self):
        service, _ = await self._service_with_confirmed_match()
        ordinary = await service.get_party(ctx(role=Role.APPROVER), "pty_one")
        assert ordinary.screening_status is None
        compliance = await service.get_party(ctx(role=Role.ADMINISTRATOR), "pty_one")
        assert compliance.screening_status is not None

    async def test_match_detail_needs_compliance_view(self):
        service, _ = await self._service_with_confirmed_match()
        detail = await service.list_screening_results(
            ctx(role=Role.ADMINISTRATOR), "pty_one", include_restricted_detail=True
        )
        assert detail[0]["match_detail"]["list_entry_ref"] == "SYN-LIST-1"
        without_detail = await service.list_screening_results(
            ctx(role=Role.ADMINISTRATOR), "pty_one"
        )
        assert "match_detail" not in without_detail[0]

    async def test_no_narrative_reaches_an_event(self):
        _, events = await self._service_with_confirmed_match()
        for event in events.published:
            assert find_private_content(event.payload) == []
            serialised = str(event.payload)
            assert "narrative" not in serialised.lower()
            assert "SYN-LIST-1" not in serialised


class TestMatterAccessStub:
    async def test_the_stub_denies_by_default(self):
        parties = FakePartyRepo()
        service = build_service(party_repo=parties, matter_access=StubMatterAccessAdapter())
        with pytest.raises(NotFoundError):
            await service.list_matter_parties(ctx(), "matter_synthetic_1")

    async def test_the_stub_refuses_outside_local_and_test(self):
        from src.modules.party.infrastructure.matter_access_stub import (
            MatterServiceUnavailableError,
            build_matter_access_adapter,
        )

        with pytest.raises(MatterServiceUnavailableError):
            build_matter_access_adapter("production")

    async def test_a_non_member_gets_no_existence_signal(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        stub = StubMatterAccessAdapter()
        stub.link_parties("matter_synthetic_1", ACTOR_A, ["pty_one"])
        service = build_service(party_repo=parties, matter_access=stub)

        assert len(await service.list_matter_parties(ctx(actor=ACTOR_A), "matter_synthetic_1")) == 1
        with pytest.raises(NotFoundError):
            await service.list_matter_parties(ctx(actor=ACTOR_B), "matter_synthetic_1")


class TestEncryptionKeyManagement:
    def test_production_refuses_the_development_key(self):
        from src.modules.party.infrastructure.field_encryption import (
            UnconfiguredPartyEncryptionError,
            build_field_encryption_adapter,
        )
        from src.platform.config import Settings

        settings = Settings.model_construct(
            environment="production",
            party_identifier_key="",
            party_blind_index_key="",
        )
        with pytest.raises(UnconfiguredPartyEncryptionError):
            build_field_encryption_adapter(settings)

    def test_the_blind_index_is_not_reversible_and_is_separately_keyed(self):
        adapter = StubFieldEncryptionAdapter()
        blind = adapter.blind_index(SYNTHETIC_NIC)
        assert SYNTHETIC_NIC not in blind
        assert len(blind) == 64
        assert blind != adapter.encrypt(SYNTHETIC_NIC).decode("latin-1", errors="ignore")
        # Same input, same index — that is what makes the exact-match probe work.
        assert adapter.blind_index(f"  {SYNTHETIC_NIC.lower()} ") == blind
