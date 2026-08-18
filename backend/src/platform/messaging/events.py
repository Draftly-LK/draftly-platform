"""Event envelope shared by every publisher (events.md §2).

Pure data: no FastAPI, no SQLAlchemy. Application services build an
``EventEnvelope`` and hand it to an ``EventPort``; only infrastructure knows
that publishing means writing an outbox row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EventEnvelope:
    """One domain event, ready for the outbox.

    ``organisation_id`` is the tenant boundary (security-model.md §2). V0 has no
    Organisation entity, so for user-scoped services it carries the owning
    ``user_id``.

    ``idempotency_key`` must be derived from the aggregate and its version so a
    redelivery — or a re-run of the same mutation — collapses to one row.
    """

    event_name: str
    organisation_id: str
    idempotency_key: str
    occurred_at: datetime
    data: dict[str, Any] = field(default_factory=dict)
    event_version: int = 1
    matter_id: str | None = None
    actor_id: str | None = None
    correlation_id: str = ""
    causation_id: str | None = None

    def to_payload(self, event_id: str) -> dict[str, Any]:
        """Return the wire envelope stored in the outbox payload column."""
        return {
            "eventId": event_id,
            "eventName": self.event_name,
            "eventVersion": self.event_version,
            "occurredAt": self.occurred_at.isoformat(),
            "organisationId": self.organisation_id,
            "matterId": self.matter_id,
            "actorId": self.actor_id,
            "correlationId": self.correlation_id,
            "causationId": self.causation_id,
            "idempotencyKey": self.idempotency_key,
            "data": self.data,
        }
