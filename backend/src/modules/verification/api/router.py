"""Read API for the lawyer-approved structured matter record."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.content_governance.contracts import CAP_AUDIT_READ, get_fact_type
from src.modules.document.contracts import FactEvidenceLocator
from src.modules.matter.contracts import require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.modules.verification.api.schemas import (
    BoundingBoxRead,
    FactDecisionRead,
    FactEvidenceRead,
    FactHistoryRead,
    FactListRead,
    FactRead,
    ManualFactRequest,
    ReviewFactRequest,
)
from src.modules.verification.application.fact_query_service import FactQueryService, FactView
from src.modules.verification.application.review_service import (
    FactReviewService,
    ManualFactInput,
    RegisterFactView,
    ReviewFactInput,
)
from src.platform.api.pagination import PageInfo, decode_cursor, encode_cursor
from src.platform.db.idempotency import IdempotencyKeyRequiredError
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["facts"])


def get_fact_query_service(session: AsyncSession = Depends(get_db)) -> FactQueryService:
    from src.bootstrap import build_fact_query_service

    return build_fact_query_service(session)


async def _authorize(ctx: RequestContext, matter_id: str, session: AsyncSession) -> None:
    from src.bootstrap import build_matter_service

    matter = await build_matter_service(session).get_access_summary(ctx.actor_id, matter_id)
    if matter is None:
        raise MatterNotFoundError()
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=matter,
        capability=CAP_AUDIT_READ,
    )


def _to_fact_read(view: FactView | RegisterFactView) -> FactRead:
    fact = view.fact
    definition = get_fact_type(fact.fact_type_id)
    return FactRead(
        id=fact.id,
        matter_id=fact.matter_id,
        fact_type_id=fact.fact_type_id,
        field_key=definition.field_key if definition else None,
        label_key=definition.label_key if definition else fact.fact_type_id,
        value=fact.value,
        status=fact.status,
        model_reported_confidence=fact.model_reported_confidence,
        evidence=[
            FactEvidenceRead(
                id=reference.id,
                source_file_id=reference.source_file_id,
                detected_document_id=reference.detected_document_id,
                page_number=reference.page_number,
                source_sha256=reference.source_sha256,
                extraction_run_id=reference.extraction_run_id,
                supporting_text=reference.text_span,
                page_text=reference.page_text,
                candidate_id=reference.candidate_id,
                candidate_version=reference.candidate_version,
                precision=cast(Literal["page", "text"], reference.precision),
                bounding_box=(
                    BoundingBoxRead(
                        x=reference.bounding_box.x,
                        y=reference.bounding_box.y,
                        width=reference.bounding_box.width,
                        height=reference.bounding_box.height,
                        coordinate_space=reference.bounding_box.coordinate_space,
                    )
                    if reference.bounding_box
                    else None
                ),
            )
            for reference in view.evidence
        ],
        reviewed_by=fact.reviewed_by,
        reviewed_at=fact.reviewed_at.isoformat() if fact.reviewed_at else None,
        version=fact.version,
        created_at=fact.created_at.isoformat(),
        original_value=fact.original_value,
        origin=cast(Literal["legacy", "machine", "lawyer"], fact.origin),
        transaction_id=fact.transaction_id,
        subject_id=fact.subject_id,
        scope_status=cast(
            Literal["legacy-unassigned", "unassigned", "assigned"], fact.scope_status
        ),
        evidence_stale=fact.evidence_stale,
        source_candidate_id=fact.source_candidate_id,
        manual_reason=fact.manual_reason,
        lineage_id=fact.lineage_id,
        supersedes_fact_id=fact.supersedes_fact_id,
        superseded_by_fact_id=fact.superseded_by_fact_id,
        scope_token=view.scope_token if isinstance(view, RegisterFactView) else None,
        conflict_fact_ids=list(view.conflict_fact_ids)
        if isinstance(view, RegisterFactView)
        else [],
    )


def get_fact_review_service(session: AsyncSession = Depends(get_db)) -> FactReviewService:
    from src.bootstrap import build_fact_review_service

    return build_fact_review_service(session)


def require_review_key(
    key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
) -> str:
    if not key:
        raise IdempotencyKeyRequiredError()
    return key


@router.get("/matters/{matter_id}/facts", response_model=FactListRead)
async def list_facts(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: FactReviewService = Depends(get_fact_review_service),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> FactListRead:
    payload = decode_cursor(cursor) if cursor else {}
    facts, more = await service.list_facts(ctx, matter_id, limit=limit, after=payload.get("id"))
    return FactListRead(
        items=[_to_fact_read(fact) for fact in facts],
        page=PageInfo(
            limit=limit,
            has_more=more,
            next_cursor=encode_cursor({"id": facts[-1].fact.id}) if more and facts else None,
        ),
    )


@router.get("/matters/{matter_id}/facts/{fact_id}", response_model=FactRead)
async def get_fact(
    matter_id: str,
    fact_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: FactReviewService = Depends(get_fact_review_service),
) -> FactRead:
    view = await service.get_view(ctx, matter_id, fact_id)
    response.headers["ETag"] = f'"{view.fact.version}"'
    return _to_fact_read(view)


@router.post("/matters/{matter_id}/facts", response_model=FactRead, status_code=201)
async def add_manual_fact(
    matter_id: str,
    body: ManualFactRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: FactReviewService = Depends(get_fact_review_service),
    key: str = Depends(require_review_key),
    uow: UnitOfWork = Depends(get_uow),
) -> FactRead:
    _ = uow
    fact = await service.add_manual(
        ctx,
        matter_id,
        ManualFactInput(
            fact_type_id=body.fact_type_id,
            value=body.value,
            reason=body.reason,
            transaction_id=body.transaction_id,
            subject_id=body.subject_id,
            evidence=FactEvidenceLocator(**body.evidence.model_dump()) if body.evidence else None,
        ),
        key=key,
    )
    response.headers["ETag"] = f'"{fact.version}"'
    return _to_fact_read(await service.get_view(ctx, matter_id, fact.id))


@router.post("/matters/{matter_id}/facts/{fact_id}/{action}", response_model=FactRead)
async def decide_fact(
    matter_id: str,
    fact_id: str,
    action: Literal["accept", "correct", "reject", "associate"],
    body: ReviewFactRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: FactReviewService = Depends(get_fact_review_service),
    expected_version: int = Depends(require_if_match),
    key: str = Depends(require_review_key),
    uow: UnitOfWork = Depends(get_uow),
) -> FactRead:
    """Review an existing scope; only associate accepts transactionId/subjectId.

    Associate first, then accept the returned successor with its ETag and
    scopeToken. Other actions reject scope fields, including explicit nulls.
    """
    _ = uow
    if action != "associate" and {"transaction_id", "subject_id"} & body.model_fields_set:
        raise DomainRuleError("Scope fields are allowed only for associate decisions.")
    fact = await service.decide(
        ctx,
        matter_id,
        fact_id,
        ReviewFactInput(
            action=action,
            expected_version=expected_version,
            reason=body.reason,
            value=body.value,
            transaction_id=body.transaction_id,
            subject_id=body.subject_id,
            expected_scope_token=body.expected_scope_token,
            resolve_fact_ids=tuple(body.resolve_fact_ids),
            evidence=FactEvidenceLocator(**body.evidence.model_dump()) if body.evidence else None,
        ),
        key=key,
    )
    response.headers["ETag"] = f'"{fact.version}"'
    return _to_fact_read(await service.get_view(ctx, matter_id, fact.id))


@router.get("/matters/{matter_id}/facts/{fact_id}/history", response_model=FactHistoryRead)
async def fact_history(
    matter_id: str,
    fact_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: FactReviewService = Depends(get_fact_review_service),
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = None,
) -> FactHistoryRead:
    payload = decode_cursor(cursor) if cursor else {}
    history = await service.history(ctx, matter_id, fact_id, limit=limit, after=payload.get("id"))
    items = [
        _to_fact_read(await service.get_view(ctx, matter_id, fact.id)) for fact in history.facts
    ]
    decisions = [
        FactDecisionRead(
            id=d.id,
            target_id=d.target_id,
            decision=d.decision,
            reviewer_id=d.reviewer_id,
            reviewer_role=d.reviewer_role,
            created_at=d.created_at.isoformat(),
            previous_value=d.previous_value,
            new_value=d.new_value,
            reason=d.reason,
            resolved_fact_ids=list(d.resolved_fact_ids),
        )
        for d in history.decisions
    ]
    return FactHistoryRead(
        items=items,
        decisions=decisions,
        page=PageInfo(
            limit=limit,
            has_more=history.has_more,
            next_cursor=encode_cursor({"id": history.facts[-1].id})
            if history.has_more and history.facts
            else None,
        ),
    )
