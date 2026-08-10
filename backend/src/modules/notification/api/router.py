"""Notification API router — user preferences and in-app notification list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_notification_service_instance, get_request_context
from src.modules.notification.api.schemas import (
    NotificationListRead,
    NotificationPreferenceListRead,
    NotificationPreferencePatch,
    NotificationPreferenceRead,
    delivery_to_read,
    preference_to_read,
)
from src.modules.notification.domain.errors import InvalidPreferencePatchError
from src.modules.notification.domain.models import NotificationChannel, NotificationLocale
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["notifications"])


@router.get("/notification-preferences", response_model=NotificationPreferenceListRead)
async def get_notification_preferences(
    ctx: RequestContext = Depends(get_request_context),
) -> NotificationPreferenceListRead:
    service = get_notification_service_instance()
    prefs = await service.get_preferences(ctx)
    return NotificationPreferenceListRead(
        items=[preference_to_read(p) for p in prefs],
    )


@router.patch("/notification-preferences", response_model=NotificationPreferenceRead)
async def patch_notification_preferences(
    body: NotificationPreferencePatch,
    ctx: RequestContext = Depends(get_request_context),
) -> NotificationPreferenceRead:
    try:
        channel = NotificationChannel(body.channel)
    except ValueError:
        raise DomainRuleError(f"Invalid channel '{body.channel}'.")
    locale: NotificationLocale | None = None
    if body.locale is not None:
        try:
            locale = NotificationLocale(body.locale)
        except ValueError:
            raise InvalidPreferencePatchError(f"Invalid locale '{body.locale}'.")

    service = get_notification_service_instance()
    saved = await service.patch_preferences(
        ctx,
        channel=channel,
        enabled=body.enabled,
        locale=locale,
        timezone=body.timezone,
        quiet_hours_start=body.quiet_hours_start,
        quiet_hours_end=body.quiet_hours_end,
        clear_quiet_hours=body.clear_quiet_hours,
    )
    return preference_to_read(saved)


@router.get("/notifications", response_model=NotificationListRead)
async def list_notifications(
    ctx: RequestContext = Depends(get_request_context),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> NotificationListRead:
    service = get_notification_service_instance()
    page = await service.list_notifications(ctx, limit=limit, cursor=cursor)
    return NotificationListRead(
        items=[delivery_to_read(d) for d in page.items],
        next_cursor=page.next_cursor,
    )
