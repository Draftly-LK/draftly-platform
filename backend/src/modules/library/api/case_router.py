from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_request_context
from src.modules.library.api.case_schemas import (
    CaseCoverageRead,
    CaseDetailRead,
    CaseListRead,
    CaseRecordRead,
)
from src.modules.library.application.cases import CaseLibraryService
from src.modules.library.domain.cases import CaseFilters
from src.modules.library.infrastructure.case_http import HttpCaseAdapter
from src.platform.config import get_settings
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/library/cases", tags=["library"])


def get_case_library_service() -> CaseLibraryService:
    return CaseLibraryService(HttpCaseAdapter(base_url=get_settings().retrieval_base_url))


@router.get("", response_model=CaseListRead)
async def browse_cases(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[CaseLibraryService, Depends(get_case_library_service)],
    query: Annotated[str | None, Query(max_length=256)] = None,
    collection: Literal["LKCA", "LKSC"] | None = None,
    court: Annotated[str | None, Query(max_length=128)] = None,
    year: Annotated[int | None, Query(ge=1700, le=2200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> CaseListRead:
    rows, page = await service.browse(
        ctx, CaseFilters(query, collection, court, year), limit=limit, cursor=cursor
    )
    return CaseListRead(
        corpus_version=rows.corpus_version,
        coverage=CaseCoverageRead.model_validate(rows.coverage),
        items=[CaseRecordRead.model_validate(row) for row in rows.items],
        page=page,
    )


@router.get("/{case_id}", response_model=CaseDetailRead)
async def read_case(
    case_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[CaseLibraryService, Depends(get_case_library_service)],
) -> CaseDetailRead:
    return CaseDetailRead.model_validate(await service.detail(ctx, case_id))
