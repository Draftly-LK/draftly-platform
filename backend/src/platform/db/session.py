"""SQLAlchemy async engine, session factory, and FastAPI dependency.

Uses the POOLED database URL for the app runtime.
Migrations use DATABASE_URL_DIRECT (unpooled) via alembic env.py.

Per infrastructure.md: sslmode=require and channel_binding=require are in the
connection string itself, so we do not add them here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.platform.config import get_settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "local",
            pool_pre_ping=True,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with get_session_maker()() as session:
        yield session


async def check_db_ready() -> bool:
    """Probe the DB for the /health/ready route — leaks no credentials."""
    try:
        async with get_session_maker()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
