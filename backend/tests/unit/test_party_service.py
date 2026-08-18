"""Unit tests for PartyService — party-service.md §11 "Unit".

Evidence state machine including supersession; `verified` requires a pinned
document version; beneficial-owner cycle rejection; confidentiality is the
maximum of party and screening; the duplicate probe returns candidates and
never merges.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.modules.auth.domain.errors import PracticeStatusError
from src.modules.auth.domain.models import Role
from src.modules.party.domain.errors import (
    BeneficialOwnerCycleError,
    BeneficialOwnerDepthExceededError,
    CrossUserPartyError,
    EvidenceNotPinnedError,
    EvidenceStateTransitionError,
    IdentityPurposeRequiredError,
    MergedPartyImmutableError,
    MergeTargetInvalidError,
)
from src.modules.party.domain.models import (
    BeneficialOwner,
    BeneficialOwnerState,
    ConfidentialityLevel,
    EvidenceState,
    OwnershipKind,
    ScreeningOutcome,
    ScreeningResult,
    ScreeningStatus,
)
from src.modules.party.domain.policies import (
    effective_confidentiality,
    identifier_last4,
    is_evidence_transition_allowed,
)
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.ports import (
    CreatePartyInput,
    PartyListFilter,
    RecordCddInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
)
from src.platform.errors import CapabilityDeniedError
from src.platform.pagination import InvalidLimitError
from tests.fixtures.party_fakes import (
    ACTOR_A,
    ACTOR_B,
    FakeAudit,
    FakeEvents,
    FakeIdentityRepo,
    FakeNotary,
    FakePartyRepo,
    build_service,
    ctx,
    synthetic_party,
)
from tests.fixtures.party_synthetic import (
    SYNTHETIC_DOCUMENT_ID,
    SYNTHETIC_DOCUMENT_VERSION_ID,
    SYNTHETIC_EVIDENCE_SPAN,
    SYNTHETIC_NIC,
    SYNTHETIC_PARTY_A,
)


def _evidence_input(**overrides: object) -> RecordIdentityEvidenceInput:
    base: dict[str, object] = {
        "evidence_kind": "nic",
        "identifier_value": SYNTHETIC_NIC,
        "issued_on": None,
        "expires_on": None,
        "issuing_authority": None,
        "document_id": None,
        "document_version_id": None,
        "evidence_span": None,
        "supersedes_evidence_id": None,
    }
    base.update(overrides)
    return RecordIdentityEvidenceInput(**base)  # type: ignore[arg-type]


def _pinned_evidence_input(**overrides: object) -> RecordIdentityEvidenceInput:
    return _evidence_input(
        document_id=SYNTHETIC_DOCUMENT_ID,
        document_version_id=SYNTHETIC_DOCUMENT_VERSION_ID,
        evidence_span=dict(SYNTHETIC_EVIDENCE_SPAN),
        **overrides,
    )


class TestPartyLifecycle:
    async def test_create_party_audits_exactly_once_without_identifier(self):
        audit = FakeAudit()
        service = build_service(audit=audit)
        read = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        assert read.party.user_id == ACTOR_A
        assert audit.actions() == ["party.created"]

    async def test_created_party_starts_unscreened_and_standard(self):
        service = build_service()
        read = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        assert read.party.screening_status == ScreeningStatus.NOT_RUN
        assert read.effective_confidentiality == ConfidentialityLevel.STANDARD

    async def test_cross_user_get_is_not_found(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_B, "pty_other"))
        service = build_service(party_repo=parties)
        with pytest.raises(CrossUserPartyError):
            await service.get_party(ctx(actor=ACTOR_A), "pty_other")

    async def test_maintainer_has_no_access_to_the_identity_tier(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        with pytest.raises(CapabilityDeniedError):
            await service.get_party(ctx(role=Role.MAINTAINER), "pty_one")

    async def test_update_uses_optimistic_concurrency(self):
        from src.platform.errors import PreconditionFailedError

        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        with pytest.raises(PreconditionFailedError):
            await service.update_party(
                ctx(), "pty_one", display_name="Renamed (demo)", expected_version=99
            )

    async def test_list_refuses_an_out_of_range_limit(self):
        service = build_service()
        with pytest.raises(InvalidLimitError):
            await service.list_parties(ctx(), PartyListFilter(limit=101))

    async def test_list_pages_with_a_cursor(self):
        parties = FakePartyRepo()
        for index in range(5):
            await parties.create(
                synthetic_party(
                    ACTOR_A,
                    f"pty_{index}",
                    created_at=datetime(2026, 1, index + 1, 9, 0, tzinfo=UTC),
                )
            )
        service = build_service(party_repo=parties)
        first = await service.list_parties(ctx(), PartyListFilter(limit=2))
        assert len(first.items) == 2
        assert first.page.has_more is True
        assert first.page.next_cursor

        from src.platform.pagination import decode_cursor

        second = await service.list_parties(
            ctx(), PartyListFilter(limit=2, cursor=decode_cursor(first.page.next_cursor))
        )
        assert {p.id for p in first.items}.isdisjoint({p.id for p in second.items})


class TestIdentityEvidenceStateMachine:
    def test_transition_table_matches_the_documented_states(self):
        assert is_evidence_transition_allowed(EvidenceState.RECORDED, EvidenceState.VERIFIED)
        assert is_evidence_transition_allowed(EvidenceState.VERIFIED, EvidenceState.SUPERSEDED)
        assert not is_evidence_transition_allowed(EvidenceState.SUPERSEDED, EvidenceState.VERIFIED)
        assert not is_evidence_transition_allowed(EvidenceState.REJECTED, EvidenceState.VERIFIED)

    async def test_recording_evidence_stores_last4_and_never_the_value(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        result = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        assert result.evidence.identifier_last4 == SYNTHETIC_NIC[-4:]
        assert result.evidence.identifier_value == ""
        assert result.evidence.state == EvidenceState.RECORDED

    async def test_short_identifier_yields_no_last4(self):
        """Showing "the last four" of a four-character value would show all of it."""
        assert identifier_last4("1234") == ""
        assert identifier_last4("12345") == "2345"

    async def test_renewal_supersedes_the_predecessor(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        service = build_service(party_repo=parties, identity_repo=identity)

        first = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        await service.record_identity_evidence(
            ctx(), "pty_one", _evidence_input(supersedes_evidence_id=first.evidence.id)
        )
        predecessor = await identity.get_evidence(ACTOR_A, "pty_one", first.evidence.id)
        assert predecessor is not None
        assert predecessor.state == EvidenceState.SUPERSEDED

    async def test_superseding_an_already_superseded_record_is_refused(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        service = build_service(party_repo=parties, identity_repo=identity)

        first = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        await service.record_identity_evidence(
            ctx(), "pty_one", _evidence_input(supersedes_evidence_id=first.evidence.id)
        )
        with pytest.raises(EvidenceStateTransitionError):
            await service.record_identity_evidence(
                ctx(), "pty_one", _evidence_input(supersedes_evidence_id=first.evidence.id)
            )

    async def test_verify_requires_a_pinned_document_version(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        unpinned = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        with pytest.raises(EvidenceNotPinnedError):
            await service.verify_identity_evidence(
                ctx(), "pty_one", unpinned.evidence.id, expected_version=1
            )

    async def test_verify_requires_a_practising_notary(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties, notary=FakeNotary(practising=False))
        pinned = await service.record_identity_evidence(ctx(), "pty_one", _pinned_evidence_input())
        with pytest.raises(PracticeStatusError):
            await service.verify_identity_evidence(
                ctx(), "pty_one", pinned.evidence.id, expected_version=1
            )

    async def test_verify_succeeds_with_a_pin_and_a_practising_notary(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)
        pinned = await service.record_identity_evidence(ctx(), "pty_one", _pinned_evidence_input())
        verified = await service.verify_identity_evidence(
            ctx(), "pty_one", pinned.evidence.id, expected_version=1
        )
        assert verified.evidence.state == EvidenceState.VERIFIED
        assert verified.evidence.verified_by == ACTOR_A
        assert audit.actions().count("party.identity-evidence-verified") == 1


class TestIdentifierReads:
    async def test_read_requires_a_purpose(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        service = build_service(party_repo=parties)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        with pytest.raises(IdentityPurposeRequiredError):
            await service.read_identity_value(ctx(), "pty_one", recorded.evidence.id, purpose="   ")

    async def test_read_requires_the_capability(self):
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

    async def test_read_returns_the_value_and_audits_the_purpose(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        value = await service.read_identity_value(
            ctx(), "pty_one", recorded.evidence.id, purpose="attestation-check"
        )
        assert value.identifier_value == SYNTHETIC_NIC
        reads = [e for e in audit.events if e.action == "party.identity-value-read"]
        assert len(reads) == 1
        assert reads[0].reason == "attestation-check"
        assert reads[0].target_id == "pty_one"


class TestBeneficialOwnership:
    async def test_self_ownership_is_a_cycle(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_entity"))
        service = build_service(party_repo=parties)
        with pytest.raises(BeneficialOwnerCycleError):
            await service.record_beneficial_owner(
                ctx(),
                "pty_entity",
                owner_party_id="pty_entity",
                ownership_kind="shareholding",
                percentage=100.0,
                evidence_refs=[],
            )

    async def test_indirect_cycle_is_rejected(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_entity"))
        await parties.create(synthetic_party(ACTOR_A, "pty_owner"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        await identity.add_beneficial_owner(
            ACTOR_A,
            BeneficialOwner(
                id="bo_seed",
                party_id="pty_owner",
                owner_party_id="pty_entity",
                ownership_kind=OwnershipKind.SHAREHOLDING,
                percentage=50.0,
                evidence_refs=[],
                determined_by=ACTOR_A,
                determined_at=datetime(2026, 1, 1, tzinfo=UTC),
                state=BeneficialOwnerState.RECORDED,
            ),
        )
        service = build_service(party_repo=parties, identity_repo=identity)
        with pytest.raises(BeneficialOwnerCycleError):
            await service.record_beneficial_owner(
                ctx(),
                "pty_entity",
                owner_party_id="pty_owner",
                ownership_kind="shareholding",
                percentage=25.0,
                evidence_refs=[],
            )

    async def test_owner_in_another_user_is_not_found(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_entity"))
        await parties.create(synthetic_party(ACTOR_B, "pty_foreign"))
        service = build_service(party_repo=parties)
        with pytest.raises(CrossUserPartyError):
            await service.record_beneficial_owner(
                ctx(),
                "pty_entity",
                owner_party_id="pty_foreign",
                ownership_kind="shareholding",
                percentage=10.0,
                evidence_refs=[],
            )

    async def test_chain_deeper_than_the_limit_is_refused(self):
        from src.modules.party.domain.policies import MAX_BENEFICIAL_OWNERSHIP_DEPTH

        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        chain_length = MAX_BENEFICIAL_OWNERSHIP_DEPTH + 3
        for index in range(chain_length):
            await parties.create(synthetic_party(ACTOR_A, f"pty_link_{index}"))
        for index in range(chain_length - 1):
            await identity.add_beneficial_owner(
                ACTOR_A,
                BeneficialOwner(
                    id=f"bo_link_{index}",
                    party_id=f"pty_link_{index}",
                    owner_party_id=f"pty_link_{index + 1}",
                    ownership_kind=OwnershipKind.SHAREHOLDING,
                    percentage=100.0,
                    evidence_refs=[],
                    determined_by=ACTOR_A,
                    determined_at=datetime(2026, 1, 1, tzinfo=UTC),
                    state=BeneficialOwnerState.RECORDED,
                ),
            )
        await parties.create(synthetic_party(ACTOR_A, "pty_root"))
        service = build_service(party_repo=parties, identity_repo=identity)
        with pytest.raises(BeneficialOwnerDepthExceededError):
            await service.record_beneficial_owner(
                ctx(),
                "pty_root",
                owner_party_id="pty_link_0",
                ownership_kind="shareholding",
                percentage=100.0,
                evidence_refs=[],
            )


class TestConfidentiality:
    def test_confidentiality_is_the_maximum_of_party_and_screening(self):
        potential = ScreeningResult(
            id="scr_demo",
            party_id="pty_one",
            list_version="demo-v1",
            provider_ref="manual",
            outcome=ScreeningOutcome.POTENTIAL_MATCH,
            match_count=1,
            reviewed_by=ACTOR_A,
            reviewed_at=datetime(2026, 1, 1, tzinfo=UTC),
            disposition_reason=None,
            confidentiality_level=ConfidentialityLevel.RESTRICTED_COMPLIANCE,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert (
            effective_confidentiality(ConfidentialityLevel.STANDARD, [potential])
            == ConfidentialityLevel.RESTRICTED_COMPLIANCE
        )
        assert (
            effective_confidentiality(ConfidentialityLevel.PRIVATE_MATTER, [])
            == ConfidentialityLevel.PRIVATE_MATTER
        )

    def test_a_clear_screening_does_not_raise_confidentiality(self):
        clear = ScreeningResult(
            id="scr_clear",
            party_id="pty_one",
            list_version="demo-v1",
            provider_ref="manual",
            outcome=ScreeningOutcome.CLEAR,
            match_count=0,
            reviewed_by=ACTOR_A,
            reviewed_at=datetime(2026, 1, 1, tzinfo=UTC),
            disposition_reason=None,
            confidentiality_level=ConfidentialityLevel.RESTRICTED_COMPLIANCE,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert (
            effective_confidentiality(ConfidentialityLevel.STANDARD, [clear])
            == ConfidentialityLevel.STANDARD
        )


class TestDuplicatesAndMerge:
    async def test_probe_surfaces_candidates_and_writes_nothing(self):
        parties = FakePartyRepo()
        first = synthetic_party(ACTOR_A, "pty_1")
        first.registration_number = "BR-SYN-0001"
        second = synthetic_party(ACTOR_A, "pty_2", display_name="Synthetic Holdings (demo)")
        second.registration_number = "BR-SYN-0001"
        await parties.create(first)
        await parties.create(second)
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)

        result = await service.detect_duplicates(ctx(), "pty_1")

        assert [c.party_id for c in result.candidates] == ["pty_2"]
        assert result.candidates[0].match_reason == "registration-number"
        # Nothing merged, nothing audited: a probe is a read.
        assert audit.events == []
        for party_id in ("pty_1", "pty_2"):
            party = await parties.get_for_user(ACTOR_A, party_id)
            assert party is not None
            assert party.merged_into_party_id is None

    async def test_an_exact_identifier_match_is_a_candidate_not_a_merge(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_1"))
        await parties.create(synthetic_party(ACTOR_A, "pty_2"))
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        service = build_service(party_repo=parties, identity_repo=identity)
        await service.record_identity_evidence(ctx(), "pty_2", _evidence_input())

        result = await service.detect_duplicates(ctx(), "pty_1", identifier_value=SYNTHETIC_NIC)

        strong = [c for c in result.candidates if c.match_reason == "exact-identifier"]
        assert [c.party_id for c in strong] == ["pty_2"]
        assert strong[0].strength == "strong"
        target = await parties.get_for_user(ACTOR_A, "pty_1")
        assert target is not None
        assert target.merged_into_party_id is None

    async def test_merge_requires_administrator(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_src"))
        await parties.create(synthetic_party(ACTOR_A, "pty_dst"))
        service = build_service(party_repo=parties)
        with pytest.raises(CapabilityDeniedError):
            await service.merge_parties(
                ctx(role=Role.APPROVER),
                "pty_src",
                "pty_dst",
                "duplicate confirmed by hand",
                expected_version=1,
            )

    async def test_merge_requires_a_reason(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_src"))
        await parties.create(synthetic_party(ACTOR_A, "pty_dst"))
        service = build_service(party_repo=parties)
        with pytest.raises(MergeTargetInvalidError):
            await service.merge_parties(
                ctx(role=Role.ADMINISTRATOR), "pty_src", "pty_dst", "  ", expected_version=1
            )

    async def test_merge_points_and_never_deletes(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_src"))
        await parties.create(synthetic_party(ACTOR_A, "pty_dst"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)

        await service.merge_parties(
            ctx(role=Role.ADMINISTRATOR),
            "pty_src",
            "pty_dst",
            "same person, confirmed against the register",
            expected_version=1,
        )

        source = await parties.get_for_user(ACTOR_A, "pty_src")
        assert source is not None
        assert source.merged_into_party_id == "pty_dst"
        assert parties.repointed == [("pty_src", "pty_dst")]
        assert audit.actions() == ["party.merged"]
        assert audit.events[0].reason == "same person, confirmed against the register"

    async def test_a_merged_party_refuses_further_writes(self):
        parties = FakePartyRepo()
        source = synthetic_party(ACTOR_A, "pty_src")
        source.merged_into_party_id = "pty_dst"
        await parties.create(source)
        service = build_service(party_repo=parties)
        with pytest.raises(MergedPartyImmutableError):
            await service.record_identity_evidence(ctx(), "pty_src", _evidence_input())


class TestCdd:
    async def test_cdd_pins_its_policy_version_and_audits_once(self):
        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)
        assessment = await service.record_cdd(
            ctx(),
            "pty_one",
            RecordCddInput(
                matter_id=None,
                level="standard",
                risk_factors=["synthetic-demo"],
                outcome="complete",
                review_due_on=date(2027, 1, 1),
                policy_version="cdd-policy-v1",
            ),
        )
        assert assessment.policy_version == "cdd-policy-v1"
        assert audit.actions() == ["party.cdd-recorded"]


class TestAuditCoverage:
    """Exactly one audit event per mutating application method (§9)."""

    async def test_every_mutation_writes_one_audit_event(self):
        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        audit = FakeAudit()
        events = FakeEvents()
        service = build_service(
            party_repo=parties, identity_repo=identity, audit=audit, events=events
        )

        created = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        assert len(audit.events) == 1

        await service.update_party(
            ctx(), created.party.id, display_name="Renamed (demo)", expected_version=1
        )
        assert len(audit.events) == 2

        recorded = await service.record_identity_evidence(
            ctx(), created.party.id, _pinned_evidence_input(expires_on=date(2030, 1, 1))
        )
        # Two events were published, but still only one audit entry.
        assert len(audit.events) == 3
        assert len(events.published) == 3

        await service.verify_identity_evidence(
            ctx(), created.party.id, recorded.evidence.id, expected_version=1
        )
        assert len(audit.events) == 4

        await service.record_screening(
            ctx(role=Role.ADMINISTRATOR),
            created.party.id,
            RecordScreeningInput(
                list_version="demo-v1",
                provider_ref="manual",
                outcome="confirmed-match",
                match_count=1,
                match_detail=None,
            ),
        )
        assert len(audit.events) == 5
        assert audit.actions()[-1] == "party.screening-completed"

    async def test_no_audit_payload_carries_a_name_or_identifier(self):
        from src.platform.privacy import find_private_content

        parties = FakePartyRepo()
        await parties.create(synthetic_party(ACTOR_A, "pty_one"))
        audit = FakeAudit()
        service = build_service(party_repo=parties, audit=audit)
        recorded = await service.record_identity_evidence(ctx(), "pty_one", _evidence_input())
        await service.read_identity_value(
            ctx(), "pty_one", recorded.evidence.id, purpose="attestation-check"
        )
        for event in audit.events:
            assert find_private_content(vars(event)) == []
