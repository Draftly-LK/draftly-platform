"""Obligations module port definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.modules.obligations.domain.models import (
    ApprovedDeadlineRule,
    DeadlineCalculation,
    Obligation,
    ReminderOccurrence,
    ReminderScheduleSpec,
    TriggerType,
)


@dataclass(frozen=True)
class ObligationListFilters:
    matter_id: str | None = None
    assignee_user_id: str | None = None
    status: str | None = None
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True)
class OutboxEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, str | int | None]
    correlation_id: str


@dataclass(frozen=True)
class NotificationReminderIntent:
    obligation_id: str
    recipient_user_id: str
    reminder_type: str
    scheduled_for: datetime
    template_key: str


class ObligationRepository(Protocol):
    async def create(self, obligation: Obligation) -> Obligation: ...

    async def update(self, obligation: Obligation) -> Obligation: ...

    async def get(
        self,
        organisation_id: str,
        obligation_id: str,
    ) -> Obligation | None: ...

    async def list_for_organisation(
        self,
        organisation_id: str,
        filters: ObligationListFilters,
    ) -> tuple[list[Obligation], str | None, bool]: ...


class ReminderRepository(Protocol):
    async def create(self, occurrence: ReminderOccurrence) -> ReminderOccurrence: ...

    async def find_existing(
        self,
        obligation_id: str,
        recipient_user_id: str,
        reminder_type: str,
    ) -> ReminderOccurrence | None: ...

    async def list_for_obligation(self, obligation_id: str) -> list[ReminderOccurrence]: ...


class DeadlineRulePort(Protocol):
    """Reads lawyer-approved fixture rules only — no statutory text generation."""

    async def find_applicable_rules(
        self,
        *,
        trigger_type: TriggerType,
        trigger_date: datetime,
        context: dict[str, str],
    ) -> list[ApprovedDeadlineRule]: ...

    async def calculate(
        self,
        rule: ApprovedDeadlineRule,
        *,
        trigger_date: datetime,
        context: dict[str, str],
    ) -> DeadlineCalculation | None: ...

    async def reminder_schedule(self, policy_id: str) -> list[ReminderScheduleSpec]: ...


class EventPort(Protocol):
    async def append(self, event: OutboxEvent) -> None: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class NotificationIntentPort(Protocol):
    async def record_reminder_intent(self, intent: NotificationReminderIntent) -> None: ...
