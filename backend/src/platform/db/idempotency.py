"""``Idempotency-Key`` replay store (api-conventions.md §4).

A creating POST stores ``(user_id, route, key) -> response`` for 24 hours. A
repeat with the same body replays the stored response; a repeat with a
different body is a 409.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base
from src.platform.errors import ConflictError, DraftlyError

RETENTION = timedelta(hours=24)

_JSON_COLUMN = JSONB().with_variant(JSON(), "sqlite")


class IdempotencyKeyRow(Base):
    __tablename__ = "api_idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "route", "idempotency_key", name="uq_idempotency_scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(_JSON_COLUMN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyConflictError(ConflictError):
    code = "idempotency_key_conflict"
    message = "This Idempotency-Key was already used with a different request body."


class IdempotencyKeyRequiredError(DraftlyError):
    code = "idempotency_key_required"
    http_status = 400
    message = "This request requires an Idempotency-Key header."


def request_fingerprint(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SqlIdempotencyStore:
    """Reads and writes replay records on the caller's session and transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(
        self, *, user_id: str, route: str, key: str, request_hash: str
    ) -> dict[str, Any] | None:
        """Return the stored response for a replay, or None for a first attempt.

        Raises IdempotencyConflictError when the same key arrives with a
        different body.
        """
        stmt = (
            select(IdempotencyKeyRow)
            .where(
                IdempotencyKeyRow.user_id == user_id,
                IdempotencyKeyRow.route == route,
                IdempotencyKeyRow.idempotency_key == key,
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.created_at.tzinfo is not None and datetime.now(tz=UTC) - row.created_at > RETENTION:
            return None
        if row.request_hash != request_hash:
            raise IdempotencyConflictError()
        return row.response

    async def store(
        self,
        *,
        record_id: str,
        user_id: str,
        route: str,
        key: str,
        request_hash: str,
        response: dict[str, Any],
    ) -> None:
        self._session.add(
            IdempotencyKeyRow(
                id=record_id,
                user_id=user_id,
                route=route,
                idempotency_key=key,
                request_hash=request_hash,
                response=response,
            )
        )
        await self._session.flush()
