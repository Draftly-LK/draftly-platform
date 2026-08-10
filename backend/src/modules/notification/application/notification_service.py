"""Notification application service — no FastAPI, SQLAlchemy, or provider SDK imports."""

from __future__ import annotations

import uuid

import structlog

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.notification.domain.errors import (
    InvalidPreferencePatchError,
    NotificationNotFoundError,
    WebhookVerificationError,
)
from src.modules.notification.domain.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
    preview_for_template,
)
from src.modules.notification.ports import (
    ClockPort,
    DeliveryRepository,
    EmailPort,
    PreferenceRepository,
    RecipientEmailResolver,
)
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

DEFAULT_CHANNELS = (NotificationChannel.EMAIL, NotificationChannel.IN_APP)
DEFAULT_TIMEZONE = "Asia/Colombo"
TEMPLATE_VERSION = "1.0.0-synthetic"


def solo_organisation_id(user_id: str) -> str:
    """Single-user Gmail model: the actor is the organisation boundary."""

    return user_id


class NotificationService:
    def __init__(
        self,
        *,
        preferences: PreferenceRepository,
        deliveries: DeliveryRepository,
        email_port: EmailPort,
        audit_port: AuditPort,
        clock: ClockPort,
        recipient_resolver: RecipientEmailResolver,
    ) -> None:
        self._preferences = preferences
        self._deliveries = deliveries
        self._email = email_port
        self._audit = audit_port
        self._clock = clock
        self._recipient_resolver = recipient_resolver

    async def get_preferences(self, ctx: RequestContext) -> list[NotificationPreference]:
        org_id = solo_organisation_id(ctx.actor_id)
        stored = await self._preferences.list_for_user(organisation_id=org_id, user_id=ctx.actor_id)
        by_channel = {p.channel: p for p in stored}
        result: list[NotificationPreference] = []
        for channel in DEFAULT_CHANNELS:
            if channel in by_channel:
                result.append(by_channel[channel])
            else:
                result.append(self._default_preference(org_id, ctx.actor_id, channel))
        return result

    async def patch_preferences(
        self,
        ctx: RequestContext,
        *,
        channel: NotificationChannel,
        enabled: bool | None = None,
        locale: NotificationLocale | None = None,
        timezone: str | None = None,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
        clear_quiet_hours: bool = False,
    ) -> NotificationPreference:
        org_id = solo_organisation_id(ctx.actor_id)
        existing = await self._preferences.get(
            organisation_id=org_id, user_id=ctx.actor_id, channel=channel
        )
        base = existing or self._default_preference(org_id, ctx.actor_id, channel)

        if timezone is not None and not timezone.strip():
            raise InvalidPreferencePatchError("timezone cannot be empty.")

        updated = NotificationPreference(
            id=base.id if existing else f"np_{uuid.uuid4().hex}",
            organisation_id=org_id,
            user_id=ctx.actor_id,
            channel=channel,
            enabled=enabled if enabled is not None else base.enabled,
            locale=locale if locale is not None else base.locale,
            timezone=timezone if timezone is not None else base.timezone,
            quiet_hours_start=None
            if clear_quiet_hours
            else (quiet_hours_start if quiet_hours_start is not None else base.quiet_hours_start),
            quiet_hours_end=None
            if clear_quiet_hours
            else (quiet_hours_end if quiet_hours_end is not None else base.quiet_hours_end),
            version=base.version + 1 if existing else 1,
        )
        saved = await self._preferences.upsert(updated)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="notification.preference-changed",
                target_type="notification_preference",
                target_id=saved.id,
                after_ref=f"{saved.channel.value}:{saved.enabled}:{saved.locale.value}",
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    async def list_notifications(
        self,
        ctx: RequestContext,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedDeliveries:
        if limit < 1 or limit > 100:
            raise InvalidPreferencePatchError("limit must be between 1 and 100.")
        org_id = solo_organisation_id(ctx.actor_id)
        return await self._deliveries.list_in_app_for_user(
            organisation_id=org_id,
            user_id=ctx.actor_id,
            limit=limit,
            cursor=cursor,
        )

    async def create_delivery_idempotent(
        self,
        *,
        organisation_id: str,
        source_event_id: str,
        obligation_id: str,
        matter_id: str | None,
        recipient_user_id: str,
        channel: NotificationChannel,
        reminder_type: str,
        obligation_class: str,
        urgency: str,
        confidentiality_level: str,
        template_key: str,
        delivery_policy_key: str,
        locale: NotificationLocale,
        correlation_id: str = "",
    ) -> NotificationDelivery:
        """Worker/event path — idempotent per obligation, recipient, reminder, channel."""
        existing = await self._deliveries.get_idempotent(
            organisation_id=organisation_id,
            obligation_id=obligation_id,
            recipient_user_id=recipient_user_id,
            reminder_type=reminder_type,
            channel=channel,
        )
        if existing:
            return existing

        preference = await self._preferences.get(
            organisation_id=organisation_id,
            user_id=recipient_user_id,
            channel=channel,
        )
        enabled = preference.enabled if preference else True
        title, body = preview_for_template(template_key)
        now = self._clock.now()
        status = DeliveryStatus.QUEUED if enabled else DeliveryStatus.SUPPRESSED
        delivery = NotificationDelivery(
            id=f"nd_{uuid.uuid4().hex}",
            organisation_id=organisation_id,
            source_event_id=source_event_id,
            obligation_id=obligation_id,
            matter_id=matter_id,
            recipient_user_id=recipient_user_id,
            channel=channel,
            reminder_type=reminder_type,
            obligation_class=obligation_class,
            urgency=urgency,
            confidentiality_level=confidentiality_level,
            template_key=template_key,
            delivery_policy_key=delivery_policy_key,
            locale=locale,
            status=status,
            attempt_count=0,
            created_at=now,
            preview_title=title,
            preview_body=body,
        )
        saved = await self._deliveries.create(delivery)
        if status == DeliveryStatus.SUPPRESSED:
            await self._audit.record(
                AuditEventInput(
                    user_id=recipient_user_id,
                    action="notification.suppressed",
                    target_type="notification_delivery",
                    target_id=saved.id,
                    correlation_id=correlation_id,
                )
            )
        return saved

    async def deliver(self, *, delivery_id: str, organisation_id: str) -> None:
        """Idempotent delivery job — failures never propagate to obligation state."""
        delivery = await self._deliveries.get_by_id(
            organisation_id=organisation_id, delivery_id=delivery_id
        )
        if delivery is None:
            log.warning("notification.deliver.missing", delivery_id=delivery_id)
            return

        if delivery.status in (
            DeliveryStatus.DELIVERED,
            DeliveryStatus.SUPPRESSED,
            DeliveryStatus.FAILED,
        ):
            return

        if delivery.channel == NotificationChannel.IN_APP:
            await self._mark_delivered(delivery)
            return

        preference = await self._preferences.get(
            organisation_id=organisation_id,
            user_id=delivery.recipient_user_id,
            channel=NotificationChannel.EMAIL,
        )
        if preference is not None and not preference.enabled:
            delivery.status = DeliveryStatus.SUPPRESSED
            await self._deliveries.update(delivery)
            await self._audit.record(
                AuditEventInput(
                    user_id=delivery.recipient_user_id,
                    action="notification.suppressed",
                    target_type="notification_delivery",
                    target_id=delivery.id,
                )
            )
            return

        delivery.status = DeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        delivery.attempted_at = self._clock.now()
        await self._deliveries.update(delivery)

        address = await self._recipient_resolver.resolve_email(delivery.recipient_user_id)
        if not address:
            await self._mark_failed(delivery, failure_code="recipient_address_missing")
            return

        variables = {
            "templateKey": delivery.template_key,
            "reminderType": delivery.reminder_type,
            "dueAt": "synthetic",
            "matterReference": delivery.matter_id or "",
            "actionUrl": "https://draftly.local/synthetic",
        }
        try:
            result = await self._email.send(
                recipient_address=address,
                template_key=delivery.template_key,
                template_version=TEMPLATE_VERSION,
                locale=delivery.locale.value,
                variables=variables,
                idempotency_key=delivery.id,
            )
        except Exception as exc:
            log.warning(
                "notification.deliver.failed",
                delivery_id=delivery.id,
                error=type(exc).__name__,
            )
            await self._mark_failed(delivery, failure_code=type(exc).__name__)
            return

        delivery.provider_message_id = result.provider_message_id
        await self._mark_delivered(delivery)

    async def handle_provider_webhook(
        self,
        *,
        payload: dict[str, object],
        signature: str | None,
    ) -> None:
        """Stub Resend webhook handler — verifies signature when configured."""
        from src.platform.config import get_settings

        settings = get_settings()
        if settings.resend_webhook_secret:
            if not signature or signature != settings.resend_webhook_secret:
                raise WebhookVerificationError()
        provider_id = payload.get("data")
        if isinstance(provider_id, dict):
            email_id = provider_id.get("email_id")
            if isinstance(email_id, str):
                delivery = await self._deliveries.find_by_provider_message_id(
                    provider_message_id=email_id
                )
                if delivery and delivery.status == DeliveryStatus.DELIVERED:
                    log.debug(
                        "notification.webhook.ack",
                        delivery_id=delivery.id,
                        event_type=payload.get("type"),
                    )
        log.debug("notification.webhook.stub", event_type=payload.get("type"))

    async def get_notification_for_actor(
        self, ctx: RequestContext, notification_id: str
    ) -> NotificationDelivery:
        org_id = solo_organisation_id(ctx.actor_id)
        row = await self._deliveries.get_by_id(organisation_id=org_id, delivery_id=notification_id)
        if row is None or row.recipient_user_id != ctx.actor_id:
            raise NotificationNotFoundError()
        if row.channel != NotificationChannel.IN_APP:
            raise NotificationNotFoundError()
        return row

    def _default_preference(
        self, organisation_id: str, user_id: str, channel: NotificationChannel
    ) -> NotificationPreference:
        return NotificationPreference(
            id=f"np_default_{channel.value}",
            organisation_id=organisation_id,
            user_id=user_id,
            channel=channel,
            enabled=True,
            locale=NotificationLocale.EN,
            timezone=DEFAULT_TIMEZONE,
        )

    async def _mark_delivered(self, delivery: NotificationDelivery) -> None:
        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = self._clock.now()
        await self._deliveries.update(delivery)
        await self._audit.record(
            AuditEventInput(
                user_id=delivery.recipient_user_id,
                action="notification.delivered",
                target_type="notification_delivery",
                target_id=delivery.id,
            )
        )

    async def _mark_failed(self, delivery: NotificationDelivery, *, failure_code: str) -> None:
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_code = failure_code
        await self._deliveries.update(delivery)
        await self._audit.record(
            AuditEventInput(
                user_id=delivery.recipient_user_id,
                action="notification.failed",
                target_type="notification_delivery",
                target_id=delivery.id,
                after_ref=failure_code,
            )
        )
