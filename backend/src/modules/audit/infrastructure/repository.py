"""SQLAlchemy repository for audit events — insert-only, no update or delete.

get_last_hash() reads the most recent event in the organisation's chain
so that insert() can compute the prevHash for chaining.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.infrastructure.orm import AuditEventRow


class SqlAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last_hash(self, organisation_id: str) -> str:
        """Return the hash of the most recent event in this org's audit chain."""
        stmt = (
            select(AuditEventRow.hash)
            .where(AuditEventRow.organisation_id == organisation_id)
            .order_by(AuditEventRow.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row or ""  # empty string for the genesis event

    async def insert(
        self,
        *,
        event_id: str,
        organisation_id: str,
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
            organisation_id=organisation_id,
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
