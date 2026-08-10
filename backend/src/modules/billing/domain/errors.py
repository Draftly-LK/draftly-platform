"""Billing domain errors — mapped to HTTP via platform/errors."""

from __future__ import annotations

from src.platform.errors import (
    ConflictError,
    DomainRuleError,
    NotFoundError,
    UnauthenticatedError,
)

__all__ = [
    "BillingNotFoundError",
    "FeatureDeniedError",
    "QuotaExceededError",
    "PlanImmutableError",
    "InvalidTransitionError",
    "InvalidWebhookError",
    "ConcurrencyError",
]


class BillingNotFoundError(NotFoundError):
    code = "billing_not_found"
    message = "The requested billing resource was not found."


class FeatureDeniedError(DomainRuleError):
    code = "feature_denied"
    http_status = 403
    message = "This feature is not included in your current plan."


class QuotaExceededError(DomainRuleError):
    code = "quota_exceeded"
    http_status = 403
    message = "Usage quota for this metric has been exceeded."


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


class ConcurrencyError(ConflictError):
    code = "concurrency_conflict"
    message = "The resource was modified concurrently. Retry the operation."
