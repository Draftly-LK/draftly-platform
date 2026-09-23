from __future__ import annotations

from typing import Protocol

from src.modules.library.domain.models import AuthorityType, LegalSourceSummary


class LegalCataloguePort(Protocol):
    async def list_authorities(
        self, authority_type: AuthorityType | None = None, query: str | None = None
    ) -> list[LegalSourceSummary]: ...

    async def get_authority(self, authority_id: str) -> LegalSourceSummary | None: ...
