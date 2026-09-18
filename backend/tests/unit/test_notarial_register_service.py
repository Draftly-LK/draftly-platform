"""Unit tests for NotarialRegisterService."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from src.modules.auth.domain.models import Role
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.modules.notarial_register.domain.errors import (
    RegisterAccessDeniedError,
    UnapprovedInstrumentError,
)
from src.modules.notarial_register.domain.models import (
    Attestation,
    AttestationCondition,
    AttestationState,
    CreateAttestationInput,
    InstrumentKind,
    MonthlyReturnPeriod,
    MonthlyReturnState,
    ProtocolRecord,
    RegisterEntryFilters,
    RegistrationRegime,
    RegistrationSubmission,
    SourceKind,
)
from src.modules.notarial_register.infrastructure.repository import (
    InMemoryRegisterRepository,
    StubApprovedInstrumentAdapter,
    StubMatterAccessAdapter,
    SystemClock,
)
from src.platform.request_context import RequestContext
from tests.factories.audit import FakeAudit as FakeAuditPort


class FakeAttestationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Attestation] = {}

    async def create(self, attestation: Attestation) -> Attestation:
        self.items[attestation.id] = attestation
        return attestation

    async def get(self, user_id: str, attestation_id: str) -> Attestation | None:
        attestation = self.items.get(attestation_id)
        if attestation is None or attestation.user_id != user_id:
            return None
        return attestation

    async def get_by_matter(
        self, user_id: str, matter_id: str, attestation_id: str
    ) -> Attestation | None:
        attestation = await self.get(user_id, attestation_id)
        if attestation is None or attestation.matter_id != matter_id:
            return None
        return attestation

    async def update(self, attestation: Attestation) -> Attestation:
        self.items[attestation.id] = attestation
        return attestation


class FakeProtocolRepository:
    def __init__(self) -> None:
        self.items: list[ProtocolRecord] = []

    async def create(self, record: ProtocolRecord) -> ProtocolRecord:
        self.items.append(record)
        return record

    async def list_for_attestation(self, attestation_id: str) -> list[ProtocolRecord]:
        return [r for r in self.items if r.attestation_id == attestation_id]


class FakeRegistrationRepository:
    def __init__(self) -> None:
        self.items: dict[str, RegistrationSubmission] = {}

    async def create(self, submission: RegistrationSubmission) -> RegistrationSubmission:
        self.items[submission.attestation_id] = submission
        return submission

    async def get_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegistrationSubmission | None:
        submission = self.items.get(attestation_id)
        if submission is None or submission.user_id != user_id:
            return None
        return submission

    async def update(self, submission: RegistrationSubmission) -> RegistrationSubmission:
        self.items[submission.attestation_id] = submission
        return submission


class FakeMonthlyReturnRepository:
    def __init__(self) -> None:
        self.periods: dict[str, MonthlyReturnPeriod] = {}

    async def get(self, user_id: str, period_id: str) -> MonthlyReturnPeriod | None:
        period = self.periods.get(period_id)
        if period is None or period.user_id != user_id:
            return None
        return period

    async def list_for_notary(self, user_id: str, notary_user_id: str) -> list[MonthlyReturnPeriod]:
        return [
            p
            for p in self.periods.values()
            if p.user_id == user_id and p.notary_user_id == notary_user_id
        ]

    async def upsert_open_period(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod:
        self.periods[period.id] = period
        return period

    async def update(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod:
        self.periods[period.id] = period
        return period

    async def find_open_for_month(
        self, user_id: str, notary_user_id: str, period_start: datetime
    ) -> MonthlyReturnPeriod | None:
        for period in self.periods.values():
            if (
                period.user_id == user_id
                and period.notary_user_id == notary_user_id
                and period.period_start == period_start.date()
                and period.state == MonthlyReturnState.OPEN
            ):
                return period
        return None


class FakeEventPort:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(
        self,
        *,
        user_id: str,
        event_type: str,
        aggregate_id: str,
        payload: dict,
        correlation_id: str,
    ) -> None:
        _ = user_id, aggregate_id, correlation_id
        self.events.append((event_type, payload))


def make_ctx(actor_id: str = "usr_notary") -> RequestContext:
    return RequestContext(
        actor_id=actor_id,
        account_role=Role.APPROVER,
        correlation_id="corr_test",
    )


def make_attestation_input(**overrides: object) -> CreateAttestationInput:
    base = CreateAttestationInput(
        matter_id="mat_demo_001",
        instrument_kind=InstrumentKind.TRANSFER,
        registration_regime=RegistrationRegime.DEED,
        source_kind=SourceKind.EXPORT,
        export_id="exp_demo_001",
        attestation_clause_definition_id="nf-e-attest",
        attestation_clause_version="1",
        attestation_conditions=[AttestationCondition.READ],
        practising_jurisdiction_id="jur_colombo",
        registration_jurisdiction_id="jur_colombo",
        instrument_language="en",
        attested_at=datetime(2026, 3, 15, 10, 30, tzinfo=UTC),
        place_of_execution="Colombo",
        executants=[],
        witnesses=[],
        consideration_recorded=True,
        party_summary_ref="party-summary:ref_demo",
        approved_instrument_fixture=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def build_service(
    *,
    register_repo: InMemoryRegisterRepository | None = None,
    matter_access: StubMatterAccessAdapter | None = None,
) -> tuple[NotarialRegisterService, FakeEventPort, InMemoryRegisterRepository]:
    register = register_repo or InMemoryRegisterRepository()
    events = FakeEventPort()
    service = NotarialRegisterService(
        attestation_repo=FakeAttestationRepository(),
        register_repo=register,
        protocol_repo=FakeProtocolRepository(),
        registration_repo=FakeRegistrationRepository(),
        monthly_return_repo=FakeMonthlyReturnRepository(),
        approved_instrument_port=StubApprovedInstrumentAdapter(),
        matter_access=matter_access or StubMatterAccessAdapter(),
        audit_port=FakeAuditPort(),
        event_port=events,
        clock=SystemClock(),
    )
    return service, events, register


@pytest.mark.asyncio
async def test_register_serials_are_gapless_per_notary_and_year() -> None:
    register = InMemoryRegisterRepository()
    serial_a = await register.allocate_serial(notary_user_id="usr_a", register_year=2026)
    serial_b = await register.allocate_serial(notary_user_id="usr_a", register_year=2026)
    serial_other_year = await register.allocate_serial(notary_user_id="usr_a", register_year=2027)
    serial_other_notary = await register.allocate_serial(notary_user_id="usr_b", register_year=2026)
    assert (serial_a, serial_b, serial_other_year, serial_other_notary) == (1, 2, 1, 1)


@pytest.mark.asyncio
async def test_attestation_refuses_unapproved_export_without_fixture_flag() -> None:
    service, _, _ = build_service()
    ctx = make_ctx()
    input_data = make_attestation_input(approved_instrument_fixture=False)
    with pytest.raises(UnapprovedInstrumentError):
        await service.record_attestation(ctx, "mat_demo_001", input_data)


@pytest.mark.asyncio
async def test_record_attestation_emits_instrument_attested_event() -> None:
    service, events, register = build_service()
    ctx = make_ctx()
    attestation = await service.record_attestation(ctx, "mat_demo_001", make_attestation_input())
    assert attestation.state == AttestationState.ATTESTED
    assert events.events[0][0] == "instrument.attested"
    payload = events.events[0][1]
    assert payload["matterId"] == "mat_demo_001"
    assert payload["practisingJurisdictionId"] == "jur_colombo"
    entries, _ = await register.list_entries(ctx.actor_id, RegisterEntryFilters(register_year=2026))
    assert len(entries) == 1
    assert entries[0].serial_number == 1


@pytest.mark.asyncio
async def test_cross_user_register_list_denied() -> None:
    service, _, _ = build_service()
    ctx = make_ctx("usr_notary")
    with pytest.raises(RegisterAccessDeniedError):
        await service.list_register_entries(
            ctx,
            RegisterEntryFilters(notary_user_id="usr_other"),
        )


@pytest.mark.asyncio
async def test_concurrent_serial_allocation_stays_gapless() -> None:
    register = InMemoryRegisterRepository()

    async def allocate() -> int:
        return await register.allocate_serial(notary_user_id="usr_a", register_year=2026)

    results = await asyncio.gather(*(allocate() for _ in range(20)))
    assert sorted(results) == list(range(1, 21))
