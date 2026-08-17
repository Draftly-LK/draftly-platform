"""Check module ports.

The application service depends on these protocols only. `ConfirmedFactReadPort`
comes from `verification.contracts` rather than being redeclared here: the fact
tier belongs to verification, and the check engine may read it but never write
it (plan §5.1).
"""

from __future__ import annotations

from typing import Protocol

from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.content_governance.contracts import IssueSeverity, IssueState


class CheckRepository(Protocol):
    """Immutable check results and the mutable issues they raise.

    Every method takes ``user_id`` first because that is the tenancy boundary in
    this deployment: no query reaches a row without it (plan §5.3 invariant 10).
    """

    async def create_results(self, results: list[CheckResult]) -> list[CheckResult]:
        """Append one run's results. Results are never updated in place (§7.1)."""
        ...

    async def list_results(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[CheckResult], str | None]: ...

    async def create_issue(self, issue: LegalIssue) -> LegalIssue: ...

    async def get_issue(self, user_id: str, issue_id: str) -> LegalIssue | None: ...

    async def list_issues(
        self,
        user_id: str,
        matter_id: str,
        *,
        severity: IssueSeverity | None,
        state: IssueState | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[LegalIssue], str | None]: ...

    async def list_all_issues(self, user_id: str, matter_id: str) -> list[LegalIssue]:
        """Every issue on the matter, for the gates and for run reconciliation.

        Unpaginated on purpose: this feeds a server-side decision, not a
        response body, and a partial page would silently under-report a blocker.
        """
        ...

    async def update_issue(self, issue: LegalIssue, expected_version: int) -> LegalIssue:
        """Persist and bump ``version``; raise on a stale ``expected_version``."""
        ...
