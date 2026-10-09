"""Explicit requirement-command replay, called only after resource authorization.

Responses describe a completed command. A replay is historical; callers read
the current resource before presenting eligibility. No middleware or auth cache.
"""

from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.db.idempotency import IdempotencyKeyRequiredError, SqlIdempotencyStore
from src.platform.idempotency import fingerprint
from src.platform.ids import new_id

ReadModel = TypeVar("ReadModel", bound=BaseModel)


class RequirementCommandReplay:
    def __init__(
        self,
        session: AsyncSession,
        user_id: str,
        route: str,
        key: str | None,
        payload: dict[str, Any],
    ) -> None:
        if not key or len(key) > 255:
            raise IdempotencyKeyRequiredError()
        self._store = SqlIdempotencyStore(session)
        self._scope = {
            "user_id": user_id,
            "route": route,
            "key": key,
            "request_hash": fingerprint(payload),
        }

    async def find(self, model: type[ReadModel]) -> ReadModel | None:
        cached = await self._store.find(**self._scope)
        return model.model_validate(cached) if cached is not None else None

    async def save(self, value: ReadModel) -> ReadModel:
        await self._store.store(
            record_id=new_id("replay"), **self._scope, response=value.model_dump(mode="json")
        )
        return value
