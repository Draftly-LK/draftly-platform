"""Notarial register API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_notarial_register_service, get_request_context
from src.modules.notarial_register.api.schemas import (
    AddProtocolRequest,
    AttestationRead,
    CollectionRequest,
    CreateAttestationRequest,
    MonthlyReturnPeriodRead,
    ProtocolRead,
    RegisterEntriesPageRead,
    RegisterEntryRead,
    RegistrationAcknowledgementRequest,
    RegistrationSubmissionRequest,
)
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.modules.notarial_register.domain.models import (
    AddProtocolInput,
    Attestation,
    AttestationCondition,
    CollectionInput,
    CreateAttestationInput,
    InstrumentKind,
    PartyRef,
    ProtocolCopyKind,
    RegisterEntryFilters,
    RegistrationAcknowledgementInput,
    RegistrationRegime,
    RegistrationSubmissionInput,
    SourceKind,
)
from src.platform.request_context import RequestContext

router = APIRouter(tags=["notarial-register"])


def _to_attestation_read(attestation: Attestation) -> AttestationRead:
    return AttestationRead(
        id=attestation.id,
        matter_id=attestation.matter_id,
        instrument_kind=attestation.instrument_kind.value,
        registration_regime=attestation.registration_regime.value,
        source_kind=attestation.source_kind.value,
        export_id=attestation.export_id,
        content_hash=attestation.content_hash,
        notary_user_id=attestation.notary_user_id,
        practising_jurisdiction_id=attestation.practising_jurisdiction_id,
        registration_jurisdiction_id=attestation.registration_jurisdiction_id,
        attested_at=attestation.attested_at,
        place_of_execution=attestation.place_of_execution,
        state=attestation.state.value,
        version=attestation.version,
    )


@router.post("/matters/{matter_id}/attestations", response_model=AttestationRead)
async def create_attestation(
    matter_id: str,
    body: CreateAttestationRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> AttestationRead:
    attestation = await service.record_attestation(
        ctx,
        matter_id,
        CreateAttestationInput(
            matter_id=matter_id,
            instrument_kind=InstrumentKind(body.instrument_kind),
            registration_regime=RegistrationRegime(body.registration_regime),
            source_kind=SourceKind(body.source_kind),
            export_id=body.export_id,
            attestation_clause_definition_id=body.attestation_clause_definition_id,
            attestation_clause_version=body.attestation_clause_version,
            attestation_conditions=[AttestationCondition(c) for c in body.attestation_conditions],
            practising_jurisdiction_id=body.practising_jurisdiction_id,
            registration_jurisdiction_id=body.registration_jurisdiction_id,
            instrument_language=body.instrument_language,
            attested_at=body.attested_at,
            place_of_execution=body.place_of_execution,
            executants=[PartyRef(p.party_id, p.capacity, p.evidence_ref) for p in body.executants],
            witnesses=[PartyRef(p.party_id, p.capacity, p.evidence_ref) for p in body.witnesses],
            consideration_recorded=body.consideration_recorded,
            party_summary_ref=body.party_summary_ref,
            consideration_ref=body.consideration_ref,
            folio_ref=body.folio_ref,
            external_reason=body.external_reason,
            approved_instrument_fixture=body.approved_instrument_fixture,
        ),
    )
    return _to_attestation_read(attestation)


@router.get(
    "/matters/{matter_id}/attestations/{attestation_id}",
    response_model=AttestationRead,
)
async def get_attestation(
    matter_id: str,
    attestation_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> AttestationRead:
    attestation = await service.get_attestation(ctx, matter_id, attestation_id)
    return _to_attestation_read(attestation)


@router.post("/attestations/{attestation_id}/protocol", response_model=ProtocolRead)
async def add_protocol(
    attestation_id: str,
    body: AddProtocolRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> ProtocolRead:
    record = await service.add_protocol(
        ctx,
        attestation_id,
        AddProtocolInput(
            copy_kind=ProtocolCopyKind(body.copy_kind),
            storage_ref=body.storage_ref,
            physical_location=body.physical_location,
            custodian_user_id=body.custodian_user_id,
            retention_class=body.retention_class,
        ),
    )
    return ProtocolRead(
        id=record.id,
        attestation_id=record.attestation_id,
        copy_kind=record.copy_kind.value,
        state=record.state.value,
        retention_class=record.retention_class,
    )


@router.post("/attestations/{attestation_id}/registration-submission")
async def registration_submission(
    attestation_id: str,
    body: RegistrationSubmissionRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> dict[str, str]:
    submission = await service.record_registration_submission(
        ctx,
        attestation_id,
        RegistrationSubmissionInput(registry_id=body.registry_id),
    )
    return {"id": submission.id, "state": submission.state.value}


@router.post("/attestations/{attestation_id}/registration-acknowledgement")
async def registration_acknowledgement(
    attestation_id: str,
    body: RegistrationAcknowledgementRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> AttestationRead:
    attestation = await service.record_registration_acknowledgement(
        ctx,
        attestation_id,
        RegistrationAcknowledgementInput(
            outcome=body.outcome,
            registry_reference=body.registry_reference,
        ),
    )
    return _to_attestation_read(attestation)


@router.post("/attestations/{attestation_id}/collection", response_model=AttestationRead)
async def record_collection(
    attestation_id: str,
    body: CollectionRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> AttestationRead:
    attestation = await service.record_collection(
        ctx,
        attestation_id,
        CollectionInput(ready_at=body.ready_at),
    )
    return _to_attestation_read(attestation)


@router.get("/register/entries", response_model=RegisterEntriesPageRead)
async def list_register_entries(
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
    register_year: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RegisterEntriesPageRead:
    page = await service.list_register_entries(
        ctx,
        RegisterEntryFilters(register_year=register_year, limit=limit, offset=offset),
    )
    return RegisterEntriesPageRead(
        items=[
            RegisterEntryRead(
                id=item.id,
                notary_user_id=item.notary_user_id,
                register_year=item.register_year,
                serial_number=item.serial_number,
                attestation_id=item.attestation_id,
                entry_date=item.entry_date,
                instrument_kind=item.instrument_kind.value,
                party_summary_ref=item.party_summary_ref,
                consideration_ref=item.consideration_ref,
                folio_ref=item.folio_ref,
                state=item.state.value,
            )
            for item in page.items
        ],
        total=page.total,
    )


@router.get("/register/periods", response_model=list[MonthlyReturnPeriodRead])
async def list_register_periods(
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> list[MonthlyReturnPeriodRead]:
    periods = await service.list_monthly_periods(ctx)
    return [
        MonthlyReturnPeriodRead(
            id=p.id,
            notary_user_id=p.notary_user_id,
            period_start=p.period_start,
            period_end=p.period_end,
            instrument_ids=p.instrument_ids,
            is_nil_return=p.is_nil_return,
            state=p.state.value,
            version=p.version,
        )
        for p in periods
    ]


@router.post("/register/periods/{period_id}/certify", response_model=MonthlyReturnPeriodRead)
async def certify_period(
    period_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: NotarialRegisterService = Depends(get_notarial_register_service),
) -> MonthlyReturnPeriodRead:
    period = await service.certify_period(ctx, period_id)
    return MonthlyReturnPeriodRead(
        id=period.id,
        notary_user_id=period.notary_user_id,
        period_start=period.period_start,
        period_end=period.period_end,
        instrument_ids=period.instrument_ids,
        is_nil_return=period.is_nil_return,
        state=period.state.value,
        version=period.version,
    )
