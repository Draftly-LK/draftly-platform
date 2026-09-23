"""Fact promotion policy (§6.4): what a machine may do, and where a human is required."""

from __future__ import annotations

import pytest

from src.modules.content_governance.contracts import (
    CONFIDENCE_POLICY,
    CRITICAL_FACT_TYPE_IDS,
    FactStatus,
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

CRITICAL = "rta.instrument.consideration"
NON_CRITICAL = "rta.parcel.village"
NEGATIVE_GATED = "rta.interest.mortgage_status"


def test_fixture_fact_types_are_what_the_tests_assume() -> None:
    assert CRITICAL in CRITICAL_FACT_TYPE_IDS
    assert NON_CRITICAL not in CRITICAL_FACT_TYPE_IDS


# ── may_auto_promote ────────────────────────────────────────────────────────


@pytest.mark.parametrize("confidence", [None, 0.0, 0.5, 0.99, 1.0])
def test_no_confidence_value_promotes_a_critical_fact(confidence: float | None) -> None:
    assert may_auto_promote(CRITICAL, confidence) is False


@pytest.mark.parametrize("fact_type_id", sorted(CRITICAL_FACT_TYPE_IDS))
def test_every_critical_fact_type_refuses_perfect_confidence(fact_type_id: str) -> None:
    assert may_auto_promote(fact_type_id, 1.0) is False


def test_non_critical_fact_promotes_at_and_above_the_threshold() -> None:
    threshold = CONFIDENCE_POLICY.noncritical_fact_auto_threshold
    assert may_auto_promote(NON_CRITICAL, threshold) is True
    assert may_auto_promote(NON_CRITICAL, 1.0) is True
    assert may_auto_promote(NON_CRITICAL, threshold - 0.01) is False


def test_non_critical_fact_without_a_confidence_is_not_promoted() -> None:
    assert may_auto_promote(NON_CRITICAL, None) is False


# ── guards ──────────────────────────────────────────────────────────────────


def test_machine_path_cannot_confirm_a_critical_fact() -> None:
    with pytest.raises(CriticalFactRequiresHumanError) as excinfo:
        guard_human_confirmation(CRITICAL, confirmed_by_human=False)
    assert excinfo.value.code == "rta_critical_fact_requires_lawyer"
    assert excinfo.value.http_status == 422
    assert excinfo.value.details == {"factTypeId": CRITICAL}


def test_human_may_confirm_a_critical_fact() -> None:
    guard_human_confirmation(CRITICAL, confirmed_by_human=True)


def test_machine_path_may_confirm_a_non_critical_fact() -> None:
    guard_human_confirmation(NON_CRITICAL, confirmed_by_human=False)


def test_a_fact_without_evidence_is_refused() -> None:
    with pytest.raises(EvidenceRequiredError) as excinfo:
        guard_evidence(NON_CRITICAL, ())
    assert excinfo.value.code == "rta_fact_evidence_required"
    assert excinfo.value.details == {"factTypeId": NON_CRITICAL}


def test_a_fact_with_evidence_passes() -> None:
    guard_evidence(NON_CRITICAL, ("evr_1",))


@pytest.mark.parametrize(
    "value",
    ["NO", "none", "False", "NOT_FOUND_IN_CURRENT_SEARCH", "no_evidence_reviewed", False],
)
@pytest.mark.parametrize(
    ("has_search", "human"),
    [(False, False), (True, False), (False, True)],
)
def test_negative_conclusion_needs_both_a_search_and_a_human(
    value: object, has_search: bool, human: bool
) -> None:
    with pytest.raises(NegativeFactRequiresSearchError) as excinfo:
        guard_negative_conclusion(
            NEGATIVE_GATED,
            value,
            has_current_search_evidence=has_search,
            confirmed_by_human=human,
        )
    assert excinfo.value.code == "rta_negative_fact_requires_search"
    assert excinfo.value.details == {"factTypeId": NEGATIVE_GATED}


def test_lawyer_with_current_search_may_record_a_negative_conclusion() -> None:
    guard_negative_conclusion(
        NEGATIVE_GATED, "NONE", has_current_search_evidence=True, confirmed_by_human=True
    )


@pytest.mark.parametrize("value", ["YES", "REGISTERED", True, 0, None])
def test_positive_values_are_not_gated(value: object) -> None:
    guard_negative_conclusion(
        NEGATIVE_GATED, value, has_current_search_evidence=False, confirmed_by_human=False
    )


@pytest.mark.parametrize("fact_type_id", [NON_CRITICAL, "rta.not.a.real.fact_type"])
def test_ungated_or_unknown_fact_types_are_not_gated(fact_type_id: str) -> None:
    guard_negative_conclusion(
        fact_type_id, "NO", has_current_search_evidence=False, confirmed_by_human=False
    )


# ── resolve_status_for_candidate ────────────────────────────────────────────


@pytest.mark.parametrize("fact_type_id", [CRITICAL, NON_CRITICAL])
def test_any_disagreement_is_a_conflict_not_a_majority(fact_type_id: str) -> None:
    status = resolve_status_for_candidate(
        fact_type_id,
        agreeing_source_count=5,
        disagreeing_source_count=1,
        model_reported_confidence=1.0,
    )
    assert status is FactStatus.CONFLICTED


def test_critical_fact_from_one_source_needs_review_even_at_full_confidence() -> None:
    status = resolve_status_for_candidate(
        CRITICAL, agreeing_source_count=1, disagreeing_source_count=0, model_reported_confidence=1.0
    )
    assert status is FactStatus.REVIEW_REQUIRED


def test_corroborated_critical_fact_is_recorded_as_such() -> None:
    status = resolve_status_for_candidate(
        CRITICAL, agreeing_source_count=2, disagreeing_source_count=0, model_reported_confidence=0.1
    )
    assert status is FactStatus.CORROBORATED


def test_non_critical_fact_outcomes() -> None:
    def resolve(agreeing: int, confidence: float | None) -> FactStatus:
        return resolve_status_for_candidate(
            NON_CRITICAL,
            agreeing_source_count=agreeing,
            disagreeing_source_count=0,
            model_reported_confidence=confidence,
        )

    assert resolve(2, None) is FactStatus.CORROBORATED
    assert resolve(1, 0.99) is FactStatus.EXTRACTED_CANDIDATE
    assert resolve(1, 0.5) is FactStatus.REVIEW_REQUIRED
    assert resolve(1, None) is FactStatus.REVIEW_REQUIRED


@pytest.mark.parametrize("fact_type_id", [CRITICAL, NON_CRITICAL])
@pytest.mark.parametrize("agreeing", [0, 1, 3])
@pytest.mark.parametrize("disagreeing", [0, 2])
@pytest.mark.parametrize("confidence", [None, 0.2, 1.0])
def test_a_candidate_is_never_lawyer_confirmed(
    fact_type_id: str, agreeing: int, disagreeing: int, confidence: float | None
) -> None:
    status = resolve_status_for_candidate(
        fact_type_id,
        agreeing_source_count=agreeing,
        disagreeing_source_count=disagreeing,
        model_reported_confidence=confidence,
    )
    assert status not in {FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM}
