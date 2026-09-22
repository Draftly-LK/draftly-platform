"""Integration tests for party_service — party-service.md §11 "Integration".

These wire the real application service to in-memory port doubles and exercise
whole flows end to end within the service boundary. Two rows of the §11 list
cannot be written yet and are recorded as gaps rather than faked:

- "expiry produces an obligation" is asserted as far as this service's
  responsibility goes — the `party.identity-document-expiry-recorded` event —
  because `obligations_service` does not exist.
- "legal hold blocks merge" needs `retention_service`, which does not exist.

There is also no database-backed harness in this repository, so these run
against the port doubles rather than Postgres.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modules.auth.domain.models import Role
from src.modules.party.domain.errors import RestrictedComplianceError
from src.modules.party.domain.models import EvidenceState, ScreeningMatchDetail
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.ports import (
    CreatePartyInput,
    RecordCddInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
)
from tests.factories.party import (
    SYNTHETIC_DOCUMENT_ID,
    SYNTHETIC_DOCUMENT_VERSION_ID,
    SYNTHETIC_EVIDENCE_SPAN,
    SYNTHETIC_NIC,
    SYNTHETIC_PARTY_A,
    SYNTHETIC_PARTY_B,
)
from tests.fixtures.party_fakes import (
    ACTOR_A,
    FakeAudit,
    FakeEvents,
    FakeIdentityRepo,
    FakePartyRepo,
    build_service,
    ctx,
)


class TestIdentityEvidenceFlow:
    async def test_nic_evidence_pinned_to_a_document_version_reaches_verified(self):
        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        events = FakeEvents()
        audit = FakeAudit()
        service = build_service(
            party_repo=parties, identity_repo=identity, events=events, audit=audit
        )

        party = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        recorded = await service.record_identity_evidence(
            ctx(),
            party.party.id,
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=date(2018, 6, 1),
                expires_on=date(2030, 6, 1),
                issuing_authority="Synthetic Registrar (demo)",
                document_id=SYNTHETIC_DOCUMENT_ID,
                document_version_id=SYNTHETIC_DOCUMENT_VERSION_ID,
                evidence_span=dict(SYNTHETIC_EVIDENCE_SPAN),
                supersedes_evidence_id=None,
            ),
        )
        verified = await service.verify_identity_evidence(
            ctx(), party.party.id, recorded.evidence.id, expected_version=1
        )

        assert verified.evidence.state == EvidenceState.VERIFIED
        assert verified.evidence.document_version_id == SYNTHETIC_DOCUMENT_VERSION_ID
        assert verified.evidence.evidence_span == dict(SYNTHETIC_EVIDENCE_SPAN)
        assert verified.evidence.verified_by == ACTOR_A

        # The full identifier is still only reachable through the audited read.
        listed = await service.list_identity_evidence(ctx(), party.party.id)
        assert all(e.identifier_value == "" for e in listed)
        value = await service.read_identity_value(
            ctx(), party.party.id, recorded.evidence.id, purpose="attestation-check"
        )
        assert value.identifier_value == SYNTHETIC_NIC

    async def test_an_expiry_date_publishes_the_obligation_trigger(self):
        events = FakeEvents()
        service = build_service(events=events)
        party = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        await service.record_identity_evidence(
            ctx(),
            party.party.id,
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=None,
                expires_on=date(2030, 6, 1),
                issuing_authority=None,
                document_id=None,
                document_version_id=None,
                evidence_span=None,
                supersedes_evidence_id=None,
            ),
        )
        expiry = events.named("party.identity-document-expiry-recorded")
        assert len(expiry) == 1
        assert expiry[0].payload["expiresOn"] == "2030-06-01"
        assert expiry[0].payload["documentKind"] == "nic"

    async def test_no_expiry_date_publishes_nothing(self):
        events = FakeEvents()
        service = build_service(events=events)
        party = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        await service.record_identity_evidence(
            ctx(),
            party.party.id,
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
        assert events.named("party.identity-document-expiry-recorded") == []


class TestConfirmedMatchFlow:
    async def test_a_confirmed_match_restricts_the_party_and_hides_the_detail(self):
        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        events = FakeEvents()
        service = build_service(party_repo=parties, identity_repo=identity, events=events)

        party = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        await service.record_screening(
            ctx(role=Role.ADMINISTRATOR),
            party.party.id,
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

        escalation = events.named("party.designated-person-confirmed")
        assert len(escalation) == 1
        assert escalation[0].payload["confidentialityLevel"] == "restricted-compliance"

        ordinary = await service.get_party(ctx(role=Role.APPROVER), party.party.id)
        assert ordinary.screening_status is None
        assert ordinary.effective_confidentiality.value == "restricted-compliance"
        with pytest.raises(RestrictedComplianceError):
            await service.list_screening_results(ctx(role=Role.APPROVER), party.party.id)

        compliance = await service.list_screening_results(
            ctx(role=Role.ADMINISTRATOR), party.party.id, include_restricted_detail=True
        )
        assert compliance[0]["outcome"] == "confirmed-match"
        assert compliance[0]["match_detail"]["list_entry_ref"] == "SYN-LIST-1"

    async def test_a_provider_outage_leaves_the_screening_not_run(self):
        """Nothing infers `clear` — absence of a result stays absence (§10)."""
        service = build_service()
        party = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        read = await service.get_party(ctx(role=Role.ADMINISTRATOR), party.party.id)
        assert read.screening_status is not None
        assert read.screening_status.value == "not-run"


class TestMergeFlow:
    async def test_a_merge_repoints_dependents_and_keeps_the_source(self):
        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        audit = FakeAudit()
        service = build_service(party_repo=parties, identity_repo=identity, audit=audit)

        source = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        target = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_B))
        await service.record_identity_evidence(
            ctx(),
            source.party.id,
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
        await service.record_cdd(
            ctx(),
            source.party.id,
            RecordCddInput(
                matter_id=None,
                level="standard",
                risk_factors=["synthetic-demo"],
                outcome="complete",
                review_due_on=None,
                policy_version="cdd-policy-v1",
            ),
        )

        await service.merge_parties(
            ctx(role=Role.ADMINISTRATOR),
            source.party.id,
            target.party.id,
            "same person, confirmed by hand",
            expected_version=source.party.version,
        )

        surviving = await parties.get_for_user(ACTOR_A, source.party.id)
        assert surviving is not None, "a merge must never delete the source"
        assert surviving.merged_into_party_id == target.party.id
        assert parties.repointed == [(source.party.id, target.party.id)]
        merge_audit = [e for e in audit.events if e.action == "party.merged"]
        assert len(merge_audit) == 1
        assert merge_audit[0].after_ref == target.party.id
        assert merge_audit[0].reason == "same person, confirmed by hand"

    @pytest.mark.skip(reason="retention_service does not exist yet; legal hold cannot be asserted")
    async def test_a_legal_hold_blocks_a_merge(self):
        raise NotImplementedError


class TestDuplicateFlow:
    async def test_the_same_person_in_two_records_is_surfaced_not_merged(self):
        parties = FakePartyRepo()
        encryption = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(encryption, parties)
        service = build_service(party_repo=parties, identity_repo=identity)

        first = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        spelling_variant = dict(SYNTHETIC_PARTY_A)
        second = await service.create_party(ctx(), CreatePartyInput(**spelling_variant))

        for party_id in (first.party.id, second.party.id):
            await service.record_identity_evidence(
                ctx(),
                party_id,
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

        probe = await service.detect_duplicates(
            ctx(), first.party.id, identifier_value=SYNTHETIC_NIC
        )
        assert [c.party_id for c in probe.candidates][0] == second.party.id
        assert probe.candidates[0].strength == "strong"

        for party_id in (first.party.id, second.party.id):
            party = await parties.get_for_user(ACTOR_A, party_id)
            assert party is not None
            assert party.merged_into_party_id is None
