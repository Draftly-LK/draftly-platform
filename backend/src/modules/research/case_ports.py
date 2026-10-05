from contextlib import AbstractAsyncContextManager
from typing import Protocol

from src.modules.research.domain.cases import CaseSearchResult
from src.platform.request_context import RequestContext


class CaseSearchPort(Protocol):
    async def search_cases(self, query: str, *, limit: int) -> CaseSearchResult: ...


class CaseSearchOperationsPort(Protocol):
    def transaction(self, ctx: RequestContext, key: str) -> AbstractAsyncContextManager[None]: ...
    async def require_feature(self, ctx: RequestContext) -> None: ...
    async def replay(
        self, ctx: RequestContext, key: str, fingerprint: str
    ) -> CaseSearchResult | None: ...
    async def reserve(self, ctx: RequestContext, operation_id: str) -> str: ...
    async def finish(
        self,
        ctx: RequestContext,
        key: str,
        fingerprint: str,
        operation_id: str,
        reservation_id: str,
        result: CaseSearchResult,
    ) -> None: ...
