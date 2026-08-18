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
    "BeneficialOwnerDepthExceededError",
    "CrossUserPartyError",
    "RestrictedComplianceError",
    "EvidenceNotPinnedError",
    "EvidenceStateTransitionError",
    "MergedPartyImmutableError",
    "MergeTargetInvalidError",
]


class IdentityPurposeRequiredError(DomainRuleError):
    code = "identity_purpose_required"
    message = "A lawful purpose is required to read a full identifier."


class BeneficialOwnerCycleError(DomainRuleError):
    code = "beneficial_owner_cycle"
    message = "Beneficial ownership cannot form a cycle."


class BeneficialOwnerDepthExceededError(DomainRuleError):
    code = "beneficial_owner_depth_exceeded"
    message = "The beneficial ownership chain exceeds the permitted depth."


class EvidenceNotPinnedError(DomainRuleError):
    code = "evidence_not_pinned"
    message = "Verified identity evidence requires a pinned immutable document version."


class EvidenceStateTransitionError(DomainRuleError):
    code = "evidence_state_transition_invalid"
    message = "That identity evidence state transition is not permitted."


class MergedPartyImmutableError(DomainRuleError):
    code = "party_merged"
    message = "This party has been merged and can no longer be modified."


class MergeTargetInvalidError(DomainRuleError):
    code = "merge_target_invalid"
    message = "A party cannot be merged into itself or into an already-merged party."


class CrossUserPartyError(NotFoundError):
    """Cross-user access is reported as not found (party-service.md §9)."""

    code = "not_found"
    message = "The requested resource was not found."


class RestrictedComplianceError(NotFoundError):
    """Restricted-compliance records give an ordinary member no existence signal.

    404 with the same code, message, and body as a genuinely missing record, so
    the absence of a screening result and the absence of permission to see one
    are indistinguishable (service-definition-of-done.md §4.7).
    """

    code = "not_found"
    message = "The requested resource was not found."
