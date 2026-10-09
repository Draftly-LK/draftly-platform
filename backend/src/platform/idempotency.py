"""Application port for the shared transactional replay store."""

import hashlib
import json
from typing import Any, Protocol


def fingerprint(body: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class IdempotencyPort(Protocol):
    async def find(
        self, *, user_id: str, route: str, key: str, request_hash: str
    ) -> dict[str, Any] | None: ...
    async def store(
        self,
        *,
        record_id: str,
        user_id: str,
        route: str,
        key: str,
        request_hash: str,
        response: dict[str, Any],
    ) -> None: ...
