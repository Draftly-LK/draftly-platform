"""Running the checks, raising the issues, and disposing of them.

All fixture content is synthetic. The acceptance criteria that live here:

- a rerun after a fact changes appends a new result rather than mutating the
  old one, so the state a conclusion was drawn under stays reconstructible;
- a rerun does not duplicate an issue nobody has disposed of yet;
- new contrary evidence reopens a closed issue, and identical evidence does not;
- a passing rerun never closes an issue by itself;
- accepting risk on a statutory blocker is refused with its own error code, and
  nothing is written when it is.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.modules.check.application.check_service import CheckService
from src.modules.check.domain.errors import StatutoryRiskNotAcceptableError
from src.modules.check.domain.models import LegalIssue
from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckOutcome,
    IssueSeverity,
    IssueState,
    RtaWorkflowRole,
)
from src.modules.verification.contracts import FactTierSummary

from .fakes import CLEAN_TRANSFER, FakeAudit, FakeCheckRepository, FakeFactReader, fact_tier

_USER = "usr_synthetic"
_MATTER = "mat_synthetic"
#: Fixed so the seven-working-day deadline check does not depend on the day the
#: suite happens to run.
_NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


def _build(summary: FactTierSummary) -> tuple[CheckService, FakeCheckRepository, FakeAudit]:
    repository, audit = FakeCheckRepository(), FakeAudit()
    facts = FakeFactReader(summary)
    service = CheckService(repository=repository, facts=facts, audit=audit, clock=lambda: _NOW)
    return service, repository, audit


async def _run(service: CheckService) -> Any:
    return await service.run_checks(
        user_id=_USER,
        matter_id=_MATTER,
        actor_id=_USER,
        correlation_id="corr_synthetic",
        search_currency_max_age_days=90,
    )


def _mortgage_issue(repository: FakeCheckRepository) -> LegalIssue:
    matching = [
        issue
        for issue in repository.issues.values()
        if issue.issue_type_id == "rta.issue.mortgage_unresolved"
    ]
    assert matching, "the mortgage check should have raised an issue"
    return matching[0]


def _uncancelled_mortgage() -> dict[str, Any]:
    return {**CLEAN_TRANSFER, "rta.interest.mortgage_status": "APPARENTLY_UNCANCELLED"}


# ── A run records every check, pinned to what it read ────────────────────────


async def test_a_run_records_one_result_per_check_under_one_run_id() -> None:
    service, repository, audit = _build(fact_tier(CLEAN_TRANSFER))
    run = await _run(service)
    assert len(repository.results) == len(run.results)
    assert {result.run_id for result in repository.results} == {run.run_id}
    assert "rta.check.run" in audit.actions()


async def test_a_clean_matter_raises_no_issue_and_no_gate() -> None:
    service, repository, _ = _build(fact_tier(CLEAN_TRANSFER))
    run = await _run(service)
    assert repository.issues == {}
    assert run.gates.blocks_draft_generation is False
    assert run.gates.blocks_approval is False


async def test_a_rerun_after_a_fact_changes_appends_rather_than_mutating() -> None:
    """§7.1, §12.2 — "what did we know when we concluded that?" stays answerable."""
    facts = FakeFactReader(fact_tier(CLEAN_TRANSFER))
    repository, audit = FakeCheckRepository(), FakeAudit()
    service = CheckService(repository=repository, facts=facts, audit=audit, clock=lambda: _NOW)

    first = await _run(service)
    first_extent = next(r for r in first.results if r.check_definition_id == "CHK_EXTENT")

    facts.summary = fact_tier(
        {**CLEAN_TRANSFER, "rta.parcel.extent_subject_to_transaction": "0.0400 ha"}, version=2
    )
    second = await _run(service)
    second_extent = next(r for r in second.results if r.check_definition_id == "CHK_EXTENT")

    assert second.run_id != first.run_id
    assert second_extent.id != first_extent.id
    assert first_extent.outcome is CheckOutcome.PASS
    assert second_extent.outcome is CheckOutcome.FAIL
    # The first result is still on file, still pinned to version 1.
    stored = [r for r in repository.results if r.check_definition_id == "CHK_EXTENT"]
    assert len(stored) == 2
    assert {pin.version for pin in stored[0].input_fact_versions} == {1}
    assert {pin.version for pin in stored[1].input_fact_versions} == {2}


# ── Issues (§10.6) ───────────────────────────────────────────────────────────


async def test_a_failing_check_opens_an_issue_at_its_default_severity() -> None:
    service, repository, audit = _build(fact_tier(_uncancelled_mortgage()))
    run = await _run(service)
    issue = _mortgage_issue(repository)
    assert issue.state is IssueState.OPEN
    assert issue.severity is IssueSeverity.HIGH_RISK
    assert issue.blocker_kind is BlockerKind.EVIDENCE
    assert issue.source_record_ids
    assert "rta.issue.created" in audit.actions()
    assert run.gates.blocks_approval is True
    assert run.gates.blocks_draft_generation is False


async def test_a_rerun_does_not_duplicate_an_issue_nobody_has_disposed_of() -> None:
    service, repository, _ = _build(fact_tier(_uncancelled_mortgage()))
    await _run(service)
    second = await _run(service)
    mortgage_issues = [
        issue
        for issue in repository.issues.values()
        if issue.issue_type_id == "rta.issue.mortgage_unresolved"
    ]
    assert len(mortgage_issues) == 1
    assert second.raised_issues == ()


async def test_a_closed_issue_reopens_on_new_contrary_evidence() -> None:
    facts = FakeFactReader(fact_tier(_uncancelled_mortgage()))
    repository, audit = FakeCheckRepository(), FakeAudit()
    service = CheckService(repository=repository, facts=facts, audit=audit, clock=lambda: _NOW)
    await _run(service)
    issue = _mortgage_issue(repository)

    resolved = await service.decide_issue(
        user_id=_USER,
        matter_id=_MATTER,
        issue_id=issue.id,
        actor_id=_USER,
        actor_workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
        correlation_id="corr_synthetic",
        expected_version=issue.version,
        target_state=IssueState.RESOLVED,
        reason="Registered cancellation sighted on the current register extract.",
        new_evidence_reference_ids=("ev_release_1",),
    )
    assert resolved.state is IssueState.RESOLVED

    # A rerun over the same evidence must not churn the lawyer's disposition.
    await _run(service)
    assert repository.issues[issue.id].state is IssueState.RESOLVED

    # A rerun over evidence the issue has not seen reopens it.
    facts.summary = fact_tier(_uncancelled_mortgage(), version=2, evidence_suffix="b")
    await _run(service)
    reopened = repository.issues[issue.id]
    assert reopened.state is IssueState.ACTION_REQUIRED
    assert "ev_release_1" in reopened.evidence_reference_ids
    assert audit.actions().count("rta.issue.decided") == 2


async def test_a_passing_rerun_never_closes_an_issue_by_itself() -> None:
    """§10.6 puts every closing disposition behind a recorded human decision."""
    facts = FakeFactReader(fact_tier(_uncancelled_mortgage()))
    repository, audit = FakeCheckRepository(), FakeAudit()
    service = CheckService(repository=repository, facts=facts, audit=audit, clock=lambda: _NOW)
    await _run(service)
    issue = _mortgage_issue(repository)

    facts.summary = fact_tier(
        {**CLEAN_TRANSFER, "rta.interest.mortgage_status": "CANCELLATION_REGISTERED"}
    )
    run = await _run(service)
    assert (
        next(r for r in run.results if r.check_definition_id == "CHK_MORTGAGE_STATUS").outcome
        is CheckOutcome.PASS
    )
    assert repository.issues[issue.id].state is IssueState.OPEN
    assert run.gates.blocks_approval is True


# ── Dispositions ─────────────────────────────────────────────────────────────


async def test_accepting_risk_on_a_statutory_blocker_is_refused_and_writes_nothing() -> None:
    facts = FakeFactReader(
        fact_tier({**CLEAN_TRANSFER, "rta.instrument.disposition_scope": "PART_OF_PARCEL"})
    )
    repository, audit = FakeCheckRepository(), FakeAudit()
    service = CheckService(repository=repository, facts=facts, audit=audit, clock=lambda: _NOW)
    await _run(service)
    issue = next(
        i
        for i in repository.issues.values()
        if i.issue_type_id == "rta.issue.part_parcel_without_subdivision"
    )
    assert issue.blocker_kind is BlockerKind.STATUTORY
    audit_before = len(audit.events)

    with pytest.raises(StatutoryRiskNotAcceptableError):
        await service.decide_issue(
            user_id=_USER,
            matter_id=_MATTER,
            issue_id=issue.id,
            actor_id=_USER,
            actor_workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
            correlation_id="corr_synthetic",
            expected_version=issue.version,
            target_state=IssueState.ACCEPTED_RISK,
            reason="The parties accept the position.",
        )
    assert repository.issues[issue.id].state is IssueState.OPEN
    assert len(audit.events) == audit_before


async def test_a_recorded_disposition_bumps_the_version_and_audits() -> None:
    service, repository, audit = _build(fact_tier(_uncancelled_mortgage()))
    await _run(service)
    issue = _mortgage_issue(repository)
    saved = await service.decide_issue(
        user_id=_USER,
        matter_id=_MATTER,
        issue_id=issue.id,
        actor_id=_USER,
        actor_workflow_role=RtaWorkflowRole.LAWYER_REVIEWER,
        correlation_id="corr_synthetic",
        expected_version=issue.version,
        target_state=IssueState.TRIAGED,
        reason="Awaiting the bank's registered cancellation.",
    )
    assert saved.version == issue.version + 1
    assert saved.resolution_decision_id is not None
    decided = [event for event in audit.events if event.action == "rta.issue.decided"]
    assert decided[-1].before_ref == IssueState.OPEN.value
    assert decided[-1].target_id == issue.id


async def test_the_gates_read_every_issue_on_the_matter() -> None:
    service, _, _ = _build(
        fact_tier({**CLEAN_TRANSFER, "rta.instrument.disposition_scope": "PART_OF_PARCEL"})
    )
    await _run(service)
    gates = await service.gates(_USER, _MATTER)
    assert gates.blocks_draft_generation is True
    assert gates.blocks_approval is True
    assert gates.blocks_registration_ready_export is True
    assert gates.open_statutory_blocker_ids
    assert gates.open_blocking_issue_ids


async def test_another_users_matter_is_invisible_to_the_gates() -> None:
    """Every query filters on ``user_id`` first — the tenancy boundary (§5.3)."""
    service, _, _ = _build(fact_tier(_uncancelled_mortgage()))
    await _run(service)
    assert (await service.gates("usr_someone_else", _MATTER)).blocks_approval is False


async def test_every_result_in_one_run_shares_its_timestamp() -> None:
    """One run is one moment: a per-check clock read would split the record."""
    service, repository, _ = _build(fact_tier(CLEAN_TRANSFER))
    await _run(service)
    assert len({result.created_at for result in repository.results}) == 1
