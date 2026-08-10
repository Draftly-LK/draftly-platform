"""Contract tests — party API schemas never expose full identifiers on list/detail."""

from __future__ import annotations

from datetime import UTC, datetime

from src.modules.party.api.schemas import (
    IdentityEvidenceReadSchema,
    PartyListItemSchema,
    PartyReadSchema,
)


class TestPartyContract:
    def test_party_read_schema_fields(self):
        now = datetime.now(tz=UTC)
        schema = PartyReadSchema(
            id="pty_demo",
            party_kind="natural-person",
            display_name="Synthetic Person (demo)",
            name_parts={},
            former_names=[],
            date_of_birth=None,
            registration_number=None,
            nationality="LK",
            residency_status=None,
            addresses=[],
            contact_points=[],
            risk_rating="unassessed",
            screening_status="not-run",
            confidentiality_level="standard",
            effective_confidentiality="standard",
            merged_into_party_id=None,
            version=1,
            created_at=now,
            updated_at=now,
            duplicate_candidates=[],
        )
        data = schema.model_dump(by_alias=True)
        assert "identifierValue" not in data
        assert "identifierLast4" not in data
        assert data["displayName"] == "Synthetic Person (demo)"

    def test_identity_evidence_read_uses_last4_only(self):
        schema = IdentityEvidenceReadSchema(
            id="ide_demo",
            party_id="pty_demo",
            evidence_kind="nic",
            identifier_last4="5678",
            issued_on=None,
            expires_on=None,
            issuing_authority=None,
            document_id=None,
            document_version_id=None,
            evidence_span=None,
            state="recorded",
            supersedes_evidence_id=None,
            version=1,
        )
        data = schema.model_dump(by_alias=True)
        assert data["identifierLast4"] == "5678"
        assert "identifierValue" not in data

    def test_party_list_item_minimal_surface(self):
        item = PartyListItemSchema(
            id="pty_demo",
            display_name="Synthetic Person (demo)",
            party_kind="natural-person",
            screening_status="not-run",
            version=1,
        )
        dumped = item.model_dump(by_alias=True)
        assert set(dumped.keys()) == {
            "id",
            "displayName",
            "partyKind",
            "screeningStatus",
            "version",
        }
