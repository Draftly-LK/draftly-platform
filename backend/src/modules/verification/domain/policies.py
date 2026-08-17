"""Fact promotion policy — what a machine may do, and where a human is required.

This is the file that makes §6.4 enforceable rather than aspirational. Three
functions carry it:

- `may_auto_promote` — never returns True for a critical fact, at any confidence.
- `guard_human_confirmation` — raises if a non-human path tries anyway.
- `guard_negative_conclusion` — refuses to record "no mortgage" from silence.

`resolve_status_for_candidate` decides what a newly extracted value becomes:
corroborated, conflicted, or simply a candidate. It never returns
``LAWYER_CONFIRMED``.
"""

from __future__ import annotations

from typing import Any

from src.modules.content_governance.contracts import (
    CONFIDENCE_POLICY,
    FactStatus,
    get_fact_type,
    is_critical,
    may_auto_confirm_critical_fact,
)
from src.modules.verification.domain.errors import (
    CriticalFactRequiresHumanError,
    EvidenceRequiredError,
    NegativeFactRequiresSearchError,
)


def may_auto_promote(fact_type_id: str, model_reported_confidence: float | None) -> bool:
    """Whether the pipeline may treat this value as usable without a human.

    A critical fact returns False unconditionally — the confidence argument is
    accepted and then deliberately ignored, and the delegation to
    `may_auto_confirm_critical_fact` keeps that decision in one governed place.
    """
    if is_critical(fact_type_id):
        return may_auto_confirm_critical_fact(model_reported_confidence or 0.0)
    if model_reported_confidence is None:
        return False
    return model_reported_confidence >= CONFIDENCE_POLICY.noncritical_fact_auto_threshold


def guard_human_confirmation(fact_type_id: str, *, confirmed_by_human: bool) -> None:
    """Raise unless a human is confirming a critical fact."""
    if is_critical(fact_type_id) and not confirmed_by_human:
        raise CriticalFactRequiresHumanError(factTypeId=fact_type_id)


def guard_evidence(fact_type_id: str, evidence_reference_ids: tuple[str, ...]) -> None:
    """A value read from a document must say which page it came from.

    A lawyer-supplied value has no source document, so it is exempt — but it
    carries a recorded reason instead, which the service requires.
    """
    if not evidence_reference_ids:
        raise EvidenceRequiredError(factTypeId=fact_type_id)


def guard_negative_conclusion(
    fact_type_id: str,
    value: Any,
    *,
    has_current_search_evidence: bool,
    confirmed_by_human: bool,
) -> None:
    """Refuse a negative conclusion drawn from an absent document.

    Only fact types flagged ``negative_requires_search_evidence`` are gated, and
    only when the value being recorded is the negative one. A lawyer may still
    reach the conclusion — but a current search has to exist for them to have
    reached it from anything.
    """
    definition = get_fact_type(fact_type_id)
    if definition is None or not definition.negative_requires_search_evidence:
        return
    if not _is_negative(value):
        return
    if not (has_current_search_evidence and confirmed_by_human):
        raise NegativeFactRequiresSearchError(factTypeId=fact_type_id)


_NEGATIVE_TOKENS = frozenset(
    {
        "NO",
        "NONE",
        "FALSE",
        "NOT_FOUND_IN_CURRENT_SEARCH",
        "NO_EVIDENCE_REVIEWED",
        "VACANT_CONFIRMED_BY_LAWYER",
    }
)


def _is_negative(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.upper() in _NEGATIVE_TOKENS


def resolve_status_for_candidate(
    fact_type_id: str,
    *,
    agreeing_source_count: int,
    disagreeing_source_count: int,
    model_reported_confidence: float | None,
) -> FactStatus:
    """The status a freshly extracted candidate takes. Never LAWYER_CONFIRMED.

    Disagreement wins over agreement: two sources that match plus one that does
    not is a conflict to resolve, not a majority to accept (§10.5 "no source is
    silently preferred").
    """
    if disagreeing_source_count > 0:
        return FactStatus.CONFLICTED
    if is_critical(fact_type_id):
        # Corroboration is real information and worth recording, but a critical
        # fact still ends up in the human queue either way.
        return FactStatus.CORROBORATED if agreeing_source_count > 1 else FactStatus.REVIEW_REQUIRED
    if agreeing_source_count > 1:
        return FactStatus.CORROBORATED
    if may_auto_promote(fact_type_id, model_reported_confidence):
        return FactStatus.EXTRACTED_CANDIDATE
    return FactStatus.REVIEW_REQUIRED
