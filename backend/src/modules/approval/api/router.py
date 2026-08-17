"""Approval, export, and registration API router.

```text
POST /api/v1/forms/{formId}/approvals                responsible lawyer only
GET  /api/v1/forms/{formId}/approvals                approval history
POST /api/v1/forms/{formId}/exports                  a record, never a document
GET  /api/v1/matters/{matterId}/exports              paginated, newest first
POST /api/v1/matters/{matterId}/registration-events  attestation / presentation / result
GET  /api/v1/matters/{matterId}/registration-events  paginated, newest first
```

Forms are addressed without their matter in the path (§12.4), so those routes
resolve the form under the caller's ``user_id`` first and authorise against the
matter it turns out to belong to. A 404 covers both "absent" and "not yours".

No route here takes `If-Match`. An approval, an export, and a registration event
are all immutable records, and api-conventions §3 gives immutable resources no
version to condition on. The form version an approval pins is read from the
server's own record, never from a header the client chose (§9.6).

**A 2xx here is never a legal conclusion.** A 201 from `/exports` means a record
was written; it does not mean the instrument may be executed, presented, or
registered. A 201 from `/registration-events` means the lawyer's account of an
official act was recorded, not that the act occurred.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context
from src.modules.approval.api.schemas import (
    ApprovalCreatedRead,
    ApprovalGateItemRead,
    ApprovalGateRead,
    ApprovalListRead,
    ApprovalRead,
    ApproveFormRequest,
    ExportFormRequest,
    FormExportListRead,
    FormExportRead,
    PageInfo,
    PresentationDeadlineRead,
    RecordRegistrationEventRequest,
    RegistrationEventCreatedRead,
    RegistrationEventListRead,
    RegistrationEventRead,
)
from src.modules.approval.application.approval_service import (
    ApprovalService,
    ApprovalView,
    RegistrationEventView,
)
from src.modules.approval.domain.declarations import CURRENT_DECLARATION_VERSION
from src.modules.approval.domain.models import (
    Approval,
    ExportFormat,
    FormExport,
    RegistrationEvent,
)
from src.modules.approval.domain.policies import (
    ApprovalGateItem,
    ApprovalGateResult,
    require_responsible_lawyer,
)
from src.modules.content_governance.contracts import (
    CAP_AUDIT_READ,
    CAP_FORM_EXPORT,
    CAP_REGISTRATION_EVENT_RECORD,
    RegistrationEventType,
)
from src.modules.matter.contracts import MatterAccessSummary, require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["approvals"])


def get_approval_service(session: AsyncSession = Depends(get_db)) -> ApprovalService:
    from src.bootstrap import build_approval_service

    return build_approval_service(session)


async def _matter(
    ctx: RequestContext, matter_id: str, session: AsyncSession
) -> MatterAccessSummary:
    """Resolve the matter through its own module. Absent or foreign is 404."""
    from src.bootstrap import build_matter_service

    summary = await build_matter_service(session).get_access_summary(ctx.actor_id, matter_id)
    if summary is None:
        raise MatterNotFoundError()
    return summary


async def _authorize(
    ctx: RequestContext, matter_id: str, session: AsyncSession, capability: str
) -> MatterAccessSummary:
    matter = await _matter(ctx, matter_id, session)
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=matter,
        capability=capability,
    )
    return matter


def _export_format(raw: str) -> ExportFormat:
    try:
        return ExportFormat(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not a record this server produces.",
            field="format",
            permitted=sorted(item.value for item in ExportFormat),
        )


def _event_type(raw: str) -> RegistrationEventType:
    try:
        return RegistrationEventType(raw)
    except ValueError:
        raise DomainRuleError(
            f"'{raw}' is not a registration event type.",
            field="eventType",
            permitted=sorted(item.value for item in RegistrationEventType),
        )


def _event_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise DomainRuleError(
            "eventDate must be an ISO calendar date, for example 2026-08-16.",
            field="eventDate",
        )


def _to_gate_item_read(item: ApprovalGateItem) -> ApprovalGateItemRead:
    return ApprovalGateItemRead(
        id=item.id,
        code=item.code.value,
        subject_id=item.subject_id,
        explanation_key=item.explanation_key,
        blocking=item.blocking,
    )


def _to_gate_read(result: ApprovalGateResult) -> ApprovalGateRead:
    return ApprovalGateRead(
        form_id=result.form_id,
        template_id=result.template_id,
        template_version=result.template_version,
        rule_pack_version=result.rule_pack_version,
        blocking=[_to_gate_item_read(item) for item in result.blocking],
        warnings=[_to_gate_item_read(item) for item in result.warnings],
        approval_ready=result.approval_ready,
        registration_ready=result.registration_ready,
        template_registration_ready_capable=result.template_registration_ready_capable,
    )


def _to_approval_read(approval: Approval) -> ApprovalRead:
    return ApprovalRead(
        id=approval.id,
        matter_id=approval.matter_id,
        target_type=approval.target_type.value,
        target_id=approval.target_id,
        target_version=approval.target_version,
        approver_id=approval.approver_id,
        approver_workflow_role=approval.approver_workflow_role.value,
        declaration_version=approval.declaration_version,
        declaration_text_hash=approval.declaration_text_hash,
        snapshot_hash=approval.snapshot_hash,
        confirmed_fact_hash=approval.confirmed_fact_hash,
        warning_disposition_ids=list(approval.warning_disposition_ids),
        template_id=approval.template_id,
        template_version=approval.template_version,
        rule_pack_version=approval.rule_pack_version,
        revoked_by_approval_id=approval.revoked_by_approval_id,
        created_at=approval.created_at.isoformat(),
    )


def _to_export_read(export: FormExport) -> FormExportRead:
    watermark = export.manifest.get("watermark")
    return FormExportRead(
        id=export.id,
        matter_id=export.matter_id,
        generated_form_id=export.generated_form_id,
        approval_id=export.approval_id,
        artifact_kind=export.export_format.value,
        artifact_hash=export.artifact_hash,
        artifact_key=export.artifact_key,
        watermarked=export.watermarked,
        watermark_key=watermark.get("key") if isinstance(watermark, dict) else None,
        registration_ready=export.registration_ready,
        registration_ready_blocked_by=list(export.manifest.get("registrationReadyBlockedBy") or []),
        manifest=export.manifest,
        created_by=export.created_by,
        created_at=export.created_at.isoformat(),
    )


def _to_event_read(event: RegistrationEvent) -> RegistrationEventRead:
    return RegistrationEventRead(
        id=event.id,
        matter_id=event.matter_id,
        generated_form_id=event.generated_form_id,
        event_type=event.event_type.value,
        event_date=event.event_date.isoformat(),
        evidence_reference_ids=list(event.evidence_reference_ids),
        day_book_reference=event.day_book_reference,
        registry_office=event.registry_office,
        result_note=event.result_note,
        recorded_by=event.recorded_by,
        created_at=event.created_at.isoformat(),
    )


def _to_approval_created(view: ApprovalView) -> ApprovalCreatedRead:
    return ApprovalCreatedRead(
        approval=_to_approval_read(view.approval), gate=_to_gate_read(view.gate)
    )


def _to_event_created(view: RegistrationEventView) -> RegistrationEventCreatedRead:
    deadline = view.deadline
    return RegistrationEventCreatedRead(
        event=_to_event_read(view.event),
        implied_matter_state=(
            view.implied_matter_state.value if view.implied_matter_state else None
        ),
        deadline=(
            PresentationDeadlineRead(
                attested_on=deadline.attested_on.isoformat(),
                due_on=deadline.due_on.isoformat(),
                working_days=deadline.working_days,
                basis_key=deadline.basis_key,
                provisional=deadline.provisional,
                unverified_reason_key=deadline.unverified_reason_key,
            )
            if deadline is not None
            else None
        ),
    )


@router.post("/forms/{form_id}/approvals", response_model=ApprovalCreatedRead, status_code=201)
async def approve_form(
    form_id: str,
    body: ApproveFormRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalCreatedRead:
    """Approve one exact form snapshot. Responsible lawyer only (§12.5).

    `require_responsible_lawyer` refuses a case assistant, a lawyer reviewer,
    and an office administrator with 403, and template counsel with 404 — it has
    no access to client matters at all. No service account can reach this route:
    the approver is the authenticated actor and the capability is granted to one
    workflow role on one matter.
    """
    _ = uow
    matter_id = await service.matter_id_for_form(user_id=ctx.actor_id, form_id=form_id)
    matter = await _matter(ctx, matter_id, session)
    role = require_responsible_lawyer(
        account_role=ctx.account_role.value, actor_id=ctx.actor_id, matter=matter
    )
    view = await service.approve_form(
        user_id=ctx.actor_id,
        form_id=form_id,
        actor_id=ctx.actor_id,
        workflow_role=role,
        correlation_id=ctx.correlation_id,
        disposed_warning_ids=body.disposed_warning_ids,
        declaration_version=body.declaration_version or CURRENT_DECLARATION_VERSION,
    )
    return _to_approval_created(view)


@router.get("/forms/{form_id}/approvals", response_model=ApprovalListRead)
async def list_approvals(
    form_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
) -> ApprovalListRead:
    """The approval history of one form. Revoked approvals are included.

    A superseded approval is the record of a signature that was given, and §17
    needs it readable: "a correction after approval marks the form stale and
    prevents reuse of the old approval" is only demonstrable if the old approval
    is still there to be seen.
    """
    matter_id = await service.matter_id_for_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    approvals, next_cursor = await service.list_approvals(
        user_id=ctx.actor_id, form_id=form_id, limit=limit, cursor=cursor
    )
    current = await service.current_approval(ctx.actor_id, form_id)
    return ApprovalListRead(
        items=[_to_approval_read(approval) for approval in approvals],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
        gate=_to_gate_read(await service.approval_gate(user_id=ctx.actor_id, form_id=form_id)),
        current_approval_id=current.id if current else None,
    )


@router.post("/forms/{form_id}/exports", response_model=FormExportRead, status_code=201)
async def export_form(
    form_id: str,
    body: ExportFormRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> FormExportRead:
    """Produce one export record.

    No document is produced. Every template in this repository is a
    transcription with no approved production rendering (§9.5), so what this
    returns is a manifest — the binding record, its evidence chain, and the
    qualifications that travel with it — and it is explicitly an internal review
    artifact. `registrationReady` is false in every case.
    """
    _ = uow
    matter_id = await service.matter_id_for_form(user_id=ctx.actor_id, form_id=form_id)
    await _authorize(ctx, matter_id, session, CAP_FORM_EXPORT)
    return _to_export_read(
        await service.export_form(
            user_id=ctx.actor_id,
            form_id=form_id,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
            export_format=_export_format(body.format),
        )
    )


@router.get("/matters/{matter_id}/exports", response_model=FormExportListRead)
async def list_exports(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
) -> FormExportListRead:
    """Every export taken on the matter, newest first. Nothing is ever deleted."""
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    exports, next_cursor = await service.list_exports(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return FormExportListRead(
        items=[_to_export_read(export) for export in exports],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )


@router.post(
    "/matters/{matter_id}/registration-events",
    response_model=RegistrationEventCreatedRead,
    status_code=201,
)
async def record_registration_event(
    matter_id: str,
    body: RecordRegistrationEventRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> RegistrationEventCreatedRead:
    """Record an attestation, a presentation, or a registry result.

    Three separate events, each requiring a human, a date, and evidence. Time
    advances none of them, export is none of them, and only a recorded
    registration result reaches ``REGISTERED`` (§9.6, §10.1, §17). A confirmed
    attestation date — and nothing else — starts the s. 45(1) seven-working-day
    forwarding task, whose date is provisional while the public-holiday calendar
    is unverified (§16.4).
    """
    _ = uow
    await _authorize(ctx, matter_id, session, CAP_REGISTRATION_EVENT_RECORD)
    view = await service.record_registration_event(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        event_type=_event_type(body.event_type),
        event_date=_event_date(body.event_date),
        evidence_reference_ids=body.evidence_reference_ids,
        generated_form_id=body.generated_form_id,
        day_book_reference=body.day_book_reference,
        registry_office=body.registry_office,
        result_note=body.result_note,
    )
    return _to_event_created(view)


@router.get("/matters/{matter_id}/registration-events", response_model=RegistrationEventListRead)
async def list_registration_events(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: ApprovalService = Depends(get_approval_service),
    session: AsyncSession = Depends(get_db),
) -> RegistrationEventListRead:
    """Every recorded registry act on the matter, newest first."""
    await _authorize(ctx, matter_id, session, CAP_AUDIT_READ)
    events, next_cursor = await service.list_registration_events(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return RegistrationEventListRead(
        items=[_to_event_read(event) for event in events],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )
