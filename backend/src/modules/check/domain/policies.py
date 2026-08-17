"""Issue dispositions and the three gates. This file is the correctness core.

Four rules carry the legal safety of the check engine (§7.3, §10.6):

1. **A statutory blocker can never be accepted as a risk.** `permitted_states`
   omits ``ACCEPTED_RISK`` for ``STATUTORY`` and `guard_issue_decision` refuses
   it with its own error code, whatever role asks.
2. **An accepted risk is a separate disposition.** It is recorded on the issue
   and never rewrites the check's ``outcome``, which is why
   `accepted_risk_does_not_change_outcome` exists as a named, tested function
   rather than as a comment.
3. **Who may accept depends on the blocker kind.** ``OFFICE_POLICY`` may be
   overridden by an office admin or the responsible lawyer with a reason;
   ``PROFESSIONAL_JUDGMENT`` only by the responsible lawyer, with a recorded
   rationale; ``EVIDENCE`` closes only through ``RESOLVED`` with new evidence;
   ``V0_SCOPE`` closes as ``OUTSIDE_SCOPE`` and the matter becomes
   manual-supported.
4. **The three gates are distinct.** A ``HIGH_RISK`` issue permits a
   watermarked working draft but not approval; a ``BLOCKING`` issue permits
   neither; and registration-ready export additionally waits for warnings to be
   acknowledged.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.modules.check.domain.errors import (
    IssueDecisionReasonRequiredError,
    IssueDecisionRoleRequiredError,
    IssueResolutionRequiresEvidenceError,
    IssueStateNotPermittedError,
    StatutoryRiskNotAcceptableError,
)
from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckOutcome,
    IssueSeverity,
    IssueState,
    RtaWorkflowRole,
)

#: Every blocker kind can be worked through triage and can be closed as
#: resolved or as a false positive. What differs is which *exit* is available
#: beyond those (§10.6).
_COMMON_STATES: frozenset[IssueState] = frozenset(
    {
        IssueState.OPEN,
        IssueState.TRIAGED,
        IssueState.ACTION_REQUIRED,
        IssueState.RESOLVED,
        IssueState.FALSE_POSITIVE,
    }
)

_PERMITTED_STATES: dict[BlockerKind, frozenset[IssueState]] = {
    # No ACCEPTED_RISK and no OUTSIDE_SCOPE: a statutory incompatibility is not
    # a scope decision either, it is a defect in the proposed transaction.
    BlockerKind.STATUTORY: _COMMON_STATES,
    BlockerKind.EVIDENCE: _COMMON_STATES,
    BlockerKind.V0_SCOPE: _COMMON_STATES | {IssueState.OUTSIDE_SCOPE},
    BlockerKind.OFFICE_POLICY: _COMMON_STATES | {IssueState.ACCEPTED_RISK},
    BlockerKind.PROFESSIONAL_JUDGMENT: _COMMON_STATES | {IssueState.ACCEPTED_RISK},
}

#: Who may record an ``ACCEPTED_RISK`` disposition, per blocker kind (§7.3).
_ACCEPTORS: dict[BlockerKind, frozenset[RtaWorkflowRole]] = {
    BlockerKind.OFFICE_POLICY: frozenset(
        {RtaWorkflowRole.OFFICE_ADMIN, RtaWorkflowRole.RESPONSIBLE_LAWYER}
    ),
    BlockerKind.PROFESSIONAL_JUDGMENT: frozenset({RtaWorkflowRole.RESPONSIBLE_LAWYER}),
}

#: Ending the automated workflow is a responsible-lawyer decision, not a triage
#: convenience: the matter moves to manual-supported (§2.3, §10.6).
_OUTSIDE_SCOPE_ROLES: frozenset[RtaWorkflowRole] = frozenset(
    {RtaWorkflowRole.RESPONSIBLE_LAWYER, RtaWorkflowRole.OFFICE_ADMIN}
)

_REASON_REQUIRED_STATES: frozenset[IssueState] = frozenset(
    {IssueState.ACCEPTED_RISK, IssueState.FALSE_POSITIVE, IssueState.OUTSIDE_SCOPE}
)


def permitted_states(blocker_kind: BlockerKind) -> frozenset[IssueState]:
    """The dispositions this blocker kind can legitimately reach (§10.6)."""
    return _PERMITTED_STATES[blocker_kind]


def guard_issue_decision(
    issue: LegalIssue,
    target_state: IssueState,
    actor_workflow_role: RtaWorkflowRole,
    reason: str | None,
    *,
    new_evidence_reference_ids: tuple[str, ...] = (),
) -> None:
    """Refuse a disposition the blocker kind, the role, or the record forbids.

    Raises rather than returning a verdict so no caller can proceed by ignoring
    a falsy result.
    """
    if target_state is IssueState.ACCEPTED_RISK and issue.blocker_kind is BlockerKind.STATUTORY:
        raise StatutoryRiskNotAcceptableError(
            issueId=issue.id,
            issueTypeId=issue.issue_type_id,
            blockerKind=issue.blocker_kind.value,
        )
    if target_state not in permitted_states(issue.blocker_kind):
        raise IssueStateNotPermittedError(
            issueId=issue.id,
            blockerKind=issue.blocker_kind.value,
            targetState=target_state.value,
            permitted=sorted(s.value for s in permitted_states(issue.blocker_kind)),
        )
    if target_state in _REASON_REQUIRED_STATES and not (reason or "").strip():
        raise IssueDecisionReasonRequiredError(issueId=issue.id, targetState=target_state.value)
    if target_state is IssueState.ACCEPTED_RISK and actor_workflow_role not in _ACCEPTORS.get(
        issue.blocker_kind, frozenset()
    ):
        raise IssueDecisionRoleRequiredError(
            issueId=issue.id,
            blockerKind=issue.blocker_kind.value,
            workflowRole=actor_workflow_role.value,
        )
    if target_state is IssueState.OUTSIDE_SCOPE and actor_workflow_role not in _OUTSIDE_SCOPE_ROLES:
        raise IssueDecisionRoleRequiredError(
            issueId=issue.id,
            targetState=target_state.value,
            workflowRole=actor_workflow_role.value,
        )
    if (
        target_state is IssueState.RESOLVED
        and issue.blocker_kind is BlockerKind.EVIDENCE
        and not new_evidence_reference_ids
    ):
        raise IssueResolutionRequiresEvidenceError(
            issueId=issue.id, issueTypeId=issue.issue_type_id
        )


def accepted_risk_does_not_change_outcome(
    result: CheckResult, accepted_issue: LegalIssue
) -> CheckOutcome:
    """Return the check's outcome, unchanged by any acceptance on its issue.

    §7.3: "Accepted risk never changes a failed deterministic check to PASS; it
    records a separate disposition." The invariant is expressed as a function so
    it can be asserted in a test, and so that the only way to learn a check's
    outcome after an acceptance is through code that visibly ignores the
    acceptance. The issue argument is deliberately unused.
    """
    _ = accepted_issue
    return result.outcome


# ── Gates (§7.3) ─────────────────────────────────────────────────────────────


def _stands(issue: LegalIssue) -> bool:
    """Whether this issue still constrains automated output.

    An acceptance clears a ``HIGH_RISK`` or lower concern, which is exactly what
    §7.3 permits an authorised lawyer to do. It does not clear a ``BLOCKING``
    one: that row of the table has no acceptance column at all — the answer is
    evidence, a lawful structure, or the manual workflow.
    """
    if issue.state in {IssueState.RESOLVED, IssueState.FALSE_POSITIVE}:
        return False
    if issue.state is IssueState.ACCEPTED_RISK:
        return issue.severity is IssueSeverity.BLOCKING
    return True


def standing_issues(issues: Iterable[LegalIssue]) -> tuple[LegalIssue, ...]:
    return tuple(issue for issue in issues if _stands(issue))


def blocks_draft_generation(issues: Iterable[LegalIssue]) -> bool:
    """Only ``BLOCKING`` stops generation.

    A ``HIGH_RISK`` issue still allows the watermarked working draft §7.3
    describes; withholding it would hide the very analysis the lawyer needs.
    """
    return any(issue.severity is IssueSeverity.BLOCKING for issue in standing_issues(issues))


def blocks_approval(issues: Iterable[LegalIssue]) -> bool:
    """``HIGH_RISK`` and ``BLOCKING`` both stop approval until disposed of."""
    return any(
        issue.severity in {IssueSeverity.BLOCKING, IssueSeverity.HIGH_RISK}
        for issue in standing_issues(issues)
    )


def blocks_registration_ready_export(issues: Iterable[LegalIssue]) -> bool:
    """Approval's gate, plus warnings nobody has looked at yet.

    §7.3 allows a ``WARNING`` through "only after acknowledgement if policy
    requires". Acknowledgement is modelled as the issue having left ``OPEN``:
    an untouched warning on a registration-ready export is an unreviewed
    warning.
    """
    if blocks_approval(issues):
        return True
    return any(
        issue.severity is IssueSeverity.WARNING and issue.state is IssueState.OPEN
        for issue in standing_issues(issues)
    )


def open_statutory_blocker_ids(issues: Iterable[LegalIssue]) -> tuple[str, ...]:
    return tuple(
        issue.id for issue in standing_issues(issues) if issue.blocker_kind is BlockerKind.STATUTORY
    )


def open_blocking_issue_ids(issues: Iterable[LegalIssue]) -> tuple[str, ...]:
    return tuple(
        issue.id for issue in standing_issues(issues) if issue.severity is IssueSeverity.BLOCKING
    )


def reopen_state(issue: LegalIssue) -> IssueState:
    """The state a closed issue returns to when contrary evidence arrives.

    §10.6 lets new contrary evidence reopen a resolution, and reopening is never
    the risky direction — so it is permitted from any state, including a
    statutory one, and the previous disposition stays in the audit trail.
    """
    return IssueState.ACTION_REQUIRED if issue.is_closed else issue.state


def reopens_on_new_evidence(issue: LegalIssue, evidence_reference_ids: Iterable[str]) -> bool:
    """Whether a failing rerun brings evidence the closed issue has not seen.

    "New" is literal. An identical rerun over the same references must not churn
    a disposition a lawyer already recorded, so only references absent from the
    issue reopen it (§10.6).
    """
    if not issue.is_closed:
        return False
    return bool(set(evidence_reference_ids) - set(issue.evidence_reference_ids))
