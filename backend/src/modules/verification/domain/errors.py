"""Verification domain errors."""

from __future__ import annotations

from src.platform.errors import ConflictError, DomainRuleError, NotFoundError


class FactNotFoundError(NotFoundError):
    code = "fact_not_found"
    message = "The requested fact was not found."


class CriticalFactRequiresHumanError(DomainRuleError):
    """§6.4 — no confidence value confirms a critical fact, including 1.00.

    Raised when a non-human path attempts to promote a critical fact to
    ``LAWYER_CONFIRMED``.
    """

    code = "rta_critical_fact_requires_lawyer"
    message = (
        "This fact is critical to the instrument and requires explicit lawyer "
        "confirmation. Model confidence, corroboration, and extraction quality "
        "cannot substitute for it."
    )


class EvidenceRequiredError(DomainRuleError):
    code = "rta_fact_evidence_required"
    message = "A fact must reference the source page it was read from."


class NegativeFactRequiresSearchError(DomainRuleError):
    """Absence of a document is not evidence that an interest does not exist."""

    code = "rta_negative_fact_requires_search"
    message = (
        "A negative conclusion about a registered interest cannot be recorded from "
        "the absence of a document. It requires current search evidence and a "
        "lawyer's conclusion."
    )


class FactSupersededError(ConflictError):
    code = "rta_fact_superseded"
    message = "That fact version has been superseded by a later one."


class FactStaleError(ConflictError):
    code = "fact_version_stale"
    message = "The fact changed since your last read."
