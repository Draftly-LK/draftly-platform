"""Audit application service — implements AuditPort.

record() is called inside the same database transaction as the mutation it
records. A missing audit event is a release-blocker (audit-service.md §9.2).

Hash chaining (audit-service.md §3.3): each event stores prevHash and
hash over its own canonical serialisation + prevHash. A retroactive edit
breaks the chain from that point.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import structlog

from src.modules.auth.ports import AuditEventInput
from src.modules.audit.infrastructure.repository import SqlAuditRepository

log = structlog.get_logger(__name__)


class AuditService:
    """Implements AuditPort. Requires a per-request SqlAuditRepository."""

    def __init__(self, *, repository: SqlAuditRepository) -> None:
        self._repo = repository

    async def record(self, event: AuditEventInput) -> None:
        """Append an audit event in the current transaction with hash chaining."""
        event_id = f"ae_{uuid.uuid4().hex}"
        now = datetime.now(tz=timezone.utc)

        # Retrieve prev_hash for this organisation's chain
        prev_hash = await self._repo.get_last_hash(event.organisation_id)

        # Compute hash: SHA-256 over canonical JSON + prevHash
        canonical = json.dumps(
            {
                "id": event_id,
                "org": event.organisation_id,
                "action": event.action,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "timestamp": now.isoformat(),
                "prev_hash": prev_hash,
            },
            sort_keys=True,
        )
        event_hash = hashlib.sha256(canonical.encode()).hexdigest()[:64]

        await self._repo.insert(
            event_id=event_id,
            organisation_id=event.organisation_id,
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
            hash_=event_hash,
            timestamp=now,
        )
        log.debug(
            "audit.recorded",
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            organisation_id=event.organisation_id,
        )
