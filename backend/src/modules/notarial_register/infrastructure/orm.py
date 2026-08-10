"""SQLAlchemy ORM models for notarial register."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class AttestationRow(Base):
    __tablename__ = "attestations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instrument_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    registration_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    export_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    draft_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attestation_clause_definition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attestation_clause_version: Mapped[str] = mapped_column(String(32), nullable=False)
    attestation_conditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    notary_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    practising_jurisdiction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    registration_jurisdiction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_language: Mapped[str] = mapped_column(String(16), nullable=False)
    attested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    place_of_execution: Mapped[str] = mapped_column(String(255), nullable=False)
    executants_json: Mapped[str] = mapped_column(Text, nullable=False)
    witnesses_json: Mapped[str] = mapped_column(Text, nullable=False)
    consideration_recorded: Mapped[bool | None] = mapped_column(nullable=True)
    external_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RegisterSerialCounterRow(Base):
    __tablename__ = "register_serial_counters"
    __table_args__ = (
        UniqueConstraint("notary_user_id", "register_year", name="uq_register_serial_scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    notary_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    register_year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_serial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RegisterEntryRow(Base):
    __tablename__ = "register_entries"
    __table_args__ = (
        UniqueConstraint(
            "notary_user_id",
            "register_year",
            "serial_number",
            name="uq_register_entry_serial",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    notary_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    register_year: Mapped[int] = mapped_column(Integer, nullable=False)
    serial_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attestation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("attestations.id", ondelete="CASCADE"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    party_summary_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    consideration_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    folio_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProtocolRecordRow(Base):
    __tablename__ = "protocol_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attestation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("attestations.id", ondelete="CASCADE"), nullable=False
    )
    copy_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    physical_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custodian_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_class: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class RegistrationSubmissionRow(Base):
    __tablename__ = "registration_submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attestation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("attestations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    registry_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    defect_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MonthlyReturnPeriodRow(Base):
    __tablename__ = "monthly_return_periods"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    notary_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    instrument_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_nil_return: Mapped[bool] = mapped_column(nullable=False, default=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    component_states_json: Mapped[str] = mapped_column(Text, nullable=False)
    certified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OutboxEventRow(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
