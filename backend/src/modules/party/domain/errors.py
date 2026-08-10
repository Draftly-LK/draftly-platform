"""Party domain errors — mapped to platform HTTP errors at the API boundary."""

from __future__ import annotations

from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    NotFoundError,
    PreconditionFailedError,
)

__all__ = [
    "CapabilityDeniedError",
    "ConflictError",
    "DomainRuleError",
    "NotFoundError",
    "PreconditionFailedError",
    "IdentityPurposeRequiredError",
    "BeneficialOwnerCycleError",
    "CrossUserPartyError",
]


class IdentityPurposeRequiredError(DomainRuleError):
    code = "identity_purpose_required"
    message = "A lawful purpose is required to read a full identifier."


class BeneficialOwnerCycleError(DomainRuleError):
    code = "beneficial_owner_cycle"
    message = "Beneficial ownership cannot form a cycle."


class CrossUserPartyError(NotFoundError):
    """Cross-user access is reported as not found (party-service.md §9)."""

    code = "not_found"
    message = "The requested resource was not found."
