"""Confirmed-fact tiers, as the verification module hands them to consumers."""

from __future__ import annotations

from typing import Any

from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary


def fact_tier(
    values: dict[str, Any],
    *,
    conflicted: tuple[str, ...] = (),
    unconfirmed_critical: tuple[str, ...] = (),
    has_search_evidence: bool = True,
    version: int = 1,
    fact_id_suffix: str | None = None,
    evidence_suffix: str | None = None,
) -> FactTierSummary:
    """One confirmed fact per entry, each with its own evidence reference.

    ``fact_id_suffix`` mints different facts for the same values, which is how
    a correction looks to a consumer. ``evidence_suffix`` keeps the facts and
    changes only their evidence. Evidence follows the fact suffix unless set.
    """
    ev_suffix = evidence_suffix or fact_id_suffix or "a"
    return FactTierSummary(
        confirmed={
            fact_type_id: ConfirmedFactValue(
                fact_id=f"fact_{index}"
                if fact_id_suffix is None
                else f"fact_{index}_{fact_id_suffix}",
                fact_type_id=fact_type_id,
                value=value,
                version=version,
                evidence_reference_ids=(f"ev_{index}_{ev_suffix}",),
            )
            for index, (fact_type_id, value) in enumerate(sorted(values.items()))
        },
        unconfirmed_critical_fact_type_ids=unconfirmed_critical,
        conflicted_fact_type_ids=conflicted,
        has_current_search_evidence=has_search_evidence,
    )
