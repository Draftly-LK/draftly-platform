"""Unit of Work — groups a set of repository operations under one transaction.

Application services obtain a UoW from the dependency injection layer and use
it as an async context manager. On success, ``__aexit__`` commits the
transaction automatically; callers do not need to call ``commit()`` on every
happy path. Use explicit ``commit()`` only when a mid-block early commit is
required. On any exception the context manager rolls back automatically.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Thin async context manager wrapping a SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
