"""SQL repositories and test adapters for notarial register."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.notarial_register.domain.models import (
    ApprovedInstrumentSnapshot,
    Attestation,
    AttestationCondition,
    AttestationState,
    InstrumentKind,
    MonthlyReturnPeriod,
    MonthlyReturnState,
    PartyRef,
    ProtocolCopyKind,
    ProtocolRecord,
    ProtocolState,
    RegisterEntry,
    RegisterEntryFilters,
    RegisterEntryState,
    RegistrationRegime,
    RegistrationSubmission,
    RegistrationSubmissionState,
    SourceKind,
)
from src.modules.notarial_register.infrastructure.orm import (
    AttestationRow,
    MonthlyReturnPeriodRow,
    OutboxEventRow,
    ProtocolRecordRow,
    RegisterEntryRow,
    RegisterSerialCounterRow,
    RegistrationSubmissionRow,
)
from src.modules.notarial_register.ports import ApprovedInstrumentPort


def _party_refs_to_json(parties: list[PartyRef]) -> str:
    return json.dumps(
        [
            {
                "party_id": p.party_id,
                "capacity": p.capacity,
                "evidence_ref": p.evidence_ref,
            }
            for p in parties
        ]
    )


def _party_refs_from_json(raw: str) -> list[PartyRef]:
    data = json.loads(raw)
    return [
        PartyRef(
            party_id=item["party_id"],
            capacity=item.get("capacity"),
            evidence_ref=item.get("evidence_ref"),
        )
        for item in data
    ]


def _conditions_to_json(conditions: list[AttestationCondition]) -> str:
    return json.dumps([c.value for c in conditions])


def _conditions_from_json(raw: str) -> list[AttestationCondition]:
    return [AttestationCondition(v) for v in json.loads(raw)]


def _attestation_from_row(row: AttestationRow) -> Attestation:
    return Attestation(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        instrument_kind=InstrumentKind(row.instrument_kind),
        registration_regime=RegistrationRegime(row.registration_regime),
        source_kind=SourceKind(row.source_kind),
        export_id=row.export_id,
        draft_version_id=row.draft_version_id,
        content_hash=row.content_hash,
        attestation_clause_definition_id=row.attestation_clause_definition_id,
        attestation_clause_version=row.attestation_clause_version,
        attestation_conditions=_conditions_from_json(row.attestation_conditions_json),
        notary_user_id=row.notary_user_id,
        practising_jurisdiction_id=row.practising_jurisdiction_id,
        registration_jurisdiction_id=row.registration_jurisdiction_id,
        instrument_language=row.instrument_language,
        attested_at=row.attested_at,
        place_of_execution=row.place_of_execution,
        executants=_party_refs_from_json(row.executants_json),
        witnesses=_party_refs_from_json(row.witnesses_json),
        consideration_recorded=row.consideration_recorded,
        state=AttestationState(row.state),
        version=row.version,
        external_reason=row.external_reason,
    )


def _attestation_to_row(attestation: Attestation) -> AttestationRow:
    return AttestationRow(
        id=attestation.id,
        user_id=attestation.user_id,
        matter_id=attestation.matter_id,
        instrument_kind=attestation.instrument_kind.value,
        registration_regime=attestation.registration_regime.value,
        source_kind=attestation.source_kind.value,
        export_id=attestation.export_id,
        draft_version_id=attestation.draft_version_id,
        content_hash=attestation.content_hash,
        attestation_clause_definition_id=attestation.attestation_clause_definition_id,
        attestation_clause_version=attestation.attestation_clause_version,
        attestation_conditions_json=_conditions_to_json(attestation.attestation_conditions),
        notary_user_id=attestation.notary_user_id,
        practising_jurisdiction_id=attestation.practising_jurisdiction_id,
        registration_jurisdiction_id=attestation.registration_jurisdiction_id,
        instrument_language=attestation.instrument_language,
        attested_at=attestation.attested_at,
        place_of_execution=attestation.place_of_execution,
        executants_json=_party_refs_to_json(attestation.executants),
        witnesses_json=_party_refs_to_json(attestation.witnesses),
        consideration_recorded=attestation.consideration_recorded,
        external_reason=attestation.external_reason,
        state=attestation.state.value,
        version=attestation.version,
    )


class SqlAttestationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, attestation: Attestation) -> Attestation:
        self._session.add(_attestation_to_row(attestation))
        await self._session.flush()
        return attestation

    async def get(self, user_id: str, attestation_id: str) -> Attestation | None:
        result = await self._session.execute(
            select(AttestationRow).where(
                AttestationRow.id == attestation_id,
                AttestationRow.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _attestation_from_row(row) if row else None

    async def get_by_matter(
        self, user_id: str, matter_id: str, attestation_id: str
    ) -> Attestation | None:
        result = await self._session.execute(
            select(AttestationRow).where(
                AttestationRow.id == attestation_id,
                AttestationRow.user_id == user_id,
                AttestationRow.matter_id == matter_id,
            )
        )
        row = result.scalar_one_or_none()
        return _attestation_from_row(row) if row else None

    async def update(self, attestation: Attestation) -> Attestation:
        result = await self._session.execute(
            select(AttestationRow).where(AttestationRow.id == attestation.id)
        )
        row = result.scalar_one()
        row.state = attestation.state.value
        row.version = attestation.version
        await self._session.flush()
        return attestation


class SqlRegisterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate_serial(self, *, notary_user_id: str, register_year: int) -> int:
        result = await self._session.execute(
            select(RegisterSerialCounterRow)
            .where(
                RegisterSerialCounterRow.notary_user_id == notary_user_id,
                RegisterSerialCounterRow.register_year == register_year,
            )
            .with_for_update()
        )
        counter = result.scalar_one_or_none()
        if counter is None:
            counter = RegisterSerialCounterRow(
                id=f"rsc_{uuid.uuid4().hex}",
                notary_user_id=notary_user_id,
                register_year=register_year,
                last_serial=0,
            )
            self._session.add(counter)
            await self._session.flush()
        counter.last_serial += 1
        await self._session.flush()
        return counter.last_serial

    async def create_entry(self, entry: RegisterEntry) -> RegisterEntry:
        self._session.add(
            RegisterEntryRow(
                id=entry.id,
                user_id=entry.user_id,
                notary_user_id=entry.notary_user_id,
                register_year=entry.register_year,
                serial_number=entry.serial_number,
                attestation_id=entry.attestation_id,
                entry_date=entry.entry_date,
                instrument_kind=entry.instrument_kind.value,
                party_summary_ref=entry.party_summary_ref,
                consideration_ref=entry.consideration_ref,
                folio_ref=entry.folio_ref,
                state=entry.state.value,
                cancellation_reason=entry.cancellation_reason,
                created_at=entry.created_at,
            )
        )
        await self._session.flush()
        return entry

    async def list_entries(
        self, user_id: str, filters: RegisterEntryFilters
    ) -> tuple[list[RegisterEntry], int]:
        query = select(RegisterEntryRow).where(RegisterEntryRow.user_id == user_id)
        if filters.notary_user_id:
            query = query.where(RegisterEntryRow.notary_user_id == filters.notary_user_id)
        if filters.register_year is not None:
            query = query.where(RegisterEntryRow.register_year == filters.register_year)

        count_result = await self._session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = int(count_result.scalar_one())

        result = await self._session.execute(
            query.order_by(RegisterEntryRow.serial_number.asc())
            .offset(filters.offset)
            .limit(filters.limit)
        )
        rows = result.scalars().all()
        items = [
            RegisterEntry(
                id=row.id,
                user_id=row.user_id,
                notary_user_id=row.notary_user_id,
                register_year=row.register_year,
                serial_number=row.serial_number,
                attestation_id=row.attestation_id,
                entry_date=row.entry_date,
                instrument_kind=InstrumentKind(row.instrument_kind),
                party_summary_ref=row.party_summary_ref,
                consideration_ref=row.consideration_ref,
                folio_ref=row.folio_ref,
                state=RegisterEntryState(row.state),
                cancellation_reason=row.cancellation_reason,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return items, total

    async def get_entry_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegisterEntry | None:
        result = await self._session.execute(
            select(RegisterEntryRow).where(
                RegisterEntryRow.user_id == user_id,
                RegisterEntryRow.attestation_id == attestation_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return RegisterEntry(
            id=row.id,
            user_id=row.user_id,
            notary_user_id=row.notary_user_id,
            register_year=row.register_year,
            serial_number=row.serial_number,
            attestation_id=row.attestation_id,
            entry_date=row.entry_date,
            instrument_kind=InstrumentKind(row.instrument_kind),
            party_summary_ref=row.party_summary_ref,
            consideration_ref=row.consideration_ref,
            folio_ref=row.folio_ref,
            state=RegisterEntryState(row.state),
            cancellation_reason=row.cancellation_reason,
            created_at=row.created_at,
        )

    async def update_entry(self, entry: RegisterEntry) -> RegisterEntry:
        result = await self._session.execute(
            select(RegisterEntryRow).where(RegisterEntryRow.id == entry.id)
        )
        row = result.scalar_one()
        row.state = entry.state.value
        row.cancellation_reason = entry.cancellation_reason
        await self._session.flush()
        return entry


class SqlProtocolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: ProtocolRecord) -> ProtocolRecord:
        self._session.add(
            ProtocolRecordRow(
                id=record.id,
                attestation_id=record.attestation_id,
                copy_kind=record.copy_kind.value,
                storage_ref=record.storage_ref,
                physical_location=record.physical_location,
                custodian_user_id=record.custodian_user_id,
                issued_to=record.issued_to,
                issued_at=record.issued_at,
                returned_at=record.returned_at,
                retention_class=record.retention_class,
                state=record.state.value,
            )
        )
        await self._session.flush()
        return record

    async def list_for_attestation(self, attestation_id: str) -> list[ProtocolRecord]:
        result = await self._session.execute(
            select(ProtocolRecordRow).where(ProtocolRecordRow.attestation_id == attestation_id)
        )
        rows = result.scalars().all()
        return [
            ProtocolRecord(
                id=row.id,
                attestation_id=row.attestation_id,
                copy_kind=ProtocolCopyKind(row.copy_kind),
                storage_ref=row.storage_ref,
                physical_location=row.physical_location,
                custodian_user_id=row.custodian_user_id,
                issued_to=row.issued_to,
                issued_at=row.issued_at,
                returned_at=row.returned_at,
                retention_class=row.retention_class,
                state=ProtocolState(row.state),
            )
            for row in rows
        ]


class SqlRegistrationSubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, submission: RegistrationSubmission) -> RegistrationSubmission:
        self._session.add(
            RegistrationSubmissionRow(
                id=submission.id,
                attestation_id=submission.attestation_id,
                user_id=submission.user_id,
                state=submission.state.value,
                registry_id=submission.registry_id,
                submitted_at=submission.submitted_at,
                acknowledged_at=submission.acknowledged_at,
                defect_notes=submission.defect_notes,
                version=submission.version,
            )
        )
        await self._session.flush()
        return submission

    async def get_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegistrationSubmission | None:
        result = await self._session.execute(
            select(RegistrationSubmissionRow).where(
                RegistrationSubmissionRow.user_id == user_id,
                RegistrationSubmissionRow.attestation_id == attestation_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return RegistrationSubmission(
            id=row.id,
            attestation_id=row.attestation_id,
            user_id=row.user_id,
            state=RegistrationSubmissionState(row.state),
            registry_id=row.registry_id,
            submitted_at=row.submitted_at,
            acknowledged_at=row.acknowledged_at,
            defect_notes=row.defect_notes,
            version=row.version,
        )

    async def update(self, submission: RegistrationSubmission) -> RegistrationSubmission:
        result = await self._session.execute(
            select(RegistrationSubmissionRow).where(RegistrationSubmissionRow.id == submission.id)
        )
        row = result.scalar_one()
        row.state = submission.state.value
        row.registry_id = submission.registry_id
        row.submitted_at = submission.submitted_at
        row.acknowledged_at = submission.acknowledged_at
        row.defect_notes = submission.defect_notes
        row.version = submission.version
        await self._session.flush()
        return submission


def _period_from_row(row: MonthlyReturnPeriodRow) -> MonthlyReturnPeriod:
    return MonthlyReturnPeriod(
        id=row.id,
        user_id=row.user_id,
        notary_user_id=row.notary_user_id,
        period_start=row.period_start,
        period_end=row.period_end,
        instrument_ids=json.loads(row.instrument_ids_json),
        is_nil_return=row.is_nil_return,
        components=json.loads(row.components_json),
        component_states=json.loads(row.component_states_json),
        certified_by=row.certified_by,
        certified_at=row.certified_at,
        submitted_at=row.submitted_at,
        acknowledged_at=row.acknowledged_at,
        state=MonthlyReturnState(row.state),
        version=row.version,
    )


class SqlMonthlyReturnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, period_id: str) -> MonthlyReturnPeriod | None:
        result = await self._session.execute(
            select(MonthlyReturnPeriodRow).where(
                MonthlyReturnPeriodRow.id == period_id,
                MonthlyReturnPeriodRow.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _period_from_row(row) if row else None

    async def list_for_notary(self, user_id: str, notary_user_id: str) -> list[MonthlyReturnPeriod]:
        result = await self._session.execute(
            select(MonthlyReturnPeriodRow)
            .where(
                MonthlyReturnPeriodRow.user_id == user_id,
                MonthlyReturnPeriodRow.notary_user_id == notary_user_id,
            )
            .order_by(MonthlyReturnPeriodRow.period_start.desc())
        )
        return [_period_from_row(row) for row in result.scalars().all()]

    async def upsert_open_period(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod:
        self._session.add(
            MonthlyReturnPeriodRow(
                id=period.id,
                user_id=period.user_id,
                notary_user_id=period.notary_user_id,
                period_start=period.period_start,
                period_end=period.period_end,
                instrument_ids_json=json.dumps(period.instrument_ids),
                is_nil_return=period.is_nil_return,
                components_json=json.dumps(period.components),
                component_states_json=json.dumps(period.component_states),
                certified_by=period.certified_by,
                certified_at=period.certified_at,
                submitted_at=period.submitted_at,
                acknowledged_at=period.acknowledged_at,
                state=period.state.value,
                version=period.version,
            )
        )
        await self._session.flush()
        return period

    async def update(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod:
        result = await self._session.execute(
            select(MonthlyReturnPeriodRow).where(MonthlyReturnPeriodRow.id == period.id)
        )
        row = result.scalar_one()
        row.instrument_ids_json = json.dumps(period.instrument_ids)
        row.is_nil_return = period.is_nil_return
        row.components_json = json.dumps(period.components)
        row.component_states_json = json.dumps(period.component_states)
        row.certified_by = period.certified_by
        row.certified_at = period.certified_at
        row.submitted_at = period.submitted_at
        row.acknowledged_at = period.acknowledged_at
        row.state = period.state.value
        row.version = period.version
        await self._session.flush()
        return period

    async def find_open_for_month(
        self, user_id: str, notary_user_id: str, period_start: datetime
    ) -> MonthlyReturnPeriod | None:
        result = await self._session.execute(
            select(MonthlyReturnPeriodRow).where(
                MonthlyReturnPeriodRow.user_id == user_id,
                MonthlyReturnPeriodRow.notary_user_id == notary_user_id,
                MonthlyReturnPeriodRow.period_start == period_start.date(),
                MonthlyReturnPeriodRow.state == MonthlyReturnState.OPEN.value,
            )
        )
        row = result.scalar_one_or_none()
        return _period_from_row(row) if row else None


class SqlEventPort:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(
        self,
        *,
        user_id: str,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, str | int | bool | list[str] | None],
        correlation_id: str,
    ) -> None:
        self._session.add(
            OutboxEventRow(
                id=f"evt_{uuid.uuid4().hex}",
                user_id=user_id,
                event_type=event_type,
                aggregate_id=aggregate_id,
                payload_json=json.dumps(payload),
                correlation_id=correlation_id,
            )
        )
        await self._session.flush()


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class StubApprovedInstrumentAdapter(ApprovedInstrumentPort):
    """Returns a synthetic approved export only when use_fixture is True."""

    async def load_approved_export(
        self,
        *,
        user_id: str,
        matter_id: str,
        export_id: str,
        use_fixture: bool,
    ) -> ApprovedInstrumentSnapshot | None:
        if not use_fixture:
            return None
        return ApprovedInstrumentSnapshot(
            export_id=export_id,
            draft_version_id="drv_demo_approved_v1",
            content_hash="sha256:synthetic-demo-hash",
            matter_id=matter_id,
        )


class StubMatterAccessAdapter:
    def __init__(self, memberships: set[tuple[str, str]] | None = None) -> None:
        self._memberships = memberships

    async def is_member(self, user_id: str, matter_id: str) -> bool:
        if self._memberships is None:
            return True
        return (user_id, matter_id) in self._memberships


class InMemoryRegisterRepository:
    """Gapless serial allocator for unit tests (per-notary, per-year)."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, int], int] = {}
        self._entries: list[RegisterEntry] = []
        self._lock = asyncio.Lock()

    async def allocate_serial(self, *, notary_user_id: str, register_year: int) -> int:
        async with self._lock:
            key = (notary_user_id, register_year)
            next_serial = self._counters.get(key, 0) + 1
            self._counters[key] = next_serial
            return next_serial

    async def create_entry(self, entry: RegisterEntry) -> RegisterEntry:
        self._entries.append(entry)
        return entry

    async def list_entries(
        self, user_id: str, filters: RegisterEntryFilters
    ) -> tuple[list[RegisterEntry], int]:
        items = [e for e in self._entries if e.user_id == user_id]
        if filters.notary_user_id:
            items = [e for e in items if e.notary_user_id == filters.notary_user_id]
        if filters.register_year is not None:
            items = [e for e in items if e.register_year == filters.register_year]
        total = len(items)
        return items[filters.offset : filters.offset + filters.limit], total

    async def get_entry_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegisterEntry | None:
        for entry in self._entries:
            if entry.user_id == user_id and entry.attestation_id == attestation_id:
                return entry
        return None

    async def update_entry(self, entry: RegisterEntry) -> RegisterEntry:
        return entry
