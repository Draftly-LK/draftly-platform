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
    "InvitationNotFoundError",
    "InvitationExpiredError",
    "InvitationAlreadyAcceptedError",
    "AccountPendingError",
    "AccountSuspendedError",
    "OrganisationSuspendedError",
    "OrganisationNotFoundError",
    "MembershipNotFoundError",
    "AdminLockoutError",
    "PracticeStatusError",
    "StepUpRequiredError",
]


class IdentityValidationError(UnauthenticatedError):
    """Token was present but failed OIDC validation."""

    code = "identity_validation_failed"
    message = "The supplied token could not be validated."


class IdentityNotFoundError(NotFoundError):
    code = "identity_not_found"
    message = "No Draftly account is linked to this identity."


class InvitationNotFoundError(NotFoundError):
    code = "invitation_not_found"
    message = "No valid invitation was found for this identity."


class InvitationExpiredError(DomainRuleError):
    code = "invitation_expired"
    message = "This invitation has expired. Please request a new one."


class InvitationAlreadyAcceptedError(DomainRuleError):
    code = "invitation_already_accepted"
    message = "This invitation has already been used."


class AccountPendingError(DomainRuleError):
    """Account is authenticated but not yet approved (no role, no memberships)."""

    code = "account_pending"
    http_status = 403
    message = "Your account is awaiting approval."


class AccountSuspendedError(DomainRuleError):
    code = "account_suspended"
    http_status = 403
    message = "Your account has been suspended."


class OrganisationSuspendedError(DomainRuleError):
    code = "organisation_suspended"
    http_status = 403
    message = "This organisation is suspended."


class OrganisationNotFoundError(NotFoundError):
    code = "organisation_not_found"
    message = "Organisation not found or you are not a member."


class MembershipNotFoundError(NotFoundError):
    code = "membership_not_found"
    message = "Matter membership not found."


class AdminLockoutError(DomainRuleError):
    """Raised when an operation would remove the last organisation owner."""

    code = "admin_lockout_blocked"
    http_status = 422
    message = "Cannot remove the last owner of an organisation."


class PracticeStatusError(DomainRuleError):
    """Actor lacks a current annual practice certificate or jurisdiction coverage."""

    code = "practice_status_required"
    http_status = 403
    message = "This action requires an active practising certificate and matching jurisdiction."


class StepUpRequiredError(DomainRuleError):
    code = "step_up_required"
    http_status = 403
    message = "This action requires recent re-authentication."
