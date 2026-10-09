"""The only surface other modules may import from check.

`draft`, `approval`, and `export` each need to know whether an open legal issue
currently stops them. They get one read port and a value object — never the
issue aggregate — so no downstream module can decide for itself that a blocker
has gone away, and none of them can create, reclassify, or close an issue.

The three booleans are separate because §7.3 makes them separate: a
``HIGH_RISK`` issue permits a watermarked working draft but not approval, and a
``BLOCKING`` issue permits neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class IssueGateSummary:
    """What the open issues on one matter currently forbid (§7.3)."""

    blocks_draft_generation: bool = False
    blocks_approval: bool = False
    blocks_registration_ready_export: bool = False
    #: Issues no role inside Draftly may override. Listed separately so a
    #: caller can render "this cannot be waived" rather than "ask someone else".
    open_statutory_blocker_ids: tuple[str, ...] = field(default_factory=tuple)
    open_blocking_issue_ids: tuple[str, ...] = field(default_factory=tuple)
    stale_check_ids: tuple[str, ...] = field(default_factory=tuple)


class IssueGatePort(Protocol):
    """Read the current issue gates for one matter."""

    async def gates(self, user_id: str, matter_id: str) -> IssueGateSummary: ...


class CheckInputInvalidationPort(Protocol):
    async def invalidate_inputs(
        self,
        *,
        user_id: str,
        matter_id: str,
        fact_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
    ) -> None: ...
