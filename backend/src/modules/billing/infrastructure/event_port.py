"""In-memory event port for transactional outbox stub."""

from __future__ import annotations

from typing import Any


class InMemoryEventPort:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        self.events.append((event_name, payload))
