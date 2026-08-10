"""Notification API router — preferences, in-app list, and provider webhooks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_notification_service_instance, get_request_context
from src.modules.notification.api.schemas import (
    NotificationListRead,
    NotificationPreferenceListRead,
    NotificationPreferencePatch,
    NotificationPreferenceRead,
    NotificationRead,
    delivery_to_read,
    page_to_read,
    preference_to_read,
)
from src.modules.notification.application.notification_service import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from src.modules.notification.domain.errors import InvalidPreferencePatchError
from src.modules.notification.domain.models import NotificationChannel, NotificationLocale
from src.platform.db.session import get_db
from src.platform.errors import DomainRuleError, PreconditionFailedError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["notifications"])


@router.get("/notification-preferences", response_model=NotificationPreferenceListRead)
async def get_notification_preferences(
    ctx: RequestContext = Depends(get_request_context),
) -> NotificationPreferenceListRead:
    service = get_notification_service_instance()
    prefs = await service.get_preferences(ctx)
    return NotificationPreferenceListRead(items=[preference_to_read(p) for p in prefs])


@router.patch("/notification-preferences", response_model=NotificationPreferenceRead)
async def patch_notification_preferences(
    body: NotificationPreferencePatch,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db),
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
    # The preference row, its audit event, and its outbox event commit together.
    await session.commit()
    return preference_to_read(saved)


@router.get("/notifications", response_model=NotificationListRead)
async def list_notifications(
    ctx: RequestContext = Depends(get_request_context),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None),
) -> NotificationListRead:
    service = get_notification_service_instance()
    page = await service.list_notifications(ctx, limit=limit, cursor=cursor)
    return page_to_read(page)


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> NotificationRead:
    """Mark the caller's own notification read. Idempotent, so If-Match is optional."""
    expected_version: int | None = None
    if if_match is not None:
        try:
            expected_version = int(if_match.strip().strip('"'))
        except ValueError:
            raise PreconditionFailedError()

    service = get_notification_service_instance()
    saved = await service.mark_notification_read(
        ctx, notification_id, expected_version=expected_version
    )
    await session.commit()
    response.headers["ETag"] = f'"{saved.version}"'
    return delivery_to_read(saved)


@router.post("/notifications/provider-webhooks/resend", include_in_schema=False)
async def resend_delivery_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Signed Resend delivery webhook.

    Unauthenticated by design: trust comes from the signature, not a session.
    An unsigned, tampered, or replayed request is rejected before any write, and
    a verified event moves delivery state only — never obligation state.
    """
    from src.modules.notification.infrastructure.service_factory import build_notification_service

    raw_body = await request.body()
    service = build_notification_service(session)
    outcome = await service.handle_provider_webhook(
        headers=dict(request.headers), raw_body=raw_body
    )
    await session.commit()
    return {"status": outcome}
