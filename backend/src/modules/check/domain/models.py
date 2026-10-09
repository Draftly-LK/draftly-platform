"""Check-result and legal-issue entities.

A `CheckResult` is immutable. Re-running a check after a fact changes appends a
new result pinned to the new fact versions rather than editing the old one, so
the state a conclusion was drawn under stays reconstructible (§7.1, §12.2).

A `LegalIssue` is the mutable half: it carries the lifecycle a lawyer works
through (§10.6). Its `severity` and `blocker_kind` start from the check
definition and are only ever changed by a recorded human decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckOutcome,
    IssueSeverity,
    IssueState,
)


@dataclass(frozen=True)
class FactVersionPin:
    """One input fact and the version the check actually read.

    Stored per result so a later fact correction is visible as a different
    input set rather than silently reinterpreting the old conclusion.
    """

    fact_id: str
    version: int


@dataclass(frozen=True)
class CheckResult:
    """One deterministic comparison, as it stood at one moment."""

    id: str
    user_id: str
    matter_id: str
    check_definition_id: str
    check_definition_version: str
    run_id: str
    outcome: CheckOutcome
    default_severity: IssueSeverity
    explanation_key: str
    created_at: datetime
    input_fact_versions: tuple[FactVersionPin, ...] = field(default_factory=tuple)
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    #: §7.1 — a PASS on all but the mechanical completeness check still needs a
    #: lawyer's conclusion before it carries weight.
    requires_human_conclusion: bool = True
    transaction_id: str | None = None
    subject_id: str | None = None
    association_version: int | None = None


@dataclass
class LegalIssue:
    """A red flag raised by a check, worked through the §10.6 lifecycle."""

    id: str
    user_id: str
    matter_id: str
    issue_type_id: str
    severity: IssueSeverity
    blocker_kind: BlockerKind
    state: IssueState
    summary_key: str
    created_at: datetime
    updated_at: datetime
    check_id: str | None = None
    source_record_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    assigned_to: str | None = None
    #: The recorded human decision that closed the issue, if any.
    resolution_decision_id: str | None = None
    resolution_reason: str | None = None
    version: int = 1
    transaction_id: str | None = None
    subject_id: str | None = None
    association_version: int | None = None

    @property
    def is_closed(self) -> bool:
        """Whether the issue no longer stands as an unanswered red flag.

        ``OUTSIDE_SCOPE`` is deliberately absent: it ends triage but keeps the
        matter out of automated output (§7.3 BLOCKING row, §10.6).
        """
        return self.state in {
            IssueState.RESOLVED,
            IssueState.FALSE_POSITIVE,
            IssueState.ACCEPTED_RISK,
        }
