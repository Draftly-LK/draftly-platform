"""Advance the matter state from an act recorded in another module (§10.1).

The approval module names the state a recorded act implies; this module owns the
state machine and decides whether the matter may go there. The adapter satisfies
``approval.ports.MatterWorkflowCommandPort`` structurally — that protocol is not
imported, because a module may only import another module's ``contracts``.

An illegal transition is **logged and refused, not raised**. The approval, export,
or registration event is the legally meaningful record and it has already been
written; the matter state is derived from it. Raising here would roll back a
lawyer's recorded act because a derived field could not follow — for example a
matter on ``LITIGATION_HOLD``, where refusing to jump to ``APPROVED`` is exactly
the behaviour the guard exists for.
"""

from __future__ import annotations

from dataclasses import replace

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.domain.enums import MatterState
from src.modules.matter.domain.models import is_transition_allowed
from src.modules.matter.infrastructure.repository import SqlMatterRepository

log = structlog.get_logger(__name__)


class SqlMatterWorkflowCommandAdapter:
    """Moves a matter through its §10.1 states on behalf of a recorded act."""

    def __init__(self, session: AsyncSession) -> None:
        self._matters = SqlMatterRepository(session)

    async def advance_state(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None:
        matter = await self._matters.get(user_id, matter_id)
        if matter is None:
            # The caller resolved this matter through its own access check a
            # moment ago, so this is a deleted-underneath race rather than an
            # authorization question. Nothing to advance.
            log.warning("matter.advance_state.matter_missing", matter_id=matter_id)
            return

        if matter.rta_state is state:
            return

        if not is_transition_allowed(matter.rta_state, state):
            log.warning(
                "matter.advance_state.refused",
                matter_id=matter_id,
                from_state=matter.rta_state.value,
                to_state=state.value,
                reason=reason,
            )
            return

        await self._matters.update(replace(matter, rta_state=state), matter.version)


#: The ordinary §10.1 path from review to approval, one step at a time.
_DRAFTING_PATH: tuple[MatterState, ...] = (
    MatterState.LEGAL_REVIEW,
    MatterState.READY_TO_DRAFT,
    MatterState.DRAFTING,
    MatterState.APPROVAL_PENDING,
    MatterState.APPROVED,
)


class DemoMatterWorkflowCommandAdapter(SqlMatterWorkflowCommandAdapter):
    """``DEMO_RELAXED_GATES`` only: walk the review-to-approval path in order.

    With the demo gates relaxed, the gate each step waits on has already passed
    by the time a later act names a later state (a form generated, a form
    approved), so the matter takes every step between, each one still checked
    against the transition table. Off this path it behaves exactly like the
    base adapter.
    """

    async def advance_state(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None:
        if state in _DRAFTING_PATH:
            matter = await self._matters.get(user_id, matter_id)
            if matter is not None and matter.rta_state in _DRAFTING_PATH:
                start = _DRAFTING_PATH.index(matter.rta_state) + 1
                for step in _DRAFTING_PATH[start : _DRAFTING_PATH.index(state)]:
                    await super().advance_state(
                        user_id=user_id, matter_id=matter_id, state=step, reason=reason
                    )
        await super().advance_state(
            user_id=user_id, matter_id=matter_id, state=state, reason=reason
        )


__all__ = ["DemoMatterWorkflowCommandAdapter", "SqlMatterWorkflowCommandAdapter"]
