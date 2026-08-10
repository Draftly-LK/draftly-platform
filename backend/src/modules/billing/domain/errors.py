"""Billing domain errors — mapped to HTTP via platform/errors."""

from __future__ import annotations

from src.platform.errors import (
    ConflictError,
    DomainRuleError,
    DraftlyError,
    NotFoundError,
    UnauthenticatedError,
)

__all__ = [
    "BillingNotFoundError",
    "ConcurrencyError",
    "FeatureDeniedError",
    "InvalidPlanInputError",
    "InvalidReturnPathError",
    "InvalidTransitionError",
    "InvalidWebhookError",
    "PlanImmutableError",
    "QuotaExceededError",
    "UserAccountNotBillableError",
    "WebhookPayloadTooLargeError",
]


class BillingNotFoundError(NotFoundError):
    code = "billing_not_found"
    message = "The requested billing resource was not found."


class FeatureDeniedError(DomainRuleError):
    code = "feature_denied"
    http_status = 403
    message = "This feature is not included in your current plan."


class QuotaExceededError(DomainRuleError):
    """429 with the metric named, so the frontend offers an upgrade, not a retry.

    api-conventions.md §8.
    """

    code = "quota_exhausted"
    http_status = 429
    message = "The usage quota for this metric has been exhausted."


class PlanImmutableError(DomainRuleError):
    code = "plan_immutable"
    http_status = 409
    message = "Published plan versions cannot be modified."


class InvalidTransitionError(DomainRuleError):
    code = "invalid_subscription_transition"
    http_status = 422
    message = "The subscription cannot move to the requested status."


class InvalidWebhookError(UnauthenticatedError):
    code = "invalid_webhook"
    message = "Webhook verification failed."


class WebhookPayloadTooLargeError(DraftlyError):
    code = "webhook_payload_too_large"
    http_status = 413
    message = "The webhook payload exceeds the accepted size."


class InvalidReturnPathError(DomainRuleError):
    code = "invalid_return_path"
    http_status = 422
    message = "The checkout return path must be a relative path inside the application."


class InvalidPlanInputError(DomainRuleError):
    code = "invalid_plan_input"
    http_status = 422
    message = "The plan version input is not valid."


class UserAccountNotBillableError(DomainRuleError):
    code = "user_account_not_billable"
    http_status = 422
    message = "This account cannot start a billing operation."


class ConcurrencyError(ConflictError):
    code = "concurrency_conflict"
    message = "The resource was modified concurrently. Retry the operation."
