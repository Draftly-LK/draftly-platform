"""Atomic query metering/replay and privacy-safe audit, serialised before lookup."""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from weakref import WeakValueDictionary

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.billing.application.billing_service import BillingService
from src.modules.research.api.case_schemas import CaseSearchRead
from src.modules.research.domain.cases import CaseSearchResult
from src.platform.db.idempotency import RETENTION, IdempotencyKeyRow, SqlIdempotencyStore
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

ROUTE = "POST /api/v1/research/cases/search"
_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


class SqlCaseSearchOperations:
    def __init__(self, session: AsyncSession, billing: BillingService, audit: AuditPort) -> None:
        self.session = session
        self.billing = billing
        self.audit = audit
        self.store = SqlIdempotencyStore(session)

    @asynccontextmanager
    async def transaction(self, ctx: RequestContext, key: str) -> AsyncIterator[None]:
        lock_key = hashlib.sha256(f"{ctx.actor_id}:{ROUTE}:{key}".encode()).hexdigest()
        lock = _locks.setdefault(lock_key, asyncio.Lock())
        async with lock, UnitOfWork(self.session):
            if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
                await self.session.execute(
                    select(
                        func.pg_advisory_xact_lock(
                            func.hashtextextended("case-search:" + lock_key, 0)
                        )
                    )
                )
            yield

    async def require_feature(self, ctx: RequestContext) -> None:
        await self.billing.require_feature_or_raise(ctx.actor_id, "research.enabled")

    async def replay(
        self, ctx: RequestContext, key: str, fingerprint: str
    ) -> CaseSearchResult | None:
        # Retired rows must be removed under the same lock before creating a new
        # reservation/response; the shared store retains a uniqueness constraint.
        await self.session.execute(
            delete(IdempotencyKeyRow).where(
                IdempotencyKeyRow.user_id == ctx.actor_id,
                IdempotencyKeyRow.route == ROUTE,
                IdempotencyKeyRow.idempotency_key == key,
                IdempotencyKeyRow.created_at < datetime.now(UTC) - RETENTION,
            )
        )
        result = await self.store.find(
            user_id=ctx.actor_id, route=ROUTE, key=key, request_hash=fingerprint
        )
        return CaseSearchRead.model_validate(result).domain() if result is not None else None

    async def reserve(self, ctx: RequestContext, operation_id: str) -> str:
        reservation = await self.billing.reserve_usage(
            ctx.actor_id, "research_queries.monthly", 1, operation_id
        )
        return reservation.id

    async def finish(
        self,
        ctx: RequestContext,
        key: str,
        fingerprint: str,
        operation_id: str,
        reservation_id: str,
        result: CaseSearchResult,
    ) -> None:
        await self.billing.consume_usage(ctx.actor_id, reservation_id, 1)
        await self.store.store(
            record_id="idem_" + uuid.uuid4().hex,
            user_id=ctx.actor_id,
            route=ROUTE,
            key=key,
            request_hash=fingerprint,
            response=CaseSearchRead.model_validate(result).model_dump(by_alias=True),
        )
        await self.audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="research.cases-searched",
                target_type="case-search",
                target_id=operation_id,
                after_ref=result.corpus_version,
                reason=result.outcome,
                correlation_id=ctx.correlation_id,
            )
        )
