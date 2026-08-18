"""Obligations domain errors."""

from __future__ import annotations

from src.platform.errors import DomainRuleError, NotFoundError


class ObligationNotFoundError(NotFoundError):
    """Missing obligation or existence hidden from the actor."""

    message = "The requested obligation was not found."


class InvalidTransitionError(DomainRuleError):
    code = "invalid_obligation_transition"
    message = "This obligation cannot move to the requested state."


class ConfirmationRequiredError(DomainRuleError):
    code = "lawyer_confirmation_required"
    message = "A lawyer must confirm this deadline before it becomes authoritative."


class LawyerConfirmationDeniedError(DomainRuleError):
    code = "lawyer_confirmation_denied"
    message = "Only a lawyer with deadline confirmation capability may confirm this obligation."


class CorrectionReasonRequiredError(DomainRuleError):
    code = "correction_reason_required"
    message = "Correcting a deadline requires a reason."


class CancellationReasonRequiredError(DomainRuleError):
    code = "cancellation_reason_required"
    message = "Cancelling an obligation requires a reason."


class RestrictedComplianceAccessError(NotFoundError):
    """No existence signal for restricted compliance obligations."""

    message = "The requested obligation was not found."
