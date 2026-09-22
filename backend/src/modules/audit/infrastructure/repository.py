"""SQLAlchemy repository for audit events — insert-only, no update or delete.

get_last_hash() reads the most recent event in the user's chain so that
insert() can compute the prevHash for chaining.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.infrastructure.orm import AuditEventRow


class SqlAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last_hash(self, user_id: str) -> str:
        """Return the hash of the most recent event in this user's audit chain.

        On Postgres, first take this user's chain lock for the rest of the
        transaction. Without it, two transactions recording for one user both
        read the same last hash and the chain forks into two branches. The
        lock is per user, so one account's volume never serialises another's
        (audit-service.md §3.3).
        """
        bind = self._session.bind
        if bind is not None and bind.dialect.name == "postgresql":
            await self._session.execute(
                select(func.pg_advisory_xact_lock(func.hashtextextended(f"audit:{user_id}", 0)))
            )
        stmt = (
            select(AuditEventRow.hash)
            .where(AuditEventRow.user_id == user_id)
            .order_by(AuditEventRow.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row or ""

    async def insert(
        self,
        *,
        event_id: str,
        user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        hash_: str,
        prev_hash: str,
        timestamp: datetime,
        matter_id: str | None = None,
        actor: str | None = None,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
        correlation_id: str = "",
        causation_id: str | None = None,
    ) -> None:
        """Append an audit event — no update or delete is allowed (insert-only)."""
        row = AuditEventRow(
            id=event_id,
            user_id=user_id,
            matter_id=matter_id,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_ref=before_ref,
            after_ref=after_ref,
            reason=reason,
            correlation_id=correlation_id,
            causation_id=causation_id,
            prev_hash=prev_hash,
            hash=hash_,
            timestamp=timestamp,
        )
        self._session.add(row)
        await self._session.flush()
