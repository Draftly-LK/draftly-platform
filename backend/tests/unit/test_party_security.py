"""Security tests for party_service — encryption and identifier exposure."""

from __future__ import annotations

from src.modules.auth.domain.models import Role
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.orm import IdentityEvidenceRow
from src.modules.party.ports import RecordIdentityEvidenceInput, RecordScreeningInput
from tests.fixtures.party_synthetic import SYNTHETIC_NIC
from tests.unit.test_party_service import (
    FakeAudit,
    FakeIdentityRepo,
    FakePartyRepo,
    _ctx,
    _party,
    _service,
)


class TestPartySecurity:
    def test_ciphertext_is_not_plaintext_identifier(self):
        enc = StubFieldEncryptionAdapter()
        ciphertext = enc.encrypt(SYNTHETIC_NIC)
        assert SYNTHETIC_NIC.encode() not in ciphertext
        assert SYNTHETIC_NIC not in ciphertext.decode("latin-1", errors="ignore")

    def test_identity_evidence_row_never_stores_plaintext_column(self):
        """ORM uses identifier_ciphertext only — no plaintext identifier field."""
        columns = {c.name for c in IdentityEvidenceRow.__table__.columns}
        assert "identifier_ciphertext" in columns
        assert "identifier_value" not in columns
        assert "identifier_last4" in columns

    async def test_list_evidence_excludes_full_identifier(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_synthetic_a", "pty_one"))
        enc = StubFieldEncryptionAdapter()
        identity = FakeIdentityRepo(enc, parties)
        service = _service(party_repo=parties, identity_repo=identity)
        await service.record_identity_evidence(
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
        items = await service.list_identity_evidence(_ctx(), "pty_one")
        for item in items:
            assert item.identifier_value == ""
            assert item.identifier_last4 == SYNTHETIC_NIC[-4:]

    async def test_designated_person_audit_carries_no_name(self):
        parties = FakePartyRepo()
        await parties.create(_party("usr_synthetic_a", "pty_one"))
        audit = FakeAudit()
        service = _service(party_repo=parties, audit=audit)
        await service.record_screening(
            _ctx(role=Role.ADMINISTRATOR),
            "pty_one",
            RecordScreeningInput(
                list_version="demo-v1",
                provider_ref="manual",
                outcome="confirmed-match",
                match_count=1,
                match_detail=None,
            ),
        )
        confirmed = [e for e in audit.events if e.action == "party.designated-person-confirmed"]
        assert confirmed
        payload = str(confirmed[-1])
        assert "Silva" not in payload
        assert SYNTHETIC_NIC not in payload
