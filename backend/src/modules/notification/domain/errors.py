"""Notification domain errors — mapped to HTTP via platform/errors or subclasses."""

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
