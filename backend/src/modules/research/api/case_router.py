from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_billing_service, get_request_context
from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.billing.application.billing_service import BillingService
from src.modules.research.api.case_schemas import CaseSearchRead, CaseSearchRequest
from src.modules.research.application.cases import CaseResearchService
from src.modules.research.infrastructure.case_operations import SqlCaseSearchOperations
from src.modules.research.infrastructure.retrieval.case_http import HttpCaseSearchAdapter
from src.platform.config import get_settings
from src.platform.db.session import get_db
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/research/cases", tags=["research"])


def get_case_research_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> CaseResearchService:
    return CaseResearchService(
        HttpCaseSearchAdapter(base_url=get_settings().retrieval_base_url),
        SqlCaseSearchOperations(
            session, billing, AuditService(repository=SqlAuditRepository(session))
        ),
    )


@router.post(
    "/search",
    response_model=CaseSearchRead,
    openapi_extra={
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string", "maxLength": 255},
            }
        ]
    },
)
async def search_cases(
    body: CaseSearchRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[CaseResearchService, Depends(get_case_research_service)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255, include_in_schema=False)
    ] = None,
) -> CaseSearchRead:
    return CaseSearchRead.model_validate(
        await service.search(ctx, body.query, limit=body.limit, key=idempotency_key)
    )
