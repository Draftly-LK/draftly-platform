from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_request_context
from src.modules.library.api.schemas import LegalSourceListRead, LegalSourceRead
from src.modules.library.application.service import LibraryService
from src.modules.library.domain.models import LegalSourceSummary
from src.modules.library.infrastructure import SqliteLegalCatalogue
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/library", tags=["library"])


def get_service() -> LibraryService:
    return LibraryService(SqliteLegalCatalogue())


def _read(source: LegalSourceSummary) -> LegalSourceRead:
    return LegalSourceRead.model_validate(source, from_attributes=True)


@router.get("", response_model=LegalSourceListRead)
async def browse_library(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[LibraryService, Depends(get_service)],
    authority_type: Annotated[
        Literal["statute", "amendment", "gazette"] | None, Query(alias="type")
    ] = None,
    query: Annotated[str | None, Query(max_length=256)] = None,
) -> LegalSourceListRead:
    rows = await service.browse(ctx, authority_type, query)
    return LegalSourceListRead(items=[_read(row) for row in rows], total=len(rows))


@router.get("/{authority_id}", response_model=LegalSourceRead)
async def get_authority(
    authority_id: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[LibraryService, Depends(get_service)],
) -> LegalSourceRead:
    return _read(await service.get_authority(ctx, authority_id))
