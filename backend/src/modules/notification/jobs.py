"""Notification worker entry points (jobs-and-workers.md §3)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.notification.domain.policies import EVENT_TEMPLATE_ROUTES
from src.modules.notification.infrastructure.service_factory import build_notification_service

NOTIFICATION_CONSUMED_EVENTS = frozenset(EVENT_TEMPLATE_ROUTES)


async def consume_registered_event(session: AsyncSession, payload: dict[str, Any]) -> str:
    """Idempotent consumer for every event in services.yaml `consumes`."""
    service = build_notification_service(session)
    result = await service.handle_event(payload)
    return result.outcome.value


async def run_delivery_job(session: AsyncSession, payload: dict[str, Any]) -> str:
    """Execute one `notification.deliver` job."""
    delivery_id = str(payload["deliveryId"])
    organisation_id = str(payload["organisationId"])
    service = build_notification_service(session)
    outcome = await service.deliver(delivery_id=delivery_id, organisation_id=organisation_id)
    return outcome.value


__all__ = ["NOTIFICATION_CONSUMED_EVENTS", "consume_registered_event", "run_delivery_job"]
