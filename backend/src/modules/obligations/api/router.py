"""Obligations API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from src.api.deps import get_obligations_service, get_request_context
from src.modules.obligations.api.schemas import (
    CancelObligationRequest,
    CompleteObligationRequest,
    ConfirmDeadlineRequest,
    CreateObligationRequest,
    LawyerConfirmationRead,
    ObligationListResponse,
    ObligationRead,
    PageMeta,
)
from src.modules.obligations.application.obligations_service import (
    CancelObligationCommand,
    CompleteObligationCommand,
    ConfirmDeadlineCommand,
    CreateObligationCommand,
    ObligationsService,
)
from src.modules.obligations.domain.models import (
    ConfidentialityLevel,
    Obligation,
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationType,
)
from src.modules.obligations.ports import ObligationListFilters
from src.platform.errors import DomainRuleError, PreconditionFailedError, PreconditionRequiredError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["obligations"])


def _to_read(obligation: Obligation) -> ObligationRead:
    conf = obligation.lawyer_confirmation
    return ObligationRead(
        id=obligation.id,
        organisation_id=obligation.organisation_id,
        scope=obligation.scope.value,
        matter_id=obligation.matter_id,
        obligation_type=obligation.obligation_type.value,
        obligation_class=obligation.obligation_class.value,
        label_key=obligation.label_key,
        due_at=obligation.due_at,
        timezone=obligation.timezone,
        hardness=obligation.hardness.value,
        status=obligation.status.value,
        assignee_user_id=obligation.assignee_user_id,
        confidentiality_level=obligation.confidentiality_level.value,
        lawyer_confirmation=LawyerConfirmationRead(
            status=conf.status.value,
            confirmed_by=conf.confirmed_by,
            confirmed_at=conf.confirmed_at,
            reason=conf.reason,
            original_due_at=conf.original_due_at,
        ),
        calculation_explanation=obligation.calculation_explanation,
        version=obligation.version,
        created_at=obligation.created_at,
        updated_at=obligation.updated_at,
    )


def _parse_enum(value: str, enum_cls: type, field_name: str):  # type: ignore[no-untyped-def]
    try:
        return enum_cls(value)
    except ValueError:
        raise DomainRuleError(f"Invalid {field_name} '{value}'.")


def _require_version(if_match: str | None, expected: int) -> None:
    if if_match is None:
        raise PreconditionRequiredError()
    try:
        version = int(if_match.strip('"'))
    except ValueError:
        raise PreconditionFailedError()
    if version != expected:
        raise PreconditionFailedError()


@router.get("/obligations", response_model=ObligationListResponse)
async def list_obligations(
    ctx: RequestContext = Depends(get_request_context),
    service: ObligationsService = Depends(get_obligations_service),
    matter_id: str | None = Query(default=None, alias="matterId"),
    assignee_user_id: str | None = Query(default=None, alias="assigneeUserId"),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> ObligationListResponse:
    items, next_cursor, has_more = await service.list_obligations(
        ctx,
        ObligationListFilters(
            matter_id=matter_id,
            assignee_user_id=assignee_user_id,
            status=status,
            limit=limit,
            cursor=cursor,
        ),
    )
    return ObligationListResponse(
        items=[_to_read(item) for item in items],
        page=PageMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.post("/obligations", response_model=ObligationRead, status_code=201)
async def create_obligation(
    body: CreateObligationRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ObligationsService = Depends(get_obligations_service),
) -> ObligationRead:
    command = CreateObligationCommand(
        scope=_parse_enum(body.scope, ObligationScope, "scope"),
        obligation_type=_parse_enum(body.obligation_type, ObligationType, "obligation_type"),
        obligation_class=_parse_enum(body.obligation_class, ObligationClass, "obligation_class"),
        label_key=body.label_key,
        due_at=body.due_at,
        timezone=body.timezone,
        hardness=_parse_enum(body.hardness, ObligationHardness, "hardness"),
        assignee_user_id=body.assignee_user_id,
        matter_id=body.matter_id,
        legal_authority_ref=body.legal_authority_ref,
        confidentiality_level=_parse_enum(
            body.confidentiality_level, ConfidentialityLevel, "confidentiality_level"
        ),
    )
    obligation = await service.create_obligation(ctx, command)
    return _to_read(obligation)


@router.post("/obligations/{obligation_id}/confirm", response_model=ObligationRead)
async def confirm_obligation(
    obligation_id: str,
    body: ConfirmDeadlineRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ObligationsService = Depends(get_obligations_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ObligationRead:
    existing = await service.get_obligation(ctx, obligation_id)
    _require_version(if_match, existing.version)
    obligation = await service.confirm_deadline(
        ctx,
        obligation_id,
        ConfirmDeadlineCommand(due_at=body.due_at, reason=body.reason),
    )
    return _to_read(obligation)


@router.post("/obligations/{obligation_id}/complete", response_model=ObligationRead)
async def complete_obligation(
    obligation_id: str,
    body: CompleteObligationRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ObligationsService = Depends(get_obligations_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ObligationRead:
    existing = await service.get_obligation(ctx, obligation_id)
    _require_version(if_match, existing.version)
    obligation = await service.complete_obligation(
        ctx,
        obligation_id,
        CompleteObligationCommand(completion_evidence_ref=body.completion_evidence_ref),
    )
    return _to_read(obligation)


@router.post("/obligations/{obligation_id}/cancel", response_model=ObligationRead)
async def cancel_obligation(
    obligation_id: str,
    body: CancelObligationRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ObligationsService = Depends(get_obligations_service),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ObligationRead:
    existing = await service.get_obligation(ctx, obligation_id)
    _require_version(if_match, existing.version)
    obligation = await service.cancel_obligation(
        ctx,
        obligation_id,
        CancelObligationCommand(reason=body.reason),
    )
    return _to_read(obligation)
