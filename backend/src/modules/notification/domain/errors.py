"""Notification errors — mapped to HTTP via platform/errors or subclasses."""

from __future__ import annotations

from src.platform.errors import DomainRuleError, NotFoundError


class NotificationNotFoundError(NotFoundError):
    message = "The requested notification was not found."


class PreferenceNotFoundError(NotFoundError):
    message = "Notification preferences were not found."


class PreferenceAccessDeniedError(NotFoundError):
    """Existence hiding when another user's preferences are requested."""

    message = "Notification preferences were not found."


class InvalidPreferencePatchError(DomainRuleError):
    code = "invalid_notification_preference"
    message = "The notification preference update is invalid."


class DuplicateDeliveryError(DomainRuleError):
    code = "duplicate_notification_delivery"
    message = "A delivery for this reminder and channel already exists."


class DeliveryNotFoundError(NotFoundError):
    message = "The requested delivery was not found."


class WebhookVerificationError(DomainRuleError):
    code = "webhook_verification_failed"
    http_status = 401
    message = "Provider webhook signature could not be verified."


class EmailSendingDisabledError(DomainRuleError):
    code = "email_sending_disabled"
    message = "Outbound provider email is disabled in this environment."


class DeliveryFailure(Exception):  # noqa: N818 — provider failure taxonomy, not HTTP errors
    """Base for channel failures. Carries a code, never a provider body."""

    def __init__(self, failure_code: str) -> None:
        self.failure_code = failure_code
        super().__init__(failure_code)


class RetryableDeliveryFailure(DeliveryFailure):
    """Timeout, rate limit, quota, or provider 5xx — back off and retry (§9)."""


class PermanentDeliveryFailure(DeliveryFailure):
    """Invalid or disabled address, or a rejected request — never retried (§9)."""


__all__ = [
    "DeliveryFailure",
    "DeliveryNotFoundError",
    "DuplicateDeliveryError",
    "EmailSendingDisabledError",
    "InvalidPreferencePatchError",
    "NotificationNotFoundError",
    "PermanentDeliveryFailure",
    "PreferenceAccessDeniedError",
    "PreferenceNotFoundError",
    "RetryableDeliveryFailure",
    "WebhookVerificationError",
]
