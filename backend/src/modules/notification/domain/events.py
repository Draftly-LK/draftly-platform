"""Inbound event interpretation for the idempotent consumer.

Turns a validated envelope (events.md §2) into the identifier-only trigger the
application service acts on. Pure domain: no FastAPI, SQLAlchemy, or provider
imports, and nothing here reads a repository.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.notification.domain.policies import (
    TERMINAL_ONLY_EVENTS,
    delivery_policy_key_for,
    is_restricted,
    template_key_for,
)
from src.platform.messaging.envelope import EventEnvelope

# Identifier keys that can stand as the notification subject, most specific first.
_SUBJECT_KEYS = (
    "obligationId",
    "documentVersionId",
    "documentId",
    "instrumentId",
    "exportId",
    "draftVersionId",
    "approvalId",
    "stepRunId",
    "subscriptionId",
    "invitationId",
    "partyId",
    "checkId",
    "userId",
)

# Keys that distinguish two notifications about the same subject.
_DISCRIMINATOR_KEYS = (
    "reminderType",
    "escalationLevel",
    "changeKind",
    "afterStatus",
    "failureCode",
    "outcome",
)


class UnroutableEventError(ValueError):
    """The event is registered but this service has no template route for it."""


class SuppressedByPolicyError(ValueError):
    """The event is routed but policy says not to notify for this instance."""


@dataclass(frozen=True)
class NotificationTrigger:
    """Identifier-only instruction to create deliveries for one event."""

    event_id: str
    event_name: str
    organisation_id: str
    recipient_user_id: str
    subject_ref: str
    reminder_type: str
    template_key: str
    delivery_policy_key: str
    obligation_class: str
    urgency: str
    confidentiality_level: str
    correlation_id: str
    matter_id: str | None = None
    obligation_id: str | None = None
    due_at: str | None = None

    @property
    def restricted(self) -> bool:
        return is_restricted(self.confidentiality_level)


def _string_field(envelope: EventEnvelope, key: str) -> str | None:
    value = envelope.data.get(key)
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def trigger_from_envelope(envelope: EventEnvelope) -> NotificationTrigger:
    """Build a trigger, or refuse the event.

    Raises UnroutableEventError when no template is registered for the event and
    SuppressedByPolicyError when policy says this instance must not notify (a
    non-terminal processing failure, for example).
    """
    confidentiality_level = _string_field(envelope, "confidentialityLevel") or "private-matter"
    template_key = template_key_for(
        envelope.event_name, confidentiality_level=confidentiality_level
    )
    if template_key is None:
        raise UnroutableEventError(envelope.event_name)

    if envelope.event_name in TERMINAL_ONLY_EVENTS and envelope.data.get("terminal") is not True:
        raise SuppressedByPolicyError(f"{envelope.event_name} is not terminal")

    # The recipient is named by the publisher or, in the V0 single-practitioner
    # model, is the organisation owner. A caller never supplies a recipient and
    # no address is ever taken from the event.
    recipient_user_id = _string_field(envelope, "recipientUserId") or envelope.organisation_id

    subject_ref = next(
        (value for key in _SUBJECT_KEYS if (value := _string_field(envelope, key))),
        envelope.matter_id or envelope.event_id,
    )

    discriminator = next(
        (value for key in _DISCRIMINATOR_KEYS if (value := _string_field(envelope, key))),
        None,
    )
    reminder_type = _string_field(envelope, "reminderType") or (
        f"{envelope.event_name}:{discriminator}" if discriminator else envelope.event_name
    )

    return NotificationTrigger(
        event_id=envelope.event_id,
        event_name=envelope.event_name,
        organisation_id=envelope.organisation_id,
        recipient_user_id=recipient_user_id,
        subject_ref=subject_ref,
        reminder_type=reminder_type,
        template_key=template_key,
        delivery_policy_key=delivery_policy_key_for(
            envelope.event_name, confidentiality_level=confidentiality_level
        ),
        obligation_class=_string_field(envelope, "class")
        or _string_field(envelope, "obligationClass")
        or envelope.aggregate,
        urgency=_string_field(envelope, "urgency") or "normal",
        confidentiality_level=confidentiality_level,
        correlation_id=envelope.correlation_id,
        matter_id=envelope.matter_id or _string_field(envelope, "matterId"),
        obligation_id=_string_field(envelope, "obligationId"),
        due_at=_string_field(envelope, "dueAt"),
    )


__all__ = [
    "NotificationTrigger",
    "SuppressedByPolicyError",
    "UnroutableEventError",
    "trigger_from_envelope",
]
