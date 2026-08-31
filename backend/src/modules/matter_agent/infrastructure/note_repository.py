"""Persistence for non-authoritative matter working notes."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.matter_agent.infrastructure.orm import MatterNoteRow
from src.platform import ids


class SqlMatterNoteRepository:
    """Writes ``matter_notes``. ``origin`` records who authored the note."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create_note(
        self,
        *,
        user_id: str,
        matter_id: str,
        author_id: str,
        body: str,
        origin: str,
        session_id: str | None,
    ) -> str:
        note_id = ids.new_id(ids.MATTER_NOTE)
        self._db.add(
            MatterNoteRow(
                id=note_id,
                user_id=user_id,
                matter_id=matter_id,
                author_id=author_id,
                body=body,
                origin=origin,
                session_id=session_id,
                created_at=datetime.now(tz=UTC),
            )
        )
        await self._db.flush()
        return note_id
