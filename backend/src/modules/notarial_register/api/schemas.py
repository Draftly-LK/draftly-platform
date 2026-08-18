"""Pydantic API schemas for notarial register routes."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PartyRefSchema(BaseModel):
    party_id: str
    capacity: str | None = None
    evidence_ref: str | None = None


class CreateAttestationRequest(BaseModel):
    instrument_kind: str
    registration_regime: str
    source_kind: str = "export"
    export_id: str | None = None
    attestation_clause_definition_id: str
    attestation_clause_version: str
    attestation_conditions: list[str]
    practising_jurisdiction_id: str
    registration_jurisdiction_id: str
    instrument_language: str = "en"
    attested_at: datetime
    place_of_execution: str
    executants: list[PartyRefSchema]
    witnesses: list[PartyRefSchema] = Field(default_factory=list)
    consideration_recorded: bool | None = None
    party_summary_ref: str
    consideration_ref: str | None = None
    folio_ref: str | None = None
    external_reason: str | None = None
    approved_instrument_fixture: bool = False


class AttestationRead(BaseModel):
    id: str
    matter_id: str
    instrument_kind: str
    registration_regime: str
    source_kind: str
    export_id: str | None
    content_hash: str | None
    notary_user_id: str
    practising_jurisdiction_id: str
    registration_jurisdiction_id: str
    attested_at: datetime
    place_of_execution: str
    state: str
    version: int


class AddProtocolRequest(BaseModel):
    copy_kind: str
    storage_ref: str | None = None
    physical_location: str | None = None
    custodian_user_id: str | None = None
    retention_class: str = "notarial-protocol"


class ProtocolRead(BaseModel):
    id: str
    attestation_id: str
    copy_kind: str
    state: str
    retention_class: str


class RegistrationSubmissionRequest(BaseModel):
    registry_id: str


class RegistrationAcknowledgementRequest(BaseModel):
    outcome: str
    registry_reference: str | None = None


class CollectionRequest(BaseModel):
    ready_at: datetime | None = None


class RegisterEntryRead(BaseModel):
    id: str
    notary_user_id: str
    register_year: int
    serial_number: int
    attestation_id: str
    entry_date: date
    instrument_kind: str
    party_summary_ref: str
    consideration_ref: str | None
    folio_ref: str | None
    state: str


class RegisterEntriesPageRead(BaseModel):
    items: list[RegisterEntryRead]
    total: int


class MonthlyReturnPeriodRead(BaseModel):
    id: str
    notary_user_id: str
    period_start: date
    period_end: date
    instrument_ids: list[str]
    is_nil_return: bool
    state: str
    version: int
