"""Operational coverage and bounded reads never imply legal sufficiency."""

from types import SimpleNamespace as N
from unittest.mock import AsyncMock

import pytest

from src.modules.check.application.readiness import CheckReadinessReader
from src.modules.verification.application.readiness import FactReadinessReader


@pytest.mark.parametrize("state", ["missing", "fresh", "partial", "unavailable"])
async def test_check_readiness_does_not_infer_all_scope_coverage(state):
    results = (
        []
        if state == "missing"
        else [
            N(
                id="synthetic-check",
                check_definition_id="SYNTHETIC",
                transaction_id="synthetic-tx",
                subject_id="synthetic-parcel",
                association_version=2,
                explanation_key="synthetic.pass",
                outcome=N(value="PASS"),
            )
        ]
    )
    checks = N(
        list_results=AsyncMock(return_value=(results, None)),
        gates=AsyncMock(return_value=N(open_blocking_issue_ids=())),
    )
    scopes = N(
        transaction=AsyncMock(
            return_value=N(
                id="synthetic-tx",
                user_id="actor",
                matter_id="matter",
                version=2 if state == "fresh" else 3,
                parcel_subject_ids=("synthetic-parcel",),
                party_roles=(),
            )
        )
    )
    if state == "unavailable":
        scopes.transaction.side_effect = RuntimeError("Synthetic outage")
    deps = await CheckReadinessReader(checks, scopes).readiness_dependencies(
        N(actor_id="actor"), "matter"
    )
    assert any(dep.category == "checks" and dep.state in {"unknown", "pending"} for dep in deps)


async def test_fact_readiness_stops_at_budget_and_reports_unknown():
    fact = N(
        id="synthetic",
        version=1,
        is_live=True,
        status=N(value="LAWYER_CONFIRMED"),
        is_confirmed=True,
        evidence_stale=False,
        scope_status="assigned",
        transaction_id="tx",
        subject_id="parcel",
    )
    review = N(list_facts=AsyncMock(return_value=([N(fact=fact, conflict_fact_ids=())], True)))
    # A page that keeps returning the same cursor must terminate too.
    deps = await FactReadinessReader(review).readiness_dependencies(N(actor_id="actor"), "matter")
    assert review.list_facts.await_count <= 4
    assert any(dep.category == "facts" and dep.state == "unknown" for dep in deps)
