"""Private v1 service adapter. Invalid/unreachable corpus is never an empty list."""

from dataclasses import asdict
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from src.modules.library.api.case_schemas import CaseDetailRead, InternalCaseListRead
from src.modules.library.domain.cases import (
    CaseCorpusUnavailableError,
    CaseDetail,
    CaseFilters,
    CaseList,
)


class HttpCaseAdapter:
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

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.base_url:
            raise CaseCorpusUnavailableError()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.request(
                    method, self.base_url + "/v1/cases" + path, **kwargs
                )
            if response.status_code != 404:
                response.raise_for_status()
            return response
        except (httpx.HTTPError, ValueError):
            raise CaseCorpusUnavailableError() from None

    async def list_cases(
        self,
        filters: CaseFilters,
        *,
        limit: int,
        after_id: str | None = None,
        after_year: int | None = None,
    ) -> CaseList:
        params = {key: value for key, value in asdict(filters).items() if value is not None}
        params["limit"] = limit
        if after_id is not None:
            params.update(after_id=after_id, after_year=after_year)
        response = await self.request("GET", "", params=params)
        try:
            result = InternalCaseListRead.model_validate(response.json())
            if (
                len(result.items) > limit
                or any(item.text is not None for item in result.items)
                or (result.has_more and not result.items)
            ):
                raise ValueError("Invalid page")
            return result.domain()
        except (ValidationError, ValueError):
            raise CaseCorpusUnavailableError() from None

    async def get_case(self, case_id: str, *, actor_id: str) -> CaseDetail | None:
        response = await self.request(
            "GET", "/" + quote(case_id, safe=""), headers={"X-Draftly-Actor": actor_id}
        )
        if response.status_code == 404:
            return None
        try:
            result = CaseDetailRead.model_validate(response.json())
            if result.item.id != case_id:
                raise ValueError("Record identity mismatch")
            return result.domain()
        except (ValidationError, ValueError):
            raise CaseCorpusUnavailableError() from None
