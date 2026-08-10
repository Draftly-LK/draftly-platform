"""Notification module port definitions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

from src.modules.auth.ports import AuditPort
from src.modules.notification.domain.models import (
    DeliveryResult,
    NotificationChannel,
    NotificationDelivery,
    NotificationPreference,
    PaginatedDeliveries,
)


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class EmailPort(Protocol):
    async def send(
        self,
        *,
        recipient_address: str,
        template_key: str,
        template_version: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
    ) -> DeliveryResult: ...


class PreferenceRepository(Protocol):
    async def list_for_user(
        self, *, organisation_id: str, user_id: str
    ) -> list[NotificationPreference]: ...

    async def upsert(self, preference: NotificationPreference) -> NotificationPreference: ...

    async def get(
        self, *, organisation_id: str, user_id: str, channel: NotificationChannel
    ) -> NotificationPreference | None: ...


class DeliveryRepository(Protocol):
    async def get_by_id(
        self, *, organisation_id: str, delivery_id: str
    ) -> NotificationDelivery | None: ...

    async def get_idempotent(
        self,
        *,
        organisation_id: str,
        obligation_id: str,
        recipient_user_id: str,
        reminder_type: str,
        channel: NotificationChannel,
    ) -> NotificationDelivery | None: ...

    async def create(self, delivery: NotificationDelivery) -> NotificationDelivery: ...

    async def update(self, delivery: NotificationDelivery) -> NotificationDelivery: ...

    async def list_in_app_for_user(
        self,
        *,
        organisation_id: str,
        user_id: str,
        limit: int,
        cursor: str | None,
    ) -> PaginatedDeliveries: ...

    async def find_by_provider_message_id(
        self, *, provider_message_id: str
    ) -> NotificationDelivery | None: ...


class RecipientEmailResolver(Protocol):
    """Resolve the current verified email for a user at delivery time."""

    async def resolve_email(self, user_id: str) -> str | None: ...


__all__ = [
    "AuditPort",
    "ClockPort",
    "DeliveryRepository",
    "EmailPort",
    "PreferenceRepository",
    "RecipientEmailResolver",
]
