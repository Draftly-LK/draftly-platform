"""Research-owned adapter for the private, bounded case-search interface."""

import httpx
from pydantic import ValidationError

from src.modules.library.contracts import CaseCorpusUnavailableError
from src.modules.research.api.case_schemas import CaseSearchRead
from src.modules.research.domain.cases import CaseSearchResult


class HttpCaseSearchAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def search_cases(self, query: str, *, limit: int) -> CaseSearchResult:
        if not self.base_url:
            raise CaseCorpusUnavailableError()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    self.base_url + "/v1/cases/search", json={"query": query, "limit": limit}
                )
            response.raise_for_status()
            result = CaseSearchRead.model_validate(response.json())
            if len(result.items) > limit:
                raise ValueError("Search bound exceeded")
            return result.domain()
        except (httpx.HTTPError, ValidationError, ValueError):
            raise CaseCorpusUnavailableError() from None
