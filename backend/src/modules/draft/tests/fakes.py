"""In-memory doubles and synthetic fixtures for the drafting module's tests.

No database. The repository double keeps the two behaviours the real one has
that the tests depend on: `update_form` is optimistic, and every accessor hands
back a copy rather than the caller's own object, so a test cannot pass by
mutating something the service still holds.

Every value in `CONFIRMED_TRANSFER` is invented. No real party, NIC, deed,
parcel, notary, or registry reference appears anywhere in this module.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from src.modules.auth.ports import AuditEventInput
from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import FactStatus
from src.modules.draft.domain.errors import GeneratedFormStaleError
from src.modules.draft.domain.models import FactCandidate, GeneratedForm, GeneratedFormField
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary

USER_ID = "usr_synthetic"
MATTER_ID = "mat_synthetic"
TRANSFER_SUBTYPE_ID = "lk.rta.instrument.transfer_sale"
FORM_08_TEMPLATE_ID = "rta.reg.2022.form.08"
TIRE_31_TEMPLATE_ID = "rta.ops.tire.31"

#: Fixed so a hash assertion does not depend on the day the suite runs.
NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)

#: Every fact type Gazette Form 8 binds, except the attestation date — §9.3
#: never pre-certifies the attestation act, so confirming one would not populate
#: the field and the fixture does not pretend otherwise.
CONFIRMED_TRANSFER: dict[str, Any] = {
    "rta.parcel.district": "Synthetic District",
    "rta.parcel.ds_division": "Synthetic DS Division",
    "rta.parcel.gn_division": "Synthetic GN Division",
    "rta.parcel.cadastral_map_number": "SYN-000000",
    "rta.parcel.block_number": "01",
    "rta.parcel.sheet_number": "02",
    "rta.parcel.parcel_number": "0003",
    "rta.parcel.extent": "0.0500 ha",
    "rta.parcel.extent_subject_to_transaction": "0.0500 ha",
    "rta.title.place_of_registration": "Synthetic Land Registry",
    "rta.title.certificate_no": "SYNTHETIC-TC-0001",
    "rta.title.class": "FIRST_CLASS",
    "rta.party.transferor_name": "Synthetic Seller One",
    "rta.party.transferor_nic": "SYNTHETIC-NIC-A",
    "rta.party.transferor_address": "1 Synthetic Road",
    "rta.party.transferee_name": "Synthetic Buyer Two",
    "rta.party.transferee_nic": "SYNTHETIC-NIC-B",
    "rta.party.transferee_address": "2 Synthetic Road",
    "rta.instrument.consideration": "1000000.00",
    "rta.instrument.consideration_words": "One million synthetic rupees",
    "rta.instrument.notary_name": "Synthetic Notary Three",
    "rta.instrument.notary_code": "SYN-NOT-0003",
}


def fact_tier(
    values: dict[str, Any],
    *,
    conflicted: tuple[str, ...] = (),
    unconfirmed_critical: tuple[str, ...] = (),
    has_search_evidence: bool = True,
    version: int = 1,
    fact_id_suffix: str = "a",
) -> FactTierSummary:
    """One confirmed fact per entry, each with its own evidence reference."""
    return FactTierSummary(
        confirmed={
            fact_type_id: ConfirmedFactValue(
                fact_id=f"fact_{index}_{fact_id_suffix}",
                fact_type_id=fact_type_id,
                value=value,
                version=version,
                evidence_reference_ids=(f"ev_{index}_{fact_id_suffix}",),
            )
            for index, (fact_type_id, value) in enumerate(sorted(values.items()))
        },
        unconfirmed_critical_fact_type_ids=unconfirmed_critical,
        conflicted_fact_type_ids=conflicted,
        has_current_search_evidence=has_search_evidence,
    )


def candidate(
    fact_type_id: str,
    value: Any,
    *,
    fact_id: str = "fact_candidate",
    confidence: float = 0.99,
    clean_ocr: bool = True,
    status: FactStatus = FactStatus.EXTRACTED_CANDIDATE,
    version: int = 1,
) -> FactCandidate:
    return FactCandidate(
        fact_id=fact_id,
        fact_type_id=fact_type_id,
        value=value,
        version=version,
        status=status,
        evidence_reference_ids=(f"ev_{fact_id}",),
        model_reported_confidence=confidence,
        clean_ocr=clean_ocr,
    )


class FakeGeneratedFormRepository:
    """Implements ``GeneratedFormRepository`` in memory."""

    def __init__(self) -> None:
        self.forms: dict[str, GeneratedForm] = {}
        self.fields: dict[str, GeneratedFormField] = {}

    async def create_form(self, form: GeneratedForm) -> GeneratedForm:
        self.forms[form.id] = replace(form)
        return replace(form)

    async def get_form(self, user_id: str, form_id: str) -> GeneratedForm | None:
        form = self.forms.get(form_id)
        if form is None or form.user_id != user_id:
            return None
        return replace(form)

    async def list_forms(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[GeneratedForm], str | None]:
        matching = [
            replace(form)
            for form in sorted(
                self.forms.values(), key=lambda f: (f.created_at, f.id), reverse=True
            )
            if form.user_id == user_id and form.matter_id == matter_id
        ]
        return matching[:limit], None

    async def next_form_version(self, user_id: str, matter_id: str, template_id: str) -> int:
        versions = [
            form.form_version
            for form in self.forms.values()
            if form.user_id == user_id
            and form.matter_id == matter_id
            and form.template_id == template_id
        ]
        return max(versions, default=0) + 1

    async def update_form(self, form: GeneratedForm, expected_version: int) -> GeneratedForm:
        stored = self.forms.get(form.id)
        if stored is None or stored.version != expected_version:
            raise GeneratedFormStaleError(expectedVersion=expected_version)
        saved = replace(form, version=expected_version + 1, updated_at=datetime.now(tz=UTC))
        self.forms[form.id] = saved
        return replace(saved)

    async def create_fields(self, fields: list[GeneratedFormField]) -> list[GeneratedFormField]:
        for form_field in fields:
            self.fields[form_field.id] = replace(form_field)
        return [replace(form_field) for form_field in fields]

    async def list_fields(self, user_id: str, form_id: str) -> list[GeneratedFormField]:
        return [
            replace(form_field)
            for form_field in sorted(self.fields.values(), key=lambda f: (f.order, f.field_id))
            if form_field.user_id == user_id and form_field.generated_form_id == form_id
        ]

    async def update_field(self, form_field: GeneratedFormField) -> GeneratedFormField:
        self.fields[form_field.id] = replace(form_field)
        return replace(form_field)

    def field(self, field_id: str) -> GeneratedFormField:
        matching = [f for f in self.fields.values() if f.field_id == field_id]
        assert matching, f"no stored field '{field_id}'"
        return matching[0]


class FakeFactReader:
    """Implements ``ConfirmedFactReadPort``; the summary is swapped between calls."""

    def __init__(self, summary: FactTierSummary) -> None:
        self.summary = summary

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        return self.summary


class FakeCandidateReader:
    """Implements ``CandidateFactReadPort``."""

    def __init__(self, candidates: tuple[FactCandidate, ...] = ()) -> None:
        self.values = candidates

    async def candidates(self, user_id: str, matter_id: str) -> tuple[FactCandidate, ...]:
        return self.values


class FakeIssueGates:
    """Implements ``IssueGatePort``."""

    def __init__(self, summary: IssueGateSummary | None = None) -> None:
        self.summary = summary or IssueGateSummary()

    async def gates(self, user_id: str, matter_id: str) -> IssueGateSummary:
        return self.summary


class FakeChecklistBlockers:
    """Implements ``ChecklistBlockerPort``."""

    def __init__(self, requirement_ids: tuple[str, ...] = ()) -> None:
        self.requirement_ids = requirement_ids

    async def blocking_requirement_ids(self, *, user_id: str, matter_id: str) -> tuple[str, ...]:
        return self.requirement_ids


class FakeAudit:
    """Implements ``AuditPort``. Records the events for assertion."""

    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)

    def actions(self) -> list[str]:
        return [event.action for event in self.events]
