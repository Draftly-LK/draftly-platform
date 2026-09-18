"""Privacy tests for party_service — party-service.md §11 "Privacy".

Encryption at rest is verified for `identifierValue`, and a dump of the party
tables contains no plaintext identifier.

The dump is taken from the rows the SQL repositories actually persist, captured
through a recording session, rather than from a live Postgres instance: there is
no database-backed test harness in this repository yet. It exercises the real
`SqlPartyRepository` and `SqlIdentityEvidenceRepository` write paths and the
real ORM column set, so a repository that started writing a plaintext column
would fail here. See docs/services/party-service.md §11 for the remaining gap.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
import structlog

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
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.orm import (
    BeneficialOwnerRow,
    CddAssessmentRow,
    IdentityEvidenceRow,
    PartyRow,
    ScreeningMatchDetailRow,
    ScreeningResultRow,
)
from src.modules.party.infrastructure.repository import (
    SqlIdentityEvidenceRepository,
    SqlPartyRepository,
)
from src.platform.privacy import (
    PrivateContentLeakError,
    assert_no_private_content,
    find_private_content,
)
from tests.factories.party import (
    SYNTHETIC_NIC,
    SYNTHETIC_NIC_OLD_FORMAT,
    SYNTHETIC_PASSPORT,
)
from tests.fixtures.party_fakes import ACTOR_A

PARTY_TABLES = (
    PartyRow,
    IdentityEvidenceRow,
    BeneficialOwnerRow,
    CddAssessmentRow,
    ScreeningResultRow,
    ScreeningMatchDetailRow,
)

_FIXED_NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


class RecordingSession:
    """Captures the rows the repositories persist, as a database would."""

    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, row: Any) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None


def _dump(rows: list[Any]) -> str:
    """Render every column of every captured row, the way pg_dump would."""
    lines: list[str] = []
    for row in rows:
        values = {column.name: getattr(row, column.name, None) for column in row.__table__.columns}
        rendered = {
            key: (value.decode("latin-1") if isinstance(value, bytes) else value)
            for key, value in values.items()
        }
        lines.append(f"{row.__tablename__}\t{json.dumps(rendered, default=str)}")
    return "\n".join(lines)


async def _write_every_party_table() -> tuple[str, StubFieldEncryptionAdapter]:
    session = RecordingSession()
    encryption = StubFieldEncryptionAdapter()
    party_repo = SqlPartyRepository(session)  # type: ignore[arg-type]
    identity_repo = SqlIdentityEvidenceRepository(session, encryption)  # type: ignore[arg-type]

    party = Party(
        id="pty_synthetic_0001",
        user_id=ACTOR_A,
        party_kind=PartyKind.NATURAL_PERSON,
        display_name="N. M. Silva (synthetic)",
        name_parts={"full": "N. M. Silva (synthetic)"},
        former_names=[],
        date_of_birth=date(1985, 3, 12),
        registration_number=None,
        nationality="LK",
        residency_status="resident",
        addresses=[{"line1": "12 Synthetic Lane, Colombo (demo)"}],
        contact_points=[],
        risk_rating=RiskRating.UNASSESSED,
        screening_status=ScreeningStatus.NOT_RUN,
        confidentiality_level=ConfidentialityLevel.STANDARD,
        merged_into_party_id=None,
        version=1,
        created_at=_FIXED_NOW,
        updated_at=_FIXED_NOW,
    )
    await party_repo.create(party)

    for identifier, kind, evidence_id in (
        (SYNTHETIC_NIC, EvidenceKind.NIC, "ide_synthetic_0001"),
        (SYNTHETIC_NIC_OLD_FORMAT, EvidenceKind.NIC, "ide_synthetic_0002"),
        (SYNTHETIC_PASSPORT, EvidenceKind.PASSPORT, "ide_synthetic_0003"),
    ):
        await identity_repo.append_evidence(
            ACTOR_A,
            party.id,
            IdentityEvidence(
                id=evidence_id,
                party_id=party.id,
                evidence_kind=kind,
                identifier_value="",
                identifier_last4=identifier[-4:],
                issued_on=date(2018, 6, 1),
                expires_on=date(2030, 6, 1),
                issuing_authority="Synthetic Registrar (demo)",
                document_id="doc_synthetic_0001",
                document_version_id="dver_synthetic_0001",
                evidence_span={"page": 1},
                verified_by=None,
                verified_at=None,
                state=EvidenceState.RECORDED,
                supersedes_evidence_id=None,
                version=1,
            ),
            encrypted_identifier=encryption.encrypt(identifier),
            identifier_blind_index=encryption.blind_index(identifier),
        )

    await identity_repo.add_beneficial_owner(
        ACTOR_A,
        BeneficialOwner(
            id="bo_synthetic_0001",
            party_id=party.id,
            owner_party_id="pty_synthetic_0002",
            ownership_kind=OwnershipKind.SHAREHOLDING,
            percentage=51.0,
            evidence_refs=["ide_synthetic_0001"],
            determined_by=ACTOR_A,
            determined_at=_FIXED_NOW,
            state=BeneficialOwnerState.RECORDED,
        ),
    )
    await identity_repo.append_cdd(
        ACTOR_A,
        CddAssessment(
            id="cdd_synthetic_0001",
            party_id=party.id,
            matter_id=None,
            level=CddLevel.STANDARD,
            risk_factors=["synthetic-demo"],
            outcome=CddOutcome.COMPLETE,
            assessed_by=ACTOR_A,
            assessed_at=_FIXED_NOW,
            review_due_on=date(2027, 1, 1),
            policy_version="cdd-policy-v1",
            version=1,
        ),
    )
    await identity_repo.append_screening(
        ACTOR_A,
        ScreeningResult(
            id="scr_synthetic_0001",
            party_id=party.id,
            list_version="demo-v1",
            provider_ref="manual",
            outcome=ScreeningOutcome.POTENTIAL_MATCH,
            match_count=1,
            reviewed_by=ACTOR_A,
            reviewed_at=_FIXED_NOW,
            disposition_reason=None,
            confidentiality_level=ConfidentialityLevel.RESTRICTED_COMPLIANCE,
            created_at=_FIXED_NOW,
        ),
        ScreeningMatchDetail(
            screening_result_id="scr_synthetic_0001",
            provider_payload={"demo": True},
            match_narrative="Synthetic narrative for tests only.",
            list_entry_ref="SYN-LIST-1",
        ),
    )
    return _dump(session.rows), encryption


class TestEncryptionAtRest:
    def test_no_party_table_has_a_plaintext_identifier_column(self):
        for table in PARTY_TABLES:
            columns = {column.name for column in table.__table__.columns}
            assert "identifier_value" not in columns
            assert "identifierValue" not in columns
        evidence_columns = {c.name for c in IdentityEvidenceRow.__table__.columns}
        assert "identifier_ciphertext" in evidence_columns
        assert "identifier_last4" in evidence_columns

    def test_the_ciphertext_does_not_contain_the_plaintext(self):
        encryption = StubFieldEncryptionAdapter()
        for identifier in (SYNTHETIC_NIC, SYNTHETIC_NIC_OLD_FORMAT, SYNTHETIC_PASSPORT):
            ciphertext = encryption.encrypt(identifier)
            assert identifier.encode() not in ciphertext
            assert identifier not in ciphertext.decode("latin-1", errors="ignore")
            assert encryption.decrypt(ciphertext) == identifier

    def test_encryption_is_not_deterministic(self):
        encryption = StubFieldEncryptionAdapter()
        assert encryption.encrypt(SYNTHETIC_NIC) != encryption.encrypt(SYNTHETIC_NIC)

    async def test_a_dump_of_the_party_tables_has_no_plaintext_identifier(self):
        dump, _ = await _write_every_party_table()
        assert dump  # the dump is not vacuously empty
        for identifier in (SYNTHETIC_NIC, SYNTHETIC_NIC_OLD_FORMAT, SYNTHETIC_PASSPORT):
            assert identifier not in dump
            assert identifier.lower() not in dump.lower()

    async def test_the_dump_covers_every_party_owned_table(self):
        dump, _ = await _write_every_party_table()
        for table in PARTY_TABLES:
            assert table.__tablename__ in dump

    async def test_every_party_owned_row_carries_the_tenant_key(self):
        dump, _ = await _write_every_party_table()
        for line in dump.splitlines():
            _table, payload = line.split("\t", 1)
            assert json.loads(payload)["user_id"] == ACTOR_A


class TestDenylist:
    def test_the_denylist_catches_the_identifier_patterns(self):
        assert find_private_content({"ref": SYNTHETIC_NIC})
        assert find_private_content({"ref": SYNTHETIC_NIC_OLD_FORMAT})
        assert find_private_content({"ref": SYNTHETIC_PASSPORT})

    def test_the_denylist_catches_private_keys(self):
        assert find_private_content({"displayName": "anything"})
        assert find_private_content({"matchNarrative": "anything"})
        assert find_private_content({"nested": [{"snippet": "anything"}]})

    def test_identifiers_and_correlation_ids_are_allowed(self):
        assert (
            find_private_content(
                {
                    "partyId": "pty_9f2c4b1a7d3e4f5a8b6c0d1e2f3a4b5c",
                    "outcome": "confirmed-match",
                    "confidentialityLevel": "restricted-compliance",
                    "correlationId": "corr_party_test",
                }
            )
            == []
        )

    def test_the_violation_message_does_not_repeat_the_value(self):
        with pytest.raises(PrivateContentLeakError) as excinfo:
            assert_no_private_content({"ref": SYNTHETIC_NIC}, context="test")
        assert SYNTHETIC_NIC not in str(excinfo.value)


class TestLogging:
    async def test_no_log_line_carries_an_identifier_or_a_suspicion_signal(self):
        from src.modules.auth.domain.models import Role
        from src.modules.party.ports import RecordIdentityEvidenceInput, RecordScreeningInput
        from tests.fixtures.party_fakes import (
            FakePartyRepo,
            build_service,
            ctx,
            synthetic_party,
        )

        captured: list[Any] = []

        def capture(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
            captured.append(dict(event_dict))
            return event_dict

        original = structlog.get_config()["processors"]
        structlog.configure(processors=[capture, *original])
        try:
            parties = FakePartyRepo()
            await parties.create(synthetic_party(ACTOR_A, "pty_one"))
            service = build_service(party_repo=parties)
            await service.record_identity_evidence(
                ctx(),
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
            await service.record_screening(
                ctx(role=Role.ADMINISTRATOR),
                "pty_one",
                RecordScreeningInput(
                    list_version="demo-v1",
                    provider_ref="manual",
                    outcome="confirmed-match",
                    match_count=1,
                    match_detail=None,
                ),
            )
        finally:
            structlog.configure(processors=original)

        for line in captured:
            assert find_private_content(line) == [], line
            # A log line naming a party as a confirmed designated person is
            # itself a suspicion signal, even without the narrative.
            assert "designated" not in json.dumps(line, default=str).lower()
