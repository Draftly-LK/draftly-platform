import uuid

from src.modules.research.case_ports import CaseSearchOperationsPort, CaseSearchPort
from src.modules.research.domain.cases import CaseSearchResult
from src.platform.db.idempotency import IdempotencyKeyRequiredError, request_fingerprint
from src.platform.request_context import RequestContext


class CaseResearchService:
    def __init__(self, retrieval: CaseSearchPort, operations: CaseSearchOperationsPort) -> None:
        self.retrieval = retrieval
        self.operations = operations

    async def search(
        self, ctx: RequestContext, query: str, *, limit: int = 8, key: str | None = None
    ) -> CaseSearchResult:
        if not key:
            raise IdempotencyKeyRequiredError()
        fingerprint = request_fingerprint({"query": query, "limit": limit})
        async with self.operations.transaction(ctx, key):
            await self.operations.require_feature(ctx)
            replay = await self.operations.replay(ctx, key, fingerprint)
            if replay is not None:
                return replay
            operation_id = "case-search:" + uuid.uuid4().hex
            reservation_id = await self.operations.reserve(ctx, operation_id)
            result = await self.retrieval.search_cases(query, limit=limit)
            await self.operations.finish(
                ctx, key, fingerprint, operation_id, reservation_id, result
            )
            return result
