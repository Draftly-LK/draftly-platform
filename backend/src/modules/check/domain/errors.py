"""Check and legal-issue domain errors."""

from __future__ import annotations

from src.platform.errors import ConflictError, DomainRuleError, NotFoundError


class CheckResultNotFoundError(NotFoundError):
    code = "check_result_not_found"
    message = "The requested check result was not found."


class LegalIssueNotFoundError(NotFoundError):
    code = "legal_issue_not_found"
    message = "The requested legal issue was not found."


class StatutoryRiskNotAcceptableError(DomainRuleError):
    """A statutory blocker cannot be overridden inside Draftly at all (§7.3).

    Its own code, separate from the generic illegal-transition error, because
    this is the one refusal the product must never let a caller talk its way
    around: no role, no reason, and no severity reclassification reaches it.
    """

    code = "rta_statutory_blocker_not_overridable"
    message = (
        "A statutory blocker cannot be accepted as a risk. Draftly cannot set aside "
        "a statutory prohibition; the matter needs a lawful structure, the required "
        "process, or the manual workflow."
    )


class IssueStateNotPermittedError(DomainRuleError):
    code = "rta_issue_state_not_permitted"
    message = "That disposition is not permitted for this issue's blocker kind."


class IssueDecisionReasonRequiredError(DomainRuleError):
    code = "rta_issue_decision_reason_required"
    message = "This disposition requires a recorded reason from the deciding lawyer."


class IssueDecisionRoleRequiredError(DomainRuleError):
    code = "rta_issue_decision_role_required"
    message = "Your workflow role on this matter cannot record that disposition."


class IssueResolutionRequiresEvidenceError(DomainRuleError):
    """An evidence blocker closes on evidence, never on assertion (§7.3, §6.4)."""

    code = "rta_issue_resolution_requires_evidence"
    message = (
        "Resolving an evidence-backed issue requires new evidence references. "
        "Absence of a document is not proof that the concern has gone away."
    )


class LegalIssueStaleError(ConflictError):
    code = "legal_issue_version_stale"
    message = "The legal issue changed since your last read."
