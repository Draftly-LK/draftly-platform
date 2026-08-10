"""Notarial register port definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.modules.auth.ports import AuditPort
from src.modules.notarial_register.domain.models import (
    ApprovedInstrumentSnapshot,
    Attestation,
    MonthlyReturnPeriod,
    ProtocolRecord,
    RegisterEntry,
    RegisterEntryFilters,
    RegistrationSubmission,
)


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class MatterAccessPort(Protocol):
    async def is_member(self, user_id: str, matter_id: str) -> bool: ...


class ApprovedInstrumentPort(Protocol):
    """Resolves approved export metadata for attestation pinning."""

    async def load_approved_export(
        self,
        *,
        user_id: str,
        matter_id: str,
        export_id: str,
        use_fixture: bool,
    ) -> ApprovedInstrumentSnapshot | None: ...


class AttestationRepository(Protocol):
    async def create(self, attestation: Attestation) -> Attestation: ...

    async def get(self, user_id: str, attestation_id: str) -> Attestation | None: ...

    async def get_by_matter(
        self, user_id: str, matter_id: str, attestation_id: str
    ) -> Attestation | None: ...

    async def update(self, attestation: Attestation) -> Attestation: ...


class RegisterRepository(Protocol):
    async def allocate_serial(self, *, notary_user_id: str, register_year: int) -> int: ...

    async def create_entry(self, entry: RegisterEntry) -> RegisterEntry: ...

    async def list_entries(
        self, user_id: str, filters: RegisterEntryFilters
    ) -> tuple[list[RegisterEntry], int]: ...

    async def get_entry_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegisterEntry | None: ...

    async def update_entry(self, entry: RegisterEntry) -> RegisterEntry: ...


class ProtocolRepository(Protocol):
    async def create(self, record: ProtocolRecord) -> ProtocolRecord: ...

    async def list_for_attestation(self, attestation_id: str) -> list[ProtocolRecord]: ...


class RegistrationSubmissionRepository(Protocol):
    async def create(self, submission: RegistrationSubmission) -> RegistrationSubmission: ...

    async def get_for_attestation(
        self, user_id: str, attestation_id: str
    ) -> RegistrationSubmission | None: ...

    async def update(self, submission: RegistrationSubmission) -> RegistrationSubmission: ...


class MonthlyReturnRepository(Protocol):
    async def get(self, user_id: str, period_id: str) -> MonthlyReturnPeriod | None: ...

    async def list_for_notary(
        self, user_id: str, notary_user_id: str
    ) -> list[MonthlyReturnPeriod]: ...

    async def upsert_open_period(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod: ...

    async def update(self, period: MonthlyReturnPeriod) -> MonthlyReturnPeriod: ...

    async def find_open_for_month(
        self, user_id: str, notary_user_id: str, period_start: datetime
    ) -> MonthlyReturnPeriod | None: ...


class EventPort(Protocol):
    async def publish(
        self,
        *,
        user_id: str,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, str | int | bool | list[str] | None],
        correlation_id: str,
    ) -> None: ...


__all__ = [
    "ApprovedInstrumentPort",
    "AttestationRepository",
    "AuditPort",
    "ClockPort",
    "EventPort",
    "MatterAccessPort",
    "MonthlyReturnRepository",
    "ProtocolRepository",
    "RegisterRepository",
    "RegistrationSubmissionRepository",
]
