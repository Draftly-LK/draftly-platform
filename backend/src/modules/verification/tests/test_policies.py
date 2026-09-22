"""Fact promotion policy: what a machine may decide, and where a lawyer must (F9).

These functions decide whether an extracted value can become a usable fact
without a lawyer looking at it. The rule the whole product rests on: a
critical fact never auto-promotes, at any confidence (Appendix A, refusal 5).
"""

from __future__ import annotations

import pytest

from src.modules.content_governance.contracts import (
    CONFIDENCE_POLICY,
    CRITICAL_FACT_TYPE_IDS,
    FACT_TYPES,
    FactStatus,
    get_fact_type,
)
from src.modules.verification.domain.errors import (
    CriticalFactRequiresHumanError,
    EvidenceRequiredError,
    NegativeFactRequiresSearchError,
)
from src.modules.verification.domain.policies import (
    guard_evidence,
    guard_human_confirmation,
    guard_negative_conclusion,
    may_auto_promote,
    resolve_status_for_candidate,
)

CRITICAL = sorted(CRITICAL_FACT_TYPE_IDS)
NON_CRITICAL = "rta.instrument.notary_name"
NEGATIVE_GATED = sorted(
    f.id
    for f in (FACT_TYPES.values() if isinstance(FACT_TYPES, dict) else FACT_TYPES)
    if get_fact_type(f.id) and get_fact_type(f.id).negative_requires_search_evidence  # type: ignore[union-attr]
)
AUTO = CONFIDENCE_POLICY.noncritical_fact_auto_threshold


def test_there_are_critical_and_negative_gated_types_to_test() -> None:
    """Guards the parametrised tests below against passing on an empty list."""
    assert len(CRITICAL) > 5
    assert NON_CRITICAL not in CRITICAL
    assert NEGATIVE_GATED


# ── may_auto_promote ────────────────────────────────────────────────────────


@pytest.mark.parametrize("fact_type_id", CRITICAL)
@pytest.mark.parametrize("confidence", [None, 0.0, 0.5, AUTO, 0.999, 1.0])
def test_a_critical_fact_never_auto_promotes(fact_type_id: str, confidence: float | None) -> None:
    assert may_auto_promote(fact_type_id, confidence) is False


@pytest.mark.parametrize(
    ("confidence", "promotes"),
    [(None, False), (0.0, False), (AUTO - 0.0001, False), (AUTO, True), (1.0, True)],
)
def test_a_non_critical_fact_promotes_only_at_the_threshold(
    confidence: float | None, promotes: bool
) -> None:
    assert may_auto_promote(NON_CRITICAL, confidence) is promotes


# ── guard_human_confirmation ────────────────────────────────────────────────


@pytest.mark.parametrize("fact_type_id", CRITICAL)
def test_a_critical_fact_needs_a_human_to_confirm_it(fact_type_id: str) -> None:
    with pytest.raises(CriticalFactRequiresHumanError):
        guard_human_confirmation(fact_type_id, confirmed_by_human=False)

    guard_human_confirmation(fact_type_id, confirmed_by_human=True)


def test_a_non_critical_fact_does_not_need_a_human() -> None:
    guard_human_confirmation(NON_CRITICAL, confirmed_by_human=False)


# ── guard_evidence ──────────────────────────────────────────────────────────


def test_a_document_value_must_cite_its_evidence() -> None:
    with pytest.raises(EvidenceRequiredError):
        guard_evidence(NON_CRITICAL, ())

    guard_evidence(NON_CRITICAL, ("ev_synthetic_1",))


# ── guard_negative_conclusion ───────────────────────────────────────────────


@pytest.mark.parametrize("fact_type_id", NEGATIVE_GATED)
@pytest.mark.parametrize("negative", ["NOT_FOUND_IN_CURRENT_SEARCH", "none", "No", False])
@pytest.mark.parametrize(("search", "human"), [(False, False), (False, True), (True, False)])
def test_silence_is_not_a_negative_finding(
    fact_type_id: str, negative: object, search: bool, human: bool
) -> None:
    """ "No mortgage" needs a current search and a lawyer, both."""
    with pytest.raises(NegativeFactRequiresSearchError):
        guard_negative_conclusion(
            fact_type_id, negative, has_current_search_evidence=search, confirmed_by_human=human
        )


@pytest.mark.parametrize("fact_type_id", NEGATIVE_GATED)
def test_a_lawyer_with_a_current_search_may_record_a_negative(fact_type_id: str) -> None:
    guard_negative_conclusion(
        fact_type_id,
        "NOT_FOUND_IN_CURRENT_SEARCH",
        has_current_search_evidence=True,
        confirmed_by_human=True,
    )


@pytest.mark.parametrize("fact_type_id", NEGATIVE_GATED)
def test_a_positive_finding_needs_no_search(fact_type_id: str) -> None:
    guard_negative_conclusion(
        fact_type_id,
        "REGISTERED_MORTGAGE",
        has_current_search_evidence=False,
        confirmed_by_human=False,
    )


def test_ungated_types_accept_a_negative_value() -> None:
    guard_negative_conclusion(
        NON_CRITICAL, "NONE", has_current_search_evidence=False, confirmed_by_human=False
    )


# ── resolve_status_for_candidate ────────────────────────────────────────────


@pytest.mark.parametrize("fact_type_id", [CRITICAL[0], NON_CRITICAL])
@pytest.mark.parametrize("agreeing", [0, 1, 3])
def test_any_disagreement_is_a_conflict(fact_type_id: str, agreeing: int) -> None:
    """No source is silently preferred: two for, one against, is a conflict."""
    status = resolve_status_for_candidate(
        fact_type_id,
        agreeing_source_count=agreeing,
        disagreeing_source_count=1,
        model_reported_confidence=1.0,
    )

    assert status is FactStatus.CONFLICTED


@pytest.mark.parametrize(
    ("agreeing", "expected"),
    [(1, FactStatus.REVIEW_REQUIRED), (2, FactStatus.CORROBORATED)],
)
def test_a_critical_candidate_waits_for_a_lawyer_even_when_corroborated(
    agreeing: int, expected: FactStatus
) -> None:
    status = resolve_status_for_candidate(
        CRITICAL[0],
        agreeing_source_count=agreeing,
        disagreeing_source_count=0,
        model_reported_confidence=1.0,
    )

    assert status is expected


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (AUTO, FactStatus.EXTRACTED_CANDIDATE),
        (AUTO - 0.01, FactStatus.REVIEW_REQUIRED),
        (None, FactStatus.REVIEW_REQUIRED),
    ],
)
def test_a_single_non_critical_source_follows_the_threshold(
    confidence: float | None, expected: FactStatus
) -> None:
    status = resolve_status_for_candidate(
        NON_CRITICAL,
        agreeing_source_count=1,
        disagreeing_source_count=0,
        model_reported_confidence=confidence,
    )

    assert status is expected


@pytest.mark.parametrize("fact_type_id", CRITICAL + [NON_CRITICAL])
@pytest.mark.parametrize("agreeing", [0, 1, 2, 5])
@pytest.mark.parametrize("disagreeing", [0, 1])
@pytest.mark.parametrize("confidence", [None, 0.5, 1.0])
def test_no_candidate_is_ever_lawyer_confirmed(
    fact_type_id: str, agreeing: int, disagreeing: int, confidence: float | None
) -> None:
    """Only a lawyer's decision confirms; extraction never does."""
    status = resolve_status_for_candidate(
        fact_type_id,
        agreeing_source_count=agreeing,
        disagreeing_source_count=disagreeing,
        model_reported_confidence=confidence,
    )

    assert status not in {FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM}
