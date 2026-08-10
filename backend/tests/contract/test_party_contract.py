"""Contract tests for party_service — party-service.md §11 "Contract".

Party list and detail schemas return `identifierLast4` and never
`identifierValue`; the screening event payload contains no name, list entry, or
narrative; every published event matches the registry in events.md §5.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from src.modules.auth.domain.models import Role
from src.modules.party.api.schemas import (
    IdentityEvidenceReadSchema,
    MatterPartyReadSchema,
    PagedResponse,
    PageSchema,
    PartyListItemSchema,
    PartyReadSchema,
)
from src.modules.party.domain.models import ScreeningMatchDetail
from src.modules.party.ports import (
    CreatePartyInput,
    RecordIdentityEvidenceInput,
    RecordScreeningInput,
)
from src.platform.privacy import find_private_content
from tests.fixtures.party_fakes import (
    ACTOR_A,
    FakeEvents,
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

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_EVENTS_DOC = _BACKEND_ROOT / "docs" / "events.md"
_SERVICES_YAML = _BACKEND_ROOT / "contracts" / "services.yaml"
_FIXTURES = Path(__file__).parent / "fixtures" / "party"


def _registry_payload_fields() -> dict[str, set[str]]:
    """Parse the party rows out of the events.md §5 registry table."""
    rows: dict[str, set[str]] = {}
    for line in _EVENTS_DOC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*`(party\.[a-z-]+)`\s*\|([^|]*)\|", line)
        if not match:
            continue
        fields = set(re.findall(r"`([A-Za-z]+)`", match.group(2)))
        rows[match.group(1)] = fields
    return rows


class TestReadSchemas:
    def test_party_read_never_carries_an_identifier(self):
        now = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
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
            screening_status=None,
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
        assert data["screeningStatus"] is None

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

    def test_party_list_item_surface_is_minimal(self):
        item = PartyListItemSchema(
            id="pty_demo",
            display_name="Synthetic Person (demo)",
            party_kind="natural-person",
            screening_status=None,
            version=1,
        )
        assert set(item.model_dump(by_alias=True)) == {
            "id",
            "displayName",
            "partyKind",
            "screeningStatus",
            "version",
        }

    def test_matter_party_read_carries_no_compliance_signal(self):
        item = MatterPartyReadSchema(
            id="pty_demo",
            display_name="Synthetic Person (demo)",
            party_kind="natural-person",
        )
        assert "screeningStatus" not in item.model_dump(by_alias=True)

    def test_closed_enums_refuse_an_unknown_value(self):
        with pytest.raises(ValueError):
            PartyListItemSchema(
                id="pty_demo",
                display_name="Synthetic Person (demo)",
                party_kind="not-a-party-kind",
                screening_status=None,
                version=1,
            )

    def test_the_list_envelope_matches_api_conventions(self):
        page = PagedResponse[PartyListItemSchema](
            items=[],
            page=PageSchema(next_cursor=None, has_more=False, limit=50),
        )
        dumped = page.model_dump(by_alias=True)
        assert set(dumped) == {"items", "page"}
        assert set(dumped["page"]) == {"nextCursor", "hasMore", "limit"}


class TestEventContracts:
    async def _publish_all(self) -> FakeEvents:
        parties = FakePartyRepo()
        events = FakeEvents()
        service = build_service(party_repo=parties, events=events)
        created = await service.create_party(ctx(), CreatePartyInput(**SYNTHETIC_PARTY_A))
        await service.record_identity_evidence(
            ctx(),
            created.party.id,
            RecordIdentityEvidenceInput(
                evidence_kind="nic",
                identifier_value=SYNTHETIC_NIC,
                issued_on=None,
                expires_on=datetime(2030, 1, 1, tzinfo=UTC).date(),
                issuing_authority=None,
                document_id=SYNTHETIC_DOCUMENT_ID,
                document_version_id=SYNTHETIC_DOCUMENT_VERSION_ID,
                evidence_span=dict(SYNTHETIC_EVIDENCE_SPAN),
                supersedes_evidence_id=None,
            ),
        )
        await service.record_screening(
            ctx(role=Role.ADMINISTRATOR),
            created.party.id,
            RecordScreeningInput(
                list_version="demo-v1",
                provider_ref="manual",
                outcome="confirmed-match",
                match_count=2,
                match_detail=ScreeningMatchDetail(
                    screening_result_id="",
                    provider_payload={"demo": True},
                    match_narrative="Synthetic narrative for tests only.",
                    list_entry_ref="SYN-LIST-1",
                ),
            ),
        )
        return events

    async def test_every_published_event_is_in_the_registry(self):
        events = await self._publish_all()
        registry = _registry_payload_fields()
        published = {e.name for e in events.published}
        assert published == {
            "party.created",
            "party.identity-evidence-recorded",
            "party.identity-document-expiry-recorded",
            "party.screening-completed",
            "party.designated-person-confirmed",
        }
        assert published <= set(registry)

    async def test_payload_fields_match_the_registry(self):
        events = await self._publish_all()
        registry = _registry_payload_fields()
        for event in events.published:
            assert set(event.payload) == registry[event.name], event.name

    async def test_the_published_set_matches_services_yaml(self):
        events = await self._publish_all()
        registry = yaml.safe_load(_SERVICES_YAML.read_text(encoding="utf-8"))
        services = registry["services"] if isinstance(registry, dict) else registry
        row = next(s for s in services if s["name"] == "party_service")
        assert {e.name for e in events.published} == set(row["publishes"])

    async def test_no_event_payload_carries_private_content(self):
        events = await self._publish_all()
        for event in events.published:
            assert find_private_content(event.payload) == [], event.name

    async def test_the_screening_event_carries_no_name_entry_or_narrative(self):
        events = await self._publish_all()
        screening = events.named("party.screening-completed")[0]
        confirmed = events.named("party.designated-person-confirmed")[0]
        assert set(screening.payload) == {"partyId", "outcome", "confidentialityLevel"}
        assert set(confirmed.payload) == {"partyId", "confidentialityLevel"}
        for event in (screening, confirmed):
            serialised = json.dumps(event.payload)
            assert "Silva" not in serialised
            assert "SYN-LIST-1" not in serialised
            assert "narrative" not in serialised.lower()
            assert SYNTHETIC_NIC not in serialised


class TestContractFixtures:
    """The example payloads frontend work is allowed to reference (L1)."""

    def test_fixtures_exist_and_are_synthetic(self):
        files = sorted(_FIXTURES.glob("*.json"))
        assert files, "party contract fixtures are missing"
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert (
                "synthetic" in json.dumps(payload).lower() or "demo" in json.dumps(payload).lower()
            )

    def test_the_party_detail_fixture_validates(self):
        payload = json.loads((_FIXTURES / "party-detail.json").read_text(encoding="utf-8"))
        schema = PartyReadSchema.model_validate(payload)
        assert schema.screening_status is None

    def test_the_party_list_fixture_validates(self):
        payload = json.loads((_FIXTURES / "party-list.json").read_text(encoding="utf-8"))
        page = PagedResponse[PartyListItemSchema].model_validate(payload)
        assert page.page.limit <= 100

    def test_the_evidence_fixture_carries_no_identifier(self):
        raw = (_FIXTURES / "identity-evidence.json").read_text(encoding="utf-8")
        payload = json.loads(raw)
        IdentityEvidenceReadSchema.model_validate(payload)
        assert "identifierValue" not in raw
        assert find_private_content(payload) == []


def test_actor_constant_is_synthetic():
    assert ACTOR_A.startswith("usr_synthetic")


def test_synthetic_party_helper_is_deterministic():
    first = synthetic_party(ACTOR_A, "pty_x")
    second = synthetic_party(ACTOR_A, "pty_x")
    assert first.created_at == second.created_at
