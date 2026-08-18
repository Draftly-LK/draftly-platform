"""Notification module port definitions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from src.modules.auth.ports import AuditPort
from src.modules.notification.domain.models import (
    DeliveryResult,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
    ProviderEvent,
    TemplateDeployment,
)
from src.platform.messaging.ports import OutboxPort


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
        subject: str,
        body: str,
        provider_template_id: str | None = None,
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
        subject_ref: str,
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


class ConsumedEventRepository(Protocol):
    """Inbox side of the outbox: one recorded consumption per event id."""

    async def already_consumed(self, *, event_id: str) -> bool: ...

    async def record(
        self,
        *,
        event_id: str,
        event_name: str,
        organisation_id: str,
        outcome: str,
        correlation_id: str,
    ) -> bool: ...


class ProviderEventRepository(Protocol):
    async def find(self, *, provider: str, provider_event_id: str) -> ProviderEvent | None: ...

    async def record(self, event: ProviderEvent) -> ProviderEvent: ...


class TemplateDeploymentRepository(Protocol):
    async def resolve(
        self, *, environment: str, template_key: str, locale: NotificationLocale
    ) -> TemplateDeployment | None: ...


class RecipientEmailResolver(Protocol):
    """Resolve the current verified email for a user at delivery time."""

    async def resolve_email(self, user_id: str) -> str | None: ...


class ComplianceRecipientPort(Protocol):
    """Restricted-compliance alerts go only to allowlisted recipients (§8.2)."""

    async def is_allowlisted(self, user_id: str) -> bool: ...


class WebhookVerifierPort(Protocol):
    """Verify a provider webhook signature and return the parsed payload."""

    def verify(self, *, headers: Mapping[str, str], raw_body: bytes) -> dict[str, Any]: ...


__all__ = [
    "AuditPort",
    "ClockPort",
    "ComplianceRecipientPort",
    "ConsumedEventRepository",
    "DeliveryRepository",
    "EmailPort",
    "OutboxPort",
    "PreferenceRepository",
    "ProviderEventRepository",
    "RecipientEmailResolver",
    "TemplateDeploymentRepository",
    "WebhookVerifierPort",
]
