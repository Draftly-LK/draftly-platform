"""Matter API router.

```text
POST   /api/v1/matters                          create an intake draft
GET    /api/v1/matters                          list the caller's matters
GET    /api/v1/matters/{id}                     read one matter (ETag = version)
GET    /api/v1/matters/{id}/intake              live intake answers
PUT    /api/v1/matters/{id}/intake/{questionId} save or supersede one answer
POST   /api/v1/matters/{id}/subtype             confirm the exact instrument
POST   /api/v1/matters/{id}/route               evaluate regime, subtype, scope
POST   /api/v1/matters/{id}/checklist/compile   create a checklist snapshot
```

Mutating routes depend on ``get_uow`` so the mutation and its audit event
commit as one transaction, and on ``require_if_match`` so a stale client cannot
overwrite a concurrent decision.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.content_governance.contracts import CURRENT_VERSIONS
from src.modules.matter.api.schemas import (
    ChecklistDeltaRead,
    ChecklistItemRead,
    ChecklistSnapshotRead,
    ConfirmSubtypeRequest,
    CreateMatterRequest,
    GateRead,
    IntakeAnswerRead,
    MatterListRead,
    MatterRead,
    PageInfo,
    RoutingRead,
    SaveAnswerRequest,
)
from src.modules.matter.application.matter_service import (
    ChecklistCompileResult,
    CreateMatterInput,
    MatterService,
    RoutingResult,
)
from src.modules.matter.domain.models import InstrumentLanguage, IntakeAnswer, Matter
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

router = APIRouter(tags=["matters"])


def get_matter_service(session: AsyncSession = Depends(get_db)) -> MatterService:
    """Request-scoped service; repositories are bound to this request's session."""
    from src.bootstrap import build_matter_service

    return build_matter_service(session)


def _to_read(matter: Matter) -> MatterRead:
    return MatterRead(
        id=matter.id,
        reference=matter.reference,
        client_reference=matter.client_reference,
        responsible_lawyer_id=matter.responsible_lawyer_id,
        regime_id=matter.regime_id,
        family_id=matter.family_id.value if matter.family_id else None,
        subtype_id=matter.subtype_id,
        subtype_decision_status=matter.subtype_decision_status.value,
        legacy_matter_type=matter.legacy_matter_type,
        lifecycle_status=matter.lifecycle_status.value,
        state=matter.rta_state.value,
        automation_scope=matter.automation_scope.value,
        title_status=matter.title_status.value,
        parcel_kind=matter.parcel_kind.value,
        disposition_scope=matter.disposition_scope.value,
        dispute_stage=matter.dispute_stage.value,
        instrument_language=matter.instrument_language.value,
        local_authority_id=matter.local_authority_id,
        active_checklist_snapshot_id=matter.active_checklist_snapshot_id,
        party_contexts=sorted(c.value for c in matter.party_contexts),
        activated_conditional_module_ids=sorted(matter.activated_conditional_module_ids),
        automation_exclusion_reason_keys=list(matter.automation_exclusion_reason_keys),
        created_at=matter.created_at.isoformat(),
        updated_at=matter.updated_at.isoformat(),
        version=matter.version,
    )


def _to_answer_read(answer: IntakeAnswer) -> IntakeAnswerRead:
    return IntakeAnswerRead(
        id=answer.id,
        question_definition_id=answer.question_definition_id,
        value=answer.value,
        status=answer.status.value,
        answered_by=answer.answered_by,
        answer_reason=answer.answer_reason,
        supersedes_id=answer.supersedes_id,
        inferred_from_fact_ids=list(answer.inferred_from_fact_ids),
        created_at=answer.created_at.isoformat(),
    )


def _to_routing_read(result: RoutingResult) -> RoutingRead:
    return RoutingRead(
        matter=_to_read(result.matter),
        automation_scope=result.decision.automation_scope.value,
        gates=[
            GateRead(
                id=gate.id,
                satisfied=gate.satisfied,
                severity=gate.severity.value,
                blocker_kind=gate.blocker_kind.value,
                reason_key=gate.reason_key,
                source_record_ids=[c.source_record_id for c in gate.sources],
                is_v0_predicate=gate.is_v0_predicate,
            )
            for gate in result.decision.gates
        ],
        unmet_gate_ids=list(result.decision.unmet_gate_ids),
        statutory_blocker_ids=[g.id for g in result.decision.statutory_blockers],
        next_question_ids=list(result.next_question_ids),
        activated_conditional_module_ids=sorted(result.derivation.activated_conditional_module_ids),
    )


def _to_snapshot_read(result: ChecklistCompileResult) -> ChecklistSnapshotRead:
    return ChecklistSnapshotRead(
        snapshot_id=result.snapshot_id,
        matter_id=result.matter.id,
        fingerprint=result.checklist.fingerprint,
        rule_pack_versions=CURRENT_VERSIONS.as_dict(),
        module_definition_ids=list(result.checklist.module_definition_ids),
        items=[
            ChecklistItemRead(
                requirement_definition_id=item.requirement_definition_id,
                module_definition_id=item.module_definition_id,
                inclusion_reason=item.inclusion_reason.value,
                inclusion_trigger_id=item.inclusion_trigger_id,
                label_key=item.label_key,
                explanation_key=item.explanation_key,
                mandatory_basis=item.mandatory_basis.value,
                group=item.group.value,
                applicability=item.applicability.value,
                source_record_ids=list(item.source_record_ids),
                accepted_document_class_ids=list(item.accepted_document_class_ids),
                may_be_satisfied_by_combined_document=item.may_be_satisfied_by_combined_document,
                physical_original_policy=item.physical_original_policy,
                currency_max_age_days=item.currency_max_age_days,
                unsatisfied_severity=item.unsatisfied_severity.value,
                unsatisfied_blocker_kind=item.unsatisfied_blocker_kind.value,
                waivable=item.waivable,
                local_authority_id=item.local_authority_id,
            )
            for item in result.checklist.items
        ],
        delta=ChecklistDeltaRead(added=[], removed=[], changed=[], retained_after_review=[]),
    )


@router.post("/matters", response_model=MatterRead, status_code=201)
async def create_matter(
    body: CreateMatterRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
    uow: UnitOfWork = Depends(get_uow),
) -> MatterRead:
    """Create an intake draft. The exact instrument is chosen later, by a lawyer."""
    _ = uow
    matter = await service.create_matter(
        ctx,
        CreateMatterInput(
            reference=body.reference,
            client_reference=body.client_reference,
            instrument_language=InstrumentLanguage(body.instrument_language),
            local_authority_id=body.local_authority_id,
            legacy_matter_type=body.legacy_matter_type,
        ),
    )
    response.headers["ETag"] = f'"{matter.version}"'
    return _to_read(matter)


@router.get("/matters", response_model=MatterListRead)
async def list_matters(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
) -> MatterListRead:
    matters, next_cursor = await service.list_matters(ctx, limit=limit, cursor=cursor)
    return MatterListRead(
        items=[_to_read(m) for m in matters],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )


@router.get("/matters/{matter_id}", response_model=MatterRead)
async def get_matter(
    matter_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
) -> MatterRead:
    matter = await service.get_matter(ctx, matter_id)
    response.headers["ETag"] = f'"{matter.version}"'
    return _to_read(matter)


@router.get("/matters/{matter_id}/intake", response_model=list[IntakeAnswerRead])
async def list_intake_answers(
    matter_id: str,
    include_superseded: bool = False,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
) -> list[IntakeAnswerRead]:
    """Superseded answers stay retrievable: history is part of the record."""
    answers = await service.list_answers(ctx, matter_id, include_superseded=include_superseded)
    return [_to_answer_read(a) for a in answers]


@router.put("/matters/{matter_id}/intake/{question_id}", response_model=IntakeAnswerRead)
async def save_intake_answer(
    matter_id: str,
    question_id: str,
    body: SaveAnswerRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
    uow: UnitOfWork = Depends(get_uow),
) -> IntakeAnswerRead:
    """Record an answer. The previous one is superseded, never overwritten."""
    _ = uow
    answer = await service.save_answer(
        ctx,
        matter_id,
        question_id,
        value=body.value,
        lawyer_confirmed=body.lawyer_confirmed,
        reason=body.reason,
        inferred_from_fact_ids=tuple(body.inferred_from_fact_ids),
    )
    return _to_answer_read(answer)


@router.post("/matters/{matter_id}/subtype", response_model=MatterRead)
async def confirm_subtype(
    matter_id: str,
    body: ConfirmSubtypeRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> MatterRead:
    """Responsible-lawyer-only. Selecting a family is not selecting an instrument."""
    _ = uow
    matter = await service.confirm_subtype(
        ctx,
        matter_id,
        subtype_id=body.subtype_id,
        declared_legal_basis=body.declared_legal_basis,
        expected_version=expected_version,
    )
    response.headers["ETag"] = f'"{matter.version}"'
    return _to_read(matter)


@router.post("/matters/{matter_id}/route", response_model=RoutingRead)
async def route_matter(
    matter_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> RoutingRead:
    """Return the decision, its reasons, and the rule versions it used.

    A 200 here means the evaluation was recorded. It is not a statement that
    the matter is legally in order (api-conventions §5).
    """
    _ = uow
    result = await service.route(ctx, matter_id, expected_version=expected_version)
    response.headers["ETag"] = f'"{result.matter.version}"'
    return _to_routing_read(result)


@router.post("/matters/{matter_id}/checklist/compile", response_model=ChecklistSnapshotRead)
async def compile_checklist(
    matter_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: MatterService = Depends(get_matter_service),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> ChecklistSnapshotRead:
    """Compile a versioned snapshot. Idempotent over unchanged inputs."""
    _ = uow
    result = await service.compile_checklist(ctx, matter_id, expected_version=expected_version)
    response.headers["ETag"] = f'"{result.matter.version}"'
    return _to_snapshot_read(result)
