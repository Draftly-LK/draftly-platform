from __future__ import annotations

from dataclasses import asdict

from src.modules.library.contracts import CaseCataloguePort
from src.modules.library.domain.cases import CaseDetail, CaseFilters, CaseList
from src.platform.api.pagination import InvalidCursorError, PageInfo, decode_cursor, encode_cursor
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext


class CaseLibraryService:
    def __init__(self, catalogue: CaseCataloguePort) -> None:
        self.catalogue = catalogue

    async def browse(
        self,
        ctx: RequestContext,
        filters: CaseFilters,
        *,
        limit: int = 25,
        cursor: str | None = None,
    ) -> tuple[CaseList, PageInfo]:
        scope = {"actor": ctx.actor_id, "filters": asdict(filters), "route": "library-cases-v1"}
        after_id, after_year, version = None, None, None
        if cursor:
            data = decode_cursor(cursor)
            if (
                data.get("scope") != scope
                or not isinstance(data.get("year"), int)
                or not isinstance(data.get("after"), str)
                or not isinstance(data.get("corpusVersion"), str)
            ):
                raise InvalidCursorError()
            after_id, after_year, version = data["after"], data["year"], data["corpusVersion"]
        rows = await self.catalogue.list_cases(
            filters, limit=limit, after_id=after_id, after_year=after_year
        )
        if version is not None and version != rows.corpus_version:
            raise InvalidCursorError()
        next_cursor = None
        if rows.has_more and rows.items:
            last = rows.items[-1]
            next_cursor = encode_cursor(
                {
                    "scope": scope,
                    "after": last.id,
                    "year": last.year,
                    "corpusVersion": rows.corpus_version,
                }
            )
        return rows, PageInfo(next_cursor=next_cursor, has_more=rows.has_more, limit=limit)

    async def detail(self, ctx: RequestContext, case_id: str) -> CaseDetail:
        record = await self.catalogue.get_case(case_id, actor_id=ctx.actor_id)
        if record is None:
            raise NotFoundError()
        return record
