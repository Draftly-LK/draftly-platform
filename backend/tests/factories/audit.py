"""The one in-memory ``AuditPort``."""

from __future__ import annotations

from src.modules.auth.ports import AuditEventInput


class FakeAudit:
    """Implements ``AuditPort``. Records the events for assertion.

    Emission is the observable behaviour here: an unaudited mutation is the
    bug, so asserting on ``events`` or ``actions()`` is a legitimate target.
    """

    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)

    def actions(self) -> list[str]:
        return [event.action for event in self.events]
