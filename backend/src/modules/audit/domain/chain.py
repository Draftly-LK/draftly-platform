"""The per-user audit hash chain (audit-service.md §3.3).

Pure functions, so the writer and the verification sweep hash an event the
same way. Each event's ``hash`` covers its own canonical serialisation plus
``prev_hash``, the hash of the event before it in the same user's chain. An
out-of-band edit breaks the chain from that event on.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol


def event_hash(
    *,
    event_id: str,
    user_id: str,
    matter_id: str | None,
    actor: str | None,
    action: str,
    target_type: str,
    target_id: str,
    before_ref: str | None,
    after_ref: str | None,
    reason: str | None,
    correlation_id: str,
    causation_id: str | None,
    timestamp: datetime,
    prev_hash: str,
) -> str:
    """SHA-256 over the event's canonical JSON, prev_hash included.

    The timestamp is normalised to UTC, so a row read back through a session
    in another time zone hashes the same as when it was written.
    """
    canonical = json.dumps(
        {
            "id": event_id,
            "user": user_id,
            "matter_id": matter_id,
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "before_ref": before_ref,
            "after_ref": after_ref,
            "reason": reason,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "timestamp": timestamp.astimezone(UTC).isoformat(),
            "prev_hash": prev_hash,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class ChainedEvent(Protocol):
    id: str
    user_id: str
    matter_id: str | None
    actor: str | None
    action: str
    target_type: str
    target_id: str
    before_ref: str | None
    after_ref: str | None
    reason: str | None
    correlation_id: str
    causation_id: str | None
    timestamp: datetime
    prev_hash: str
    hash: str


def first_broken_link(chain: Sequence[ChainedEvent]) -> str | None:
    """The id of the first event that fails verification, or None if intact.

    ``chain`` is one user's events in chain order. An event fails when its
    stored hash does not recompute, or when its prev_hash is not the hash of
    the event before it (the first event links to "").
    """
    expected_prev = ""
    for event in chain:
        recomputed = event_hash(
            event_id=event.id,
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
            timestamp=event.timestamp,
            prev_hash=event.prev_hash,
        )
        if event.prev_hash != expected_prev or event.hash != recomputed:
            return event.id
        expected_prev = event.hash
    return None
