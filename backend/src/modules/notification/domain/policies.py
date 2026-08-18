"""Delivery routing, restricted-compliance policy, and failure classification.

Pure domain rules (notification-service.md §6.2, §8.2, §9). No FastAPI,
SQLAlchemy, or provider imports.
"""

from __future__ import annotations

from enum import Enum

from src.modules.notification.domain.models import NotificationChannel

RESTRICTED_CONFIDENTIALITY = "restricted-compliance"
RESTRICTED_TEMPLATE_KEY = "restricted.action_required"
RESTRICTED_DELIVERY_POLICY_KEY = "restricted-compliance.neutral"

# Every event in contracts/services.yaml `notification_service.consumes`, routed
# to a template key in domain/templates.py. A consumed event with no route would
# silently never notify, so parity is asserted in tests/contract.
EVENT_TEMPLATE_ROUTES: dict[str, str] = {
    "obligation.reminder-due": "obligation.reminder.due",
    "obligation.escalated": "obligation.escalated",
    "obligation.deadline-confirmed": "obligation.deadline_changed",
    "obligation.deadline-corrected": "obligation.deadline_changed",
    "matter.membership-changed": "matter.assignment_changed",
    "matter.assigned-notary-changed": "matter.assignment_changed",
    "workflow.review-requested": "review.requested",
    "workflow.setup-failed": "workflow.setup_failed",
    "workflow.signing-scheduled": "workflow.signing_scheduled",
    "document.processing-failed": "document.processing_failed",
    "document.replaced": "document.replacement_ready",
    "instrument.collection-ready": "instrument.collection_ready",
    "draft.review-requested": "review.requested",
    "draft.approved": "draft.approved",
    "draft.approval-invalidated": "draft.approval_invalidated",
    "export.rendered": "export.ready",
    "export.failed": "export.failed",
    "user.invited": "user.invited",
    "user.activated": "account.status_changed",
    "user.suspended": "account.status_changed",
    "party.designated-person-confirmed": RESTRICTED_TEMPLATE_KEY,
    "billing.trial-ending": "billing.notice",
    "billing.payment-failed": "billing.notice",
    "billing.grace-period-ending": "billing.notice",
    "billing.plan-changed": "billing.notice",
    "billing.subscription-cancelled": "billing.notice",
    "billing.subscription-restricted": "billing.notice",
}

# Events whose payload carries `terminal`; only the terminal case notifies
# (events.md §5.4, §5.10).
TERMINAL_ONLY_EVENTS = frozenset({"document.processing-failed", "export.failed"})

DELIVERY_CHANNELS = (NotificationChannel.EMAIL, NotificationChannel.IN_APP)


class FailureClass(str, Enum):
    """How a delivery failure is handled (notification-service.md §9)."""

    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    DEAD_LETTER = "dead-letter"


RETRYABLE_FAILURE_CODES = frozenset(
    {
        "provider_timeout",
        "provider_rate_limited",
        "provider_unavailable",
        "provider_server_error",
        "provider_quota_exceeded",
        "transient_error",
    }
)

PERMANENT_FAILURE_CODES = frozenset(
    {
        "recipient_address_missing",
        "recipient_address_invalid",
        "recipient_address_suppressed",
        "provider_rejected_request",
        "recipient_not_permitted",
    }
)

DEAD_LETTER_FAILURE_CODES = frozenset(
    {
        "template_missing",
        "template_not_approved",
        "template_not_published",
        "template_variables_invalid",
    }
)


def classify_failure(failure_code: str) -> FailureClass:
    """Classify a failure code; an unrecognised code is never silently retried."""
    if failure_code in RETRYABLE_FAILURE_CODES:
        return FailureClass.RETRYABLE
    if failure_code in DEAD_LETTER_FAILURE_CODES:
        return FailureClass.DEAD_LETTER
    if failure_code in PERMANENT_FAILURE_CODES:
        return FailureClass.PERMANENT
    return FailureClass.PERMANENT


def is_restricted(confidentiality_level: str | None) -> bool:
    return confidentiality_level == RESTRICTED_CONFIDENTIALITY


def template_key_for(event_name: str, *, confidentiality_level: str | None) -> str | None:
    """Route an event to its template. Restricted confidentiality always wins."""
    if is_restricted(confidentiality_level):
        return RESTRICTED_TEMPLATE_KEY
    return EVENT_TEMPLATE_ROUTES.get(event_name)


def delivery_policy_key_for(event_name: str, *, confidentiality_level: str | None) -> str:
    if is_restricted(confidentiality_level):
        return RESTRICTED_DELIVERY_POLICY_KEY
    return f"{event_name}.standard"


__all__ = [
    "DEAD_LETTER_FAILURE_CODES",
    "DELIVERY_CHANNELS",
    "EVENT_TEMPLATE_ROUTES",
    "PERMANENT_FAILURE_CODES",
    "RESTRICTED_CONFIDENTIALITY",
    "RESTRICTED_DELIVERY_POLICY_KEY",
    "RESTRICTED_TEMPLATE_KEY",
    "RETRYABLE_FAILURE_CODES",
    "TERMINAL_ONLY_EVENTS",
    "FailureClass",
    "classify_failure",
    "delivery_policy_key_for",
    "is_restricted",
    "template_key_for",
]
