"""Notarial register domain errors."""

from __future__ import annotations

from src.platform.errors import DomainRuleError, NotFoundError, PreconditionFailedError


class UnapprovedInstrumentError(DomainRuleError):
    code = "unapproved_instrument"
    message = "Attestation requires an approved and exported instrument."


class AttestationImmutableError(DomainRuleError):
    code = "attestation_immutable"
    message = "Attestations cannot be modified after recording."


class InvalidAttestationStateError(PreconditionFailedError):
    code = "invalid_attestation_state"
    message = "This action is not allowed in the attestation's current state."


class RegisterAccessDeniedError(NotFoundError):
    """Cross-user register access is hidden as not found."""

    code = "not_found"
    message = "The requested resource was not found."


class MatterAccessDeniedError(NotFoundError):
    code = "not_found"
    message = "The requested resource was not found."


class PractisingNotaryRequiredError(DomainRuleError):
    code = "practising_notary_required"
    message = "A current practising notary is required to perform this action."
