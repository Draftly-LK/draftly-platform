"""Audit application service — implements AuditPort.

record() is called inside the same database transaction as the mutation it
records. A missing audit event is a release-blocker (audit-service.md §9.2).

Hash chaining (audit-service.md §3.3): each event stores prevHash and
hash over its own canonical serialisation + prevHash. A retroactive edit
breaks the chain from that point.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.chain import event_hash
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.ports import AuditEventInput

log = structlog.get_logger(__name__)


class AuditService:
    """Implements AuditPort. Requires a per-request SqlAuditRepository."""

    def __init__(self, *, repository: SqlAuditRepository) -> None:
        self._repo = repository

    async def record(self, event: AuditEventInput) -> None:
        """Append an audit event in the current transaction with hash chaining."""
        event_id = f"ae_{uuid.uuid4().hex}"
        now = datetime.now(tz=UTC)

        prev_hash = await self._repo.get_last_hash(event.user_id)

        event_hash_ = event_hash(
            event_id=event_id,
            user_id=event.user_id,
            matter_id=event.matter_id,
            actor=event.actor,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            before_ref=event.before_ref,
            after_ref=event.after_ref,
            reason=event.reason,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            timestamp=now,
            prev_hash=prev_hash,
        )

        await self._repo.insert(
            event_id=event_id,
            user_id=event.user_id,
            matter_id=event.matter_id,
            actor=event.actor,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            before_ref=event.before_ref,
            after_ref=event.after_ref,
            reason=event.reason,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            prev_hash=prev_hash,
            hash_=event_hash_,
            timestamp=now,
        )
        log.debug(
            "audit.recorded",
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            user_id=event.user_id,
        )
