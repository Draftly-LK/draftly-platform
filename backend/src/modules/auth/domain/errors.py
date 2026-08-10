"""Auth domain error types.

These are pure Python exceptions with no FastAPI imports. The API layer maps
them to HTTP responses using the error envelope (platform/errors.py).
"""

from __future__ import annotations

from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    NotFoundError,
    UnauthenticatedError,
)

__all__ = [
    "CapabilityDeniedError",
    "ConflictError",
    "DomainRuleError",
    "NotFoundError",
    "UnauthenticatedError",
    "IdentityValidationError",
    "IdentityNotFoundError",
    "AccountPendingError",
    "AccountSuspendedError",
    "EmailRequiredError",
    "PracticeStatusError",
    "StepUpRequiredError",
    "RoleLockoutError",
]


class IdentityValidationError(UnauthenticatedError):
    """Token was present but failed OIDC validation."""

    code = "identity_validation_failed"
    message = "The supplied token could not be validated."


class IdentityNotFoundError(NotFoundError):
    code = "identity_not_found"
    message = "No Draftly account is linked to this identity."


class AccountPendingError(DomainRuleError):
    """Account is authenticated but not yet linked or approved."""

    code = "account_pending"
    http_status = 403
    message = "Your account is awaiting approval."


class AccountSuspendedError(DomainRuleError):
    code = "account_suspended"
    http_status = 403
    message = "Your account has been suspended."


class EmailRequiredError(DomainRuleError):
    """Google sign-in must yield a verified email before provisioning."""

    code = "email_required"
    http_status = 422
    message = "A verified email address is required to create your account."


class PracticeStatusError(DomainRuleError):
    """Actor lacks a current annual practice certificate or jurisdiction coverage."""

    code = "practice_status_required"
    http_status = 403
    message = "This action requires an active practising certificate and matching jurisdiction."


class StepUpRequiredError(DomainRuleError):
    code = "step_up_required"
    http_status = 403
    message = "This action requires recent re-authentication."


class RoleLockoutError(DomainRuleError):
    """Prevents an actor from removing their own role-recovery capability."""

    code = "role_lockout"
    http_status = 409
    message = "You cannot demote yourself to a role that cannot change roles."
