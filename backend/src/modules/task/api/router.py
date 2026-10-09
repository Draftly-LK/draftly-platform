"""Checklist API router.

```text
GET  /api/v1/matters/{id}/checklist                             current snapshot
GET  /api/v1/matters/{id}/checklist/snapshots/{snapshotId}      an earlier snapshot
POST /api/v1/matters/{id}/checklist-items/{itemId}/decisions    record a decision
POST /api/v1/matters/{id}/checklist-items/{itemId}/original-inspection
POST /api/v1/matters/{id}/checklist-items/{itemId}/links        link a document
GET  /api/v1/matters/{id}/checklist-items/{itemId}/links
```

Earlier snapshots stay readable on purpose: a lawyer must be able to see the
requirement set a decision was made under, not only the current one.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.content_governance.contracts import (
    CAP_CHECKLIST_DECIDE,
    CAP_CHECKLIST_WAIVE,
    CAP_ORIGINAL_INSPECT,
    ApplicabilityStatus,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    ResolutionStatus,
)
from src.modules.matter.contracts import require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.modules.task.api.replay import RequirementCommandReplay
from src.modules.task.api.schemas import (
    ChecklistItemRead,
    ChecklistRead,
    LinkDocumentRequest,
    OriginalInspectionRead,
    OriginalInspectionRequest,
    OriginalSourceRead,
    SatisfactionDecisionRequest,
    SatisfactionLinkRead,
)
from src.modules.task.application.checklist_service import (
    ChecklistItemView,
    ChecklistService,
    ChecklistView,
)
from src.modules.task.domain.models import SatisfactionLink
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["checklist"])


def get_checklist_service(session: AsyncSession = Depends(get_db)) -> ChecklistService:
    from src.bootstrap import build_checklist_service

    return build_checklist_service(session)


async def _authorized_matter(
    ctx: RequestContext, matter_id: str, session: AsyncSession, capability: str
) -> None:
    """Resolve the matter through its own module, then check the capability."""
    from src.bootstrap import build_matter_service

    summary = await build_matter_service(session).get_access_summary(ctx.actor_id, matter_id)
    if summary is None:
        raise MatterNotFoundError()
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=summary,
        capability=capability,
    )


def _to_item_read(view: ChecklistItemView) -> ChecklistItemRead:
    item, requirement = view.item, view.requirement
    inspection = item.original_inspection
    return ChecklistItemRead(
        id=item.id,
        requirement_definition_id=item.requirement_definition_id,
        module_definition_id=item.module_definition_id,
        inclusion_reason=item.inclusion_reason,
        inclusion_trigger_id=item.inclusion_trigger_id,
        label_key=requirement.label_key,
        explanation_key=requirement.explanation_key,
        mandatory_basis=requirement.mandatory_basis.value,
        group=requirement.group.value,
        source_record_ids=[c.source_record_id for c in requirement.sources],
        accepted_document_class_ids=list(requirement.accepted_document_class_ids),
        may_be_satisfied_by_combined_document=requirement.may_be_satisfied_by_combined_document,
        physical_original_policy=requirement.physical_original_policy.value,
        waivable=requirement.waivable,
        local_authority_id=item.local_authority_id,
        applicability=item.applicability.value,
        collection=item.collection.value,
        digital_review=item.digital_review.value,
        physical_original=item.physical_original.value,
        currency=item.currency.value,
        consistency=item.consistency.value,
        resolution=item.resolution.value,
        lifecycle=view.lifecycle.value,
        computed_resolution=view.computed_resolution.value,
        blocks_approval=view.blocks_approval,
        live_link_count=view.live_link_count,
        applicability_reason=item.applicability_reason,
        inspection_history=[
            OriginalInspectionRead(
                **{**asdict(entry), "inspected_at": entry.inspected_at.isoformat()}
            )
            for entry in item.inspection_history
        ],
        original_inspection=(
            OriginalInspectionRead(
                reviewer_id=inspection.reviewer_id,
                inspected_at=inspection.inspected_at.isoformat(),
                method=inspection.method,
                location=inspection.location,
                note=inspection.note,
                originals=[OriginalSourceRead(**asdict(pin)) for pin in inspection.originals],
            )
            if inspection
            else None
        ),
        assigned_to=item.assigned_to,
        due_at=item.due_at.isoformat() if item.due_at else None,
        version=item.version,
    )


def _to_checklist_read(view: ChecklistView) -> ChecklistRead:
    snapshot = view.snapshot
    return ChecklistRead(
        snapshot_id=snapshot.id,
        matter_id=snapshot.matter_id,
        fingerprint=snapshot.fingerprint,
        rule_pack_version=snapshot.rule_pack_version,
        compiler_version=snapshot.compiler_version,
        taxonomy_version=snapshot.taxonomy_version,
        checklist_version=snapshot.checklist_version,
        module_definition_ids=list(snapshot.module_definition_ids),
        supersedes_id=snapshot.supersedes_id,
        created_at=snapshot.created_at.isoformat(),
        items=[_to_item_read(item) for item in view.items],
        blocking_requirement_ids=list(view.blocking_requirement_ids),
    )


def _to_link_read(link: SatisfactionLink) -> SatisfactionLinkRead:
    return SatisfactionLinkRead(
        id=link.id,
        document_version=link.document_version,
        interpretation_generation=link.interpretation_generation,
        originals=[OriginalSourceRead(**asdict(pin)) for pin in link.originals],
        checklist_item_id=link.checklist_item_id,
        detected_document_id=link.detected_document_id,
        digital_review=link.digital_review.value,
        evidence_reference_ids=list(link.evidence_reference_ids),
        reviewed_by=link.reviewed_by,
        reviewed_at=link.reviewed_at.isoformat() if link.reviewed_at else None,
        review_note=link.review_note,
        superseded_by_link_id=link.superseded_by_link_id,
        is_live=link.is_live,
        created_at=link.created_at.isoformat(),
    )


def _enum(raw: str | None, enum_type: type, field: str):  # type: ignore[no-untyped-def]
    if raw is None:
        return None
    try:
        return enum_type(raw)
    except ValueError:
        raise DomainRuleError(f"'{raw}' is not a valid {field} value.", field=field, value=raw)


@router.get("/matters/{matter_id}/checklist", response_model=ChecklistRead)
async def get_checklist(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
) -> ChecklistRead:
    await _authorized_matter(ctx, matter_id, session, CAP_CHECKLIST_DECIDE)
    view = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter_id)
    return _to_checklist_read(view)


@router.get("/matters/{matter_id}/checklist/snapshots/{snapshot_id}", response_model=ChecklistRead)
async def get_checklist_snapshot(
    matter_id: str,
    snapshot_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
) -> ChecklistRead:
    await _authorized_matter(ctx, matter_id, session, CAP_CHECKLIST_DECIDE)
    view = await service.get_checklist(
        user_id=ctx.actor_id, matter_id=matter_id, snapshot_id=snapshot_id
    )
    return _to_checklist_read(view)


@router.post(
    "/matters/{matter_id}/checklist-items/{item_id}/decisions",
    response_model=ChecklistItemRead,
)
async def decide_satisfaction(
    matter_id: str,
    item_id: str,
    body: SatisfactionDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChecklistItemRead:
    """Record a decision. Waiving requires the narrower waive capability."""
    _ = uow
    capability = (
        CAP_CHECKLIST_WAIVE
        if body.applicability
        in {
            ApplicabilityStatus.WAIVED_BY_LAWYER.value,
            ApplicabilityStatus.NOT_APPLICABLE.value,
        }
        else CAP_CHECKLIST_DECIDE
    )
    await _authorized_matter(ctx, matter_id, session, capability)
    await service.lock_item(ctx.actor_id, matter_id, item_id)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/checklist-items/{item_id}/decisions",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(ChecklistItemRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    view = await service.decide_satisfaction(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        item_id=item_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        applicability=_enum(body.applicability, ApplicabilityStatus, "applicability"),
        collection=_enum(body.collection, CollectionStatus, "collection"),
        digital_review=_enum(body.digital_review, DigitalReviewStatus, "digitalReview"),
        currency=_enum(body.currency, CurrencyStatus, "currency"),
        consistency=_enum(body.consistency, ConsistencyStatus, "consistency"),
        resolution=_enum(body.resolution, ResolutionStatus, "resolution"),
        reason=body.reason,
        assigned_to=body.assigned_to,
    )
    response.headers["ETag"] = f'"{view.item.version}"'
    return await replay.save(_to_item_read(view))


@router.post(
    "/matters/{matter_id}/checklist-items/{item_id}/original-inspection",
    response_model=ChecklistItemRead,
)
async def record_original_inspection(
    matter_id: str,
    item_id: str,
    body: OriginalInspectionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChecklistItemRead:
    """Human-only. The reviewer is the authenticated actor, never the body."""
    _ = uow
    await _authorized_matter(ctx, matter_id, session, CAP_ORIGINAL_INSPECT)
    await service.lock_item(ctx.actor_id, matter_id, item_id)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/checklist-items/{item_id}/original-inspection",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(ChecklistItemRead)
    if cached:
        response.headers["ETag"] = f'"{cached.version}"'
        return cached
    view = await service.record_original_inspection(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        item_id=item_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        method=body.method,
        location=body.location,
        note=body.note,
    )
    response.headers["ETag"] = f'"{view.item.version}"'
    return await replay.save(_to_item_read(view))


@router.post(
    "/matters/{matter_id}/checklist-items/{item_id}/links",
    response_model=SatisfactionLinkRead,
    status_code=201,
)
async def link_document(
    matter_id: str,
    item_id: str,
    body: LinkDocumentRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SatisfactionLinkRead:
    """Link one document to one item; call once per item it satisfies."""
    _ = uow
    await _authorized_matter(ctx, matter_id, session, CAP_CHECKLIST_DECIDE)
    await service.lock_item(ctx.actor_id, matter_id, item_id)
    replay = RequirementCommandReplay(
        session,
        ctx.actor_id,
        f"/matters/{matter_id}/checklist-items/{item_id}/links",
        key,
        {**body.model_dump(mode="json"), "expectedVersion": expected_version},
    )
    cached = await replay.find(SatisfactionLinkRead)
    if cached:
        return cached
    link = await service.link_document(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        item_id=item_id,
        detected_document_id=body.detected_document_id,
        expected_version=expected_version,
        document_version=body.document_version,
        interpretation_generation=body.interpretation_generation,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        evidence_reference_ids=tuple(body.evidence_reference_ids),
        lawyer_confirmed=body.lawyer_confirmed,
        note=body.note,
    )
    return await replay.save(_to_link_read(link))


@router.get(
    "/matters/{matter_id}/checklist-items/{item_id}/links",
    response_model=list[SatisfactionLinkRead],
)
async def list_links(
    matter_id: str,
    item_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: ChecklistService = Depends(get_checklist_service),
    session: AsyncSession = Depends(get_db),
) -> list[SatisfactionLinkRead]:
    """Superseded links are returned too: replacement never erases history."""
    await _authorized_matter(ctx, matter_id, session, CAP_CHECKLIST_DECIDE)
    view = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter_id)
    if not any(item.item.id == item_id for item in view.items):
        raise MatterNotFoundError()
    links = await service.list_links(user_id=ctx.actor_id, item_id=item_id)
    return [_to_link_read(link) for link in links]
