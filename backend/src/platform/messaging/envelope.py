"""Event envelope shared by every publisher and consumer (events.md §2).

Pure data and validation: no FastAPI, SQLAlchemy, or provider imports, so domain
and application layers may depend on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z-]*\.[a-z][a-z0-9-]*$")

REGISTERED_AGGREGATES = frozenset(
    {
        "user",
        "organisation",
        "matter",
        "party",
        "document",
        "instrument",
        "particular",
        "check",
        "finding",
        "workflow",
        "obligation",
        "draft",
        "export",
        "corpus",
        "content",
        "assistant",
        "agent",
        "memory",
        "voice",
        "retention",
        "notification",
        "billing",
        "register",
    }
)


class InvalidEnvelopeError(ValueError):
    """The inbound payload is not a valid registered event envelope."""


@dataclass(frozen=True)
class EventEnvelope:
    """A validated inbound or outbound event (events.md §2)."""

    event_id: str
    event_name: str
    event_version: int
    occurred_at: datetime
    organisation_id: str
    correlation_id: str
    idempotency_key: str
    data: dict[str, Any] = field(default_factory=dict)
    matter_id: str | None = None
    actor_id: str | None = None
    causation_id: str | None = None

    @property
    def aggregate(self) -> str:
        return self.event_name.split(".", 1)[0]

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventName": self.event_name,
            "eventVersion": self.event_version,
            "occurredAt": self.occurred_at.isoformat(),
            "organisationId": self.organisation_id,
            "matterId": self.matter_id,
            "actorId": self.actor_id,
            "correlationId": self.correlation_id,
            "causationId": self.causation_id,
            "idempotencyKey": self.idempotency_key,
            "data": dict(self.data),
        }


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidEnvelopeError(f"envelope field '{key}' is required")
    return value


def parse_envelope(payload: dict[str, Any]) -> EventEnvelope:
    """Validate an inbound event payload, or raise InvalidEnvelopeError.

    A consumer that cannot trust the envelope must dead-letter rather than guess,
    so every required identifier is checked here and nothing is defaulted.
    """
    event_id = _require_str(payload, "eventId")
    event_name = _require_str(payload, "eventName")
    if not EVENT_NAME_PATTERN.match(event_name):
        raise InvalidEnvelopeError(f"event name '{event_name}' is not a registry name")
    if event_name.split(".", 1)[0] not in REGISTERED_AGGREGATES:
        raise InvalidEnvelopeError(f"event name '{event_name}' has an unregistered aggregate")

    organisation_id = _require_str(payload, "organisationId")
    correlation_id = _require_str(payload, "correlationId")

    raw_version = payload.get("eventVersion", 1)
    if not isinstance(raw_version, int) or isinstance(raw_version, bool) or raw_version < 1:
        raise InvalidEnvelopeError("envelope field 'eventVersion' must be a positive integer")

    raw_occurred_at = _require_str(payload, "occurredAt")
    try:
        occurred_at = datetime.fromisoformat(raw_occurred_at)
    except ValueError as exc:
        raise InvalidEnvelopeError("envelope field 'occurredAt' is not ISO-8601") from exc

    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise InvalidEnvelopeError("envelope field 'data' must be an object")

    matter_id = payload.get("matterId")
    actor_id = payload.get("actorId")
    causation_id = payload.get("causationId")
    for optional_key, optional_value in (
        ("matterId", matter_id),
        ("actorId", actor_id),
        ("causationId", causation_id),
    ):
        if optional_value is not None and not isinstance(optional_value, str):
            raise InvalidEnvelopeError(f"envelope field '{optional_key}' must be a string or null")

    idempotency_key = payload.get("idempotencyKey")
    if idempotency_key is not None and not isinstance(idempotency_key, str):
        raise InvalidEnvelopeError("envelope field 'idempotencyKey' must be a string")

    return EventEnvelope(
        event_id=event_id,
        event_name=event_name,
        event_version=raw_version,
        occurred_at=occurred_at,
        organisation_id=organisation_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key or event_id,
        data=dict(data),
        matter_id=matter_id,
        actor_id=actor_id,
        causation_id=causation_id,
    )


__all__ = [
    "EVENT_NAME_PATTERN",
    "REGISTERED_AGGREGATES",
    "EventEnvelope",
    "InvalidEnvelopeError",
    "parse_envelope",
]
