"""Issue dispositions and the three §7.3 gates.

The acceptance criteria that live here:

- a statutory blocker can never be accepted as a risk, by anyone, ever;
- who may accept depends on the blocker kind, and every acceptance carries a
  reason;
- an evidence blocker closes on evidence, not on assertion;
- accepting a risk records a separate disposition and never rewrites the
  check's outcome;
- ``HIGH_RISK`` permits a watermarked working draft but not approval, and
  ``BLOCKING`` permits neither.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.check.domain.errors import (
    IssueDecisionReasonRequiredError,
    IssueDecisionRoleRequiredError,
    IssueResolutionRequiresEvidenceError,
    IssueStateNotPermittedError,
    StatutoryRiskNotAcceptableError,
)
from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.check.domain.policies import (
    accepted_risk_does_not_change_outcome,
    blocks_approval,
    blocks_draft_generation,
    blocks_registration_ready_export,
    guard_issue_decision,
    open_blocking_issue_ids,
    open_statutory_blocker_ids,
    permitted_states,
    reopen_state,
    reopens_on_new_evidence,
)
from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckOutcome,
    IssueSeverity,
    IssueState,
    RtaWorkflowRole,
)

_NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def _issue(
    *,
    issue_id: str = "iss_synthetic_1",
    severity: IssueSeverity = IssueSeverity.BLOCKING,
    blocker_kind: BlockerKind = BlockerKind.EVIDENCE,
    state: IssueState = IssueState.OPEN,
    evidence: tuple[str, ...] = (),
) -> LegalIssue:
    return LegalIssue(
        id=issue_id,
        user_id="usr_synthetic",
        matter_id="mat_synthetic",
        issue_type_id="rta.issue.synthetic",
        severity=severity,
        blocker_kind=blocker_kind,
        state=state,
        summary_key="rta.issue.synthetic.summary",
        created_at=_NOW,
        updated_at=_NOW,
        evidence_reference_ids=evidence,
    )


# ── Which dispositions each blocker kind can reach (§10.6) ───────────────────


def test_a_statutory_blocker_can_never_reach_accepted_risk() -> None:
    assert IssueState.ACCEPTED_RISK not in permitted_states(BlockerKind.STATUTORY)


def test_a_statutory_blocker_is_not_a_scope_decision_either() -> None:
    """It is a defect in the proposed transaction, not a Draftly-scope question."""
    assert IssueState.OUTSIDE_SCOPE not in permitted_states(BlockerKind.STATUTORY)


@pytest.mark.parametrize(
    "blocker_kind", [BlockerKind.OFFICE_POLICY, BlockerKind.PROFESSIONAL_JUDGMENT]
)
def test_overridable_blockers_can_reach_accepted_risk(blocker_kind: BlockerKind) -> None:
    assert IssueState.ACCEPTED_RISK in permitted_states(blocker_kind)


def test_an_evidence_blocker_closes_only_by_resolution() -> None:
    states = permitted_states(BlockerKind.EVIDENCE)
    assert IssueState.RESOLVED in states
    assert IssueState.ACCEPTED_RISK not in states
    assert IssueState.OUTSIDE_SCOPE not in states


def test_a_v0_scope_blocker_closes_as_outside_scope() -> None:
    states = permitted_states(BlockerKind.V0_SCOPE)
    assert IssueState.OUTSIDE_SCOPE in states
    assert IssueState.ACCEPTED_RISK not in states


# ── The hard refusal ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", list(RtaWorkflowRole))
def test_no_role_can_accept_risk_on_a_statutory_blocker(role: RtaWorkflowRole) -> None:
    issue = _issue(blocker_kind=BlockerKind.STATUTORY)
    with pytest.raises(StatutoryRiskNotAcceptableError) as raised:
        guard_issue_decision(issue, IssueState.ACCEPTED_RISK, role, "The client accepts the risk.")
    assert raised.value.code == "rta_statutory_blocker_not_overridable"
    assert raised.value.http_status == 422


def test_a_statutory_blocker_still_refuses_acceptance_with_a_long_rationale() -> None:
    """No amount of reason turns a statutory prohibition into an accepted risk."""
    issue = _issue(blocker_kind=BlockerKind.STATUTORY)
    with pytest.raises(StatutoryRiskNotAcceptableError):
        guard_issue_decision(
            issue,
            IssueState.ACCEPTED_RISK,
            RtaWorkflowRole.RESPONSIBLE_LAWYER,
            "Counsel has advised at length that the parties accept the section 47 position.",
        )


# ── Who may accept, and on what terms (§7.3) ─────────────────────────────────


def test_an_office_admin_may_accept_an_office_policy_risk_with_a_reason() -> None:
    issue = _issue(blocker_kind=BlockerKind.OFFICE_POLICY, severity=IssueSeverity.WARNING)
    guard_issue_decision(
        issue,
        IssueState.ACCEPTED_RISK,
        RtaWorkflowRole.OFFICE_ADMIN,
        "Office rule set does not require a rates receipt for this council.",
    )


def test_an_acceptance_without_a_reason_is_refused() -> None:
    issue = _issue(blocker_kind=BlockerKind.OFFICE_POLICY, severity=IssueSeverity.WARNING)
    with pytest.raises(IssueDecisionReasonRequiredError):
        guard_issue_decision(issue, IssueState.ACCEPTED_RISK, RtaWorkflowRole.OFFICE_ADMIN, "   ")


def test_a_case_assistant_may_not_accept_an_office_policy_risk() -> None:
    issue = _issue(blocker_kind=BlockerKind.OFFICE_POLICY, severity=IssueSeverity.WARNING)
    with pytest.raises(IssueDecisionRoleRequiredError):
        guard_issue_decision(
            issue, IssueState.ACCEPTED_RISK, RtaWorkflowRole.CASE_ASSISTANT, "Looks fine."
        )


def test_only_the_responsible_lawyer_may_accept_a_professional_judgment_risk() -> None:
    issue = _issue(blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT, severity=IssueSeverity.HIGH_RISK)
    guard_issue_decision(
        issue,
        IssueState.ACCEPTED_RISK,
        RtaWorkflowRole.RESPONSIBLE_LAWYER,
        "Extent variance is within the tolerance recorded on the file.",
    )
    with pytest.raises(IssueDecisionRoleRequiredError):
        guard_issue_decision(
            issue,
            IssueState.ACCEPTED_RISK,
            RtaWorkflowRole.OFFICE_ADMIN,
            "Extent variance is within tolerance.",
        )


def test_an_evidence_blocker_cannot_be_accepted_at_all() -> None:
    issue = _issue(blocker_kind=BlockerKind.EVIDENCE)
    with pytest.raises(IssueStateNotPermittedError):
        guard_issue_decision(
            issue,
            IssueState.ACCEPTED_RISK,
            RtaWorkflowRole.RESPONSIBLE_LAWYER,
            "The bank confirmed by telephone.",
        )


def test_resolving_an_evidence_blocker_requires_new_evidence() -> None:
    """Absence of a document is not proof that the concern has gone away (§6.4)."""
    issue = _issue(blocker_kind=BlockerKind.EVIDENCE)
    with pytest.raises(IssueResolutionRequiresEvidenceError):
        guard_issue_decision(issue, IssueState.RESOLVED, RtaWorkflowRole.RESPONSIBLE_LAWYER, None)
    guard_issue_decision(
        issue,
        IssueState.RESOLVED,
        RtaWorkflowRole.RESPONSIBLE_LAWYER,
        None,
        new_evidence_reference_ids=("ev_synthetic_1",),
    )


def test_moving_a_v0_scope_issue_out_of_scope_is_a_senior_decision() -> None:
    issue = _issue(blocker_kind=BlockerKind.V0_SCOPE)
    guard_issue_decision(
        issue,
        IssueState.OUTSIDE_SCOPE,
        RtaWorkflowRole.RESPONSIBLE_LAWYER,
        "Attorney-executed transfer moves to the manual-supported workflow.",
    )
    with pytest.raises(IssueDecisionRoleRequiredError):
        guard_issue_decision(
            issue,
            IssueState.OUTSIDE_SCOPE,
            RtaWorkflowRole.LAWYER_REVIEWER,
            "Moving to the manual workflow.",
        )


def test_triage_states_are_open_to_any_role() -> None:
    issue = _issue()
    for state in (IssueState.TRIAGED, IssueState.ACTION_REQUIRED):
        guard_issue_decision(issue, state, RtaWorkflowRole.CASE_ASSISTANT, None)


# ── An acceptance is a separate disposition (§7.3) ───────────────────────────


def test_accepting_a_risk_never_rewrites_the_check_outcome() -> None:
    result = CheckResult(
        id="chk_synthetic_1",
        user_id="usr_synthetic",
        matter_id="mat_synthetic",
        check_definition_id="CHK_EXTENT",
        check_definition_version="1.0.0",
        run_id="run_synthetic_1",
        outcome=CheckOutcome.FAIL,
        default_severity=IssueSeverity.HIGH_RISK,
        explanation_key="rta.check.CHK_EXTENT.explanation.extent_discrepancy",
        created_at=_NOW,
    )
    accepted = _issue(
        blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
        severity=IssueSeverity.HIGH_RISK,
        state=IssueState.ACCEPTED_RISK,
    )
    assert accepted_risk_does_not_change_outcome(result, accepted) is CheckOutcome.FAIL


# ── The three gates (§7.3) ───────────────────────────────────────────────────


def test_a_blocking_issue_permits_neither_a_draft_nor_an_approval() -> None:
    issues = [_issue(severity=IssueSeverity.BLOCKING)]
    assert blocks_draft_generation(issues) is True
    assert blocks_approval(issues) is True
    assert blocks_registration_ready_export(issues) is True


def test_a_high_risk_issue_permits_a_working_draft_but_not_approval() -> None:
    """§7.3 — withholding the draft would hide the analysis the lawyer needs."""
    issues = [_issue(severity=IssueSeverity.HIGH_RISK)]
    assert blocks_draft_generation(issues) is False
    assert blocks_approval(issues) is True
    assert blocks_registration_ready_export(issues) is True


def test_an_unacknowledged_warning_stops_only_the_registration_ready_export() -> None:
    issues = [_issue(severity=IssueSeverity.WARNING)]
    assert blocks_draft_generation(issues) is False
    assert blocks_approval(issues) is False
    assert blocks_registration_ready_export(issues) is True


def test_an_acknowledged_warning_stops_nothing() -> None:
    issues = [_issue(severity=IssueSeverity.WARNING, state=IssueState.TRIAGED)]
    assert blocks_registration_ready_export(issues) is False


def test_an_information_issue_stops_nothing() -> None:
    issues = [_issue(severity=IssueSeverity.INFORMATION)]
    assert blocks_registration_ready_export(issues) is False


def test_an_accepted_high_risk_clears_approval() -> None:
    issues = [_issue(severity=IssueSeverity.HIGH_RISK, state=IssueState.ACCEPTED_RISK)]
    assert blocks_approval(issues) is False


def test_an_accepted_blocking_issue_still_blocks() -> None:
    """Defence in depth: the guard refuses this, and the gate ignores it anyway."""
    issues = [_issue(severity=IssueSeverity.BLOCKING, state=IssueState.ACCEPTED_RISK)]
    assert blocks_draft_generation(issues) is True
    assert blocks_approval(issues) is True


def test_an_out_of_scope_issue_keeps_the_matter_out_of_automated_output() -> None:
    issues = [_issue(severity=IssueSeverity.BLOCKING, state=IssueState.OUTSIDE_SCOPE)]
    assert blocks_draft_generation(issues) is True


@pytest.mark.parametrize("state", [IssueState.RESOLVED, IssueState.FALSE_POSITIVE])
def test_a_closed_issue_stops_nothing(state: IssueState) -> None:
    issues = [_issue(severity=IssueSeverity.BLOCKING, state=state)]
    assert blocks_draft_generation(issues) is False
    assert blocks_approval(issues) is False
    assert blocks_registration_ready_export(issues) is False


def test_statutory_and_blocking_ids_are_reported_separately() -> None:
    statutory = _issue(
        issue_id="iss_statutory",
        severity=IssueSeverity.BLOCKING,
        blocker_kind=BlockerKind.STATUTORY,
    )
    evidence = _issue(issue_id="iss_evidence", severity=IssueSeverity.BLOCKING)
    high_risk = _issue(
        issue_id="iss_high_risk",
        severity=IssueSeverity.HIGH_RISK,
        blocker_kind=BlockerKind.STATUTORY,
    )
    issues = [statutory, evidence, high_risk]
    assert open_statutory_blocker_ids(issues) == ("iss_statutory", "iss_high_risk")
    assert open_blocking_issue_ids(issues) == ("iss_statutory", "iss_evidence")


# ── Reopening (§10.6) ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "state", [IssueState.RESOLVED, IssueState.FALSE_POSITIVE, IssueState.ACCEPTED_RISK]
)
def test_a_closed_issue_reopens_into_action_required(state: IssueState) -> None:
    assert reopen_state(_issue(state=state)) is IssueState.ACTION_REQUIRED


def test_reopening_an_open_issue_leaves_it_where_it_is() -> None:
    assert reopen_state(_issue(state=IssueState.TRIAGED)) is IssueState.TRIAGED


def test_only_evidence_the_issue_has_not_seen_reopens_it() -> None:
    issue = _issue(state=IssueState.RESOLVED, evidence=("ev_1",))
    assert reopens_on_new_evidence(issue, ("ev_1",)) is False
    assert reopens_on_new_evidence(issue, ("ev_1", "ev_2")) is True


def test_an_open_issue_is_never_reopened() -> None:
    issue = _issue(state=IssueState.OPEN, evidence=("ev_1",))
    assert reopens_on_new_evidence(issue, ("ev_2",)) is False
