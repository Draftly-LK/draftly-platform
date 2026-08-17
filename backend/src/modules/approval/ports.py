"""Approval module ports.

The three repositories are this module's own storage. The two command ports are
not: they are shapes this module needs on aggregates it does not own, declared
here because the rule that needs them is implemented and tested rather than
deferred.

`GeneratedFormCommandPort` writes the two columns the drafting module reserved
for exactly this (`approved_artifact_hash`, `approval_id`) and marks a form stale
when a correction is detected after approval (§17). `MatterWorkflowCommandPort`
advances the §10.1 matter state on approval, on export of an approved snapshot,
and on a recorded presentation or registration.

Both are **optional** on the service. With neither wired, every legal fact this
module owns is still recorded — the approval row, the export row, the
registration event — and the two aggregates that belong to other modules simply
do not move. That is honest degradation: the alternative would be this module
reaching into another module's tables.
"""

from __future__ import annotations

from typing import Protocol

from src.modules.approval.domain.models import Approval, FormExport, RegistrationEvent
from src.modules.content_governance.contracts import MatterState


class ApprovalRepository(Protocol):
    """Append-only approvals.

    Every method takes ``user_id`` first because that is the tenancy boundary in
    this deployment: no query reaches a row without it (plan §5.3 invariant 10).
    There is no update path and no delete path; `revoke` writes the single field
    an approval ever changes.
    """

    async def create(self, approval: Approval) -> Approval: ...

    async def list_for_target(
        self, user_id: str, target_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Approval], str | None]:
        """Every approval of one target, newest first. Revoked ones included.

        History is the point: an auditor must be able to see the approval that
        was superseded, not only the one that replaced it.
        """
        ...

    async def current_for_target(self, user_id: str, target_id: str) -> Approval | None:
        """The newest approval of this target that has not been revoked."""
        ...

    async def revoke(self, user_id: str, approval_id: str, revoked_by_approval_id: str) -> None:
        """Point an approval at the one that superseded it. Never cleared."""
        ...


class FormExportRepository(Protocol):
    async def create(self, export: FormExport) -> FormExport: ...

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[FormExport], str | None]: ...


class RegistrationEventRepository(Protocol):
    async def create(self, event: RegistrationEvent) -> RegistrationEvent: ...

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[RegistrationEvent], str | None]: ...

    async def all_for_matter(self, user_id: str, matter_id: str) -> list[RegistrationEvent]:
        """Every event on the matter, oldest first.

        Unpaginated on purpose and only ever consumed inside the server: the
        ordering rules and the status fold need the whole sequence, and a matter
        accumulates a handful of registry events, not a feed.
        """
        ...


class GeneratedFormCommandPort(Protocol):
    """The two writes `draft` reserved for this module (§10.7).

    Implemented by the drafting module, which owns the form aggregate and its
    optimistic concurrency. Nothing here can change a binding.
    """

    async def record_approval(
        self,
        *,
        user_id: str,
        form_id: str,
        approval_id: str,
        approved_artifact_hash: str,
        expected_version: int,
    ) -> None:
        """Freeze the snapshot: write the approval id and hash, and set ``APPROVED``."""
        ...

    async def mark_stale(self, *, user_id: str, form_id: str, reason: str) -> None:
        """§17 — a correction after approval marks the form stale."""
        ...


class MatterWorkflowCommandPort(Protocol):
    """Advance the §10.1 matter state from a recorded act.

    Implemented by `matter`, which owns the state machine and remains free to
    refuse a transition. This module names the state the recorded act implies;
    it does not decide whether the matter may go there.
    """

    async def advance_state(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None: ...


__all__ = [
    "ApprovalRepository",
    "FormExportRepository",
    "GeneratedFormCommandPort",
    "MatterWorkflowCommandPort",
    "RegistrationEventRepository",
]
