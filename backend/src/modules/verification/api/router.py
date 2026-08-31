"""Read API for the lawyer-approved structured matter record."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context
from src.modules.content_governance.contracts import CAP_AUDIT_READ, get_fact_type
from src.modules.matter.contracts import require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.modules.verification.api.schemas import (
    BoundingBoxRead,
    FactEvidenceRead,
    FactListRead,
    FactRead,
)
from src.modules.verification.application.fact_query_service import FactQueryService, FactView
from src.platform.db.session import get_db
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


def _to_fact_read(view: FactView) -> FactRead:
    fact = view.fact
    definition = get_fact_type(fact.fact_type_id)
    return FactRead(
        id=fact.id,
        matter_id=fact.matter_id,
        fact_type_id=fact.fact_type_id,
        field_key=definition.field_key if definition else None,
        label_key=definition.label_key if definition else fact.fact_type_id,
        value=fact.value,
        status=fact.status.value,
        model_reported_confidence=fact.model_reported_confidence,
        evidence=[
            FactEvidenceRead(
                id=reference.id,
                source_file_id=reference.source_file_id,
                detected_document_id=reference.detected_document_id,
                page_number=reference.page_number,
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
    )


@router.get("/matters/{matter_id}/facts", response_model=FactListRead)
async def list_facts(
    matter_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: FactQueryService = Depends(get_fact_query_service),
    session: AsyncSession = Depends(get_db),
) -> FactListRead:
    """Return every live fact in a matter, including unconfirmed states."""
    await _authorize(ctx, matter_id, session)
    facts = await service.list_facts(user_id=ctx.actor_id, matter_id=matter_id)
    return FactListRead(items=[_to_fact_read(fact) for fact in facts])
