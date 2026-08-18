"""Resolve recipient email from persisted user identities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.infrastructure.orm import UserIdentityRow


class SqlRecipientEmailResolver:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_email(self, user_id: str) -> str | None:
        stmt = (
            select(UserIdentityRow.verified_email)
            .where(UserIdentityRow.user_id == user_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
