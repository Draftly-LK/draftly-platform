from __future__ import annotations

from src.modules.library.domain.models import AuthorityType, LegalSourceSummary
from src.modules.library.ports import LegalCataloguePort
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext


class LibraryService:
    def __init__(self, catalogue: LegalCataloguePort) -> None:
        self.catalogue = catalogue

    async def browse(
        self,
        ctx: RequestContext,
        authority_type: AuthorityType | None = None,
        query: str | None = None,
    ) -> list[LegalSourceSummary]:
        del ctx
        return await self.catalogue.list_authorities(authority_type, query)

    async def get_authority(self, ctx: RequestContext, authority_id: str) -> LegalSourceSummary:
        del ctx
        authority = await self.catalogue.get_authority(authority_id)
        if authority is None:
            raise NotFoundError()
        return authority
