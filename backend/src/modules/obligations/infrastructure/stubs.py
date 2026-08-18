"""In-memory stubs for obligations ports used in unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.modules.obligations.domain.models import Obligation, ReminderOccurrence
from src.modules.obligations.ports import (
    NotificationReminderIntent,
    ObligationListFilters,
    ObligationRepository,
    OutboxEvent,
    ReminderRepository,
)


class InMemoryObligationRepository(ObligationRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, Obligation] = {}

    async def create(self, obligation: Obligation) -> Obligation:
        self._by_id[obligation.id] = obligation
        return obligation

    async def update(self, obligation: Obligation) -> Obligation:
        self._by_id[obligation.id] = obligation
        return obligation

    async def get(self, organisation_id: str, obligation_id: str) -> Obligation | None:
        row = self._by_id.get(obligation_id)
        if row is None or row.organisation_id != organisation_id:
            return None
        return row

    async def list_for_organisation(
        self,
        organisation_id: str,
        filters: ObligationListFilters,
    ) -> tuple[list[Obligation], str | None, bool]:
        items = [o for o in self._by_id.values() if o.organisation_id == organisation_id]
        if filters.assignee_user_id:
            items = [o for o in items if o.assignee_user_id == filters.assignee_user_id]
        if filters.matter_id:
            items = [o for o in items if o.matter_id == filters.matter_id]
        if filters.status:
            items = [o for o in items if o.status.value == filters.status]
        items.sort(key=lambda o: o.due_at)
        limit = min(filters.limit, 100)
        page = items[:limit]
        has_more = len(items) > limit
        next_cursor = page[-1].id if has_more and page else None
        return page, next_cursor, has_more


class InMemoryReminderRepository(ReminderRepository):
    def __init__(self) -> None:
        self._rows: list[ReminderOccurrence] = []

    async def create(self, occurrence: ReminderOccurrence) -> ReminderOccurrence:
        self._rows.append(occurrence)
        return occurrence

    async def find_existing(
        self,
        obligation_id: str,
        recipient_user_id: str,
        reminder_type: str,
    ) -> ReminderOccurrence | None:
        for row in self._rows:
            if (
                row.obligation_id == obligation_id
                and row.recipient_user_id == recipient_user_id
                and row.reminder_type.value == reminder_type
            ):
                return row
        return None

    async def list_for_obligation(self, obligation_id: str) -> list[ReminderOccurrence]:
        return [r for r in self._rows if r.obligation_id == obligation_id]


class RecordingEventPort:
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    async def append(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FixedClockPort:
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed


class SystemClockPort:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class RecordingNotificationIntentPort:
    def __init__(self) -> None:
        self.intents: list[NotificationReminderIntent] = []

    async def record_reminder_intent(self, intent: NotificationReminderIntent) -> None:
        self.intents.append(intent)
