"""Adapters for the two narrow questions the agent asks other modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter.infrastructure.orm import MatterRow
from src.modules.task.infrastructure.orm import ChecklistItemRow


class SqlMatterAccessAdapter:
    """Answers ownership, and nothing else.

    Deliberately narrower than ``matter_service``: the agent needs to know
    whether this user owns this matter, and giving it a whole matter reader
    would let it read matters through a path with no capability check.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def owns_matter(self, *, user_id: str, matter_id: str) -> bool:
        found = (
            await self._db.execute(
                select(MatterRow.id).where(MatterRow.id == matter_id, MatterRow.user_id == user_id)
            )
        ).scalar_one_or_none()
        return found is not None


class SqlTargetVersionAdapter:
    """Current version of a pending action's target.

    ``target_ref`` is ``<aggregate>:<id>``. An unknown aggregate returns a
    version that can never match, so an unrecognised card fails closed as a
    stale 412 rather than confirming against nothing.
    """

    _UNRESOLVABLE = -1

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def current_version(self, *, matter_id: str, target_ref: str) -> int:
        aggregate, _, target_id = target_ref.partition(":")
        if aggregate == "checklist-item":
            version = (
                await self._db.execute(
                    select(ChecklistItemRow.version).where(
                        ChecklistItemRow.id == target_id,
                        ChecklistItemRow.matter_id == matter_id,
                    )
                )
            ).scalar_one_or_none()
            return int(version) if version is not None else self._UNRESOLVABLE
        if aggregate == "matter":
            version = (
                await self._db.execute(
                    select(MatterRow.version).where(
                        MatterRow.id == target_id, MatterRow.id == matter_id
                    )
                )
            ).scalar_one_or_none()
            return int(version) if version is not None else self._UNRESOLVABLE
        return self._UNRESOLVABLE
