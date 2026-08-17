"""Matter domain errors.

Each carries the stable ``code`` the frontend switches on (api-conventions §5).
An illegal transition is 422, never 500: the request was well formed and the
domain refused it.
"""

from __future__ import annotations

from src.platform.errors import ConflictError, DomainRuleError, NotFoundError


class MatterNotFoundError(NotFoundError):
    """Absent, or the caller is not a member — deliberately indistinguishable."""

    code = "matter_not_found"
    message = "The requested matter was not found."


class UnknownSubtypeError(DomainRuleError):
    code = "rta_subtype_unknown"
    message = "That RTA instrument subtype does not exist in the current taxonomy."


class UnknownQuestionError(DomainRuleError):
    code = "rta_question_unknown"
    message = "That intake question does not exist in the current rule pack."


class InvalidAnswerValueError(DomainRuleError):
    code = "rta_answer_invalid"
    message = "The answer value does not match the question's accepted vocabulary."


class SubtypeConfirmationRequiredError(DomainRuleError):
    """Selecting a family is not selecting an instrument (§Executive 2)."""

    code = "rta_subtype_confirmation_required"
    message = "The exact prescribed instrument must be confirmed by the responsible lawyer."


class LegalBasisRequiredError(DomainRuleError):
    """`other_declared_instrument` is a controlled fallback, not a default."""

    code = "rta_legal_basis_required"
    message = (
        "This instrument is only available when the responsible lawyer records the "
        "legal basis that authorises it."
    )


class IllegalMatterTransitionError(DomainRuleError):
    code = "rta_matter_transition_illegal"
    message = "That matter state transition is not permitted."


class MatterStaleError(ConflictError):
    code = "matter_version_stale"
    message = "The matter changed since your last read."


class UnknownLegacyMatterTypeError(DomainRuleError):
    """Migration never guesses; an unmapped legacy value is reported (§3.6)."""

    code = "rta_legacy_type_unknown"
    message = "That legacy matter type has no migration target in the current taxonomy."
