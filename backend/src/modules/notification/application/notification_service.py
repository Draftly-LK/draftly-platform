"""Notification application service — no FastAPI, SQLAlchemy, or provider SDK imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any

import structlog

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.notification.domain.errors import (
    DeliveryFailure,
    InvalidPreferencePatchError,
    NotificationNotFoundError,
    PermanentDeliveryFailure,
    RetryableDeliveryFailure,
)
from src.modules.notification.domain.events import (
    NotificationTrigger,
    SuppressedByPolicyError,
    UnroutableEventError,
    trigger_from_envelope,
)
from src.modules.notification.domain.models import (
    PROVIDER_EVENT_STATES,
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
    ProviderDeliveryState,
    ProviderEvent,
)
from src.modules.notification.domain.policies import (
    DELIVERY_CHANNELS,
    FailureClass,
    classify_failure,
)
from src.modules.notification.domain.templates import (
    TemplateApprovalState,
    TemplateVariableError,
    get_template,
    render,
)
from src.modules.notification.ports import (
    ClockPort,
    ComplianceRecipientPort,
    ConsumedEventRepository,
    DeliveryRepository,
    EmailPort,
    PreferenceRepository,
    ProviderEventRepository,
    RecipientEmailResolver,
    TemplateDeploymentRepository,
    WebhookVerifierPort,
)
from src.platform.errors import DomainRuleError, PreconditionFailedError
from src.platform.messaging.envelope import (
    EventEnvelope,
    InvalidEnvelopeError,
    parse_envelope,
)
from src.platform.messaging.outbox import backoff_seconds
from src.platform.messaging.ports import OutboxPort
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

DEFAULT_TIMEZONE = "Asia/Colombo"
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100
MAX_DELIVERY_ATTEMPTS = 8
DELIVER_JOB_TYPE = "notification.deliver"
# Action links are short-lived and authenticated; no private data in the URL.
ACTION_URL = "https://app.draftly.lk/inbox"


def solo_organisation_id(user_id: str) -> str:
    """Single-user Gmail model: the actor is the organisation boundary."""

    return user_id


class ConsumeOutcome(str, Enum):
    """What the worker should do with the consumed message."""

    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    SUPPRESSED = "suppressed"
    DEAD_LETTER = "dead-letter"


class DeliveryOutcome(str, Enum):
    DELIVERED = "delivered"
    SUPPRESSED = "suppressed"
    RETRY = "retry"
    PERMANENT_FAILURE = "permanent-failure"
    DEAD_LETTER = "dead-letter"
    UNKNOWN_DELIVERY = "unknown-delivery"


@dataclass(frozen=True)
class ConsumeResult:
    outcome: ConsumeOutcome
    delivery_ids: tuple[str, ...] = ()
    reason: str | None = None


class NotificationService:
    def __init__(
        self,
        *,
        preferences: PreferenceRepository,
        deliveries: DeliveryRepository,
        consumed_events: ConsumedEventRepository,
        provider_events: ProviderEventRepository,
        template_deployments: TemplateDeploymentRepository,
        email_port: EmailPort,
        audit_port: AuditPort,
        outbox: OutboxPort,
        clock: ClockPort,
        recipient_resolver: RecipientEmailResolver,
        compliance_recipients: ComplianceRecipientPort,
        webhook_verifier: WebhookVerifierPort | None = None,
        environment: str = "local",
        require_published_template: bool = False,
        max_attempts: int = MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        self._preferences = preferences
        self._deliveries = deliveries
        self._consumed = consumed_events
        self._provider_events = provider_events
        self._deployments = template_deployments
        self._email = email_port
        self._audit = audit_port
        self._outbox = outbox
        self._clock = clock
        self._recipient_resolver = recipient_resolver
        self._compliance = compliance_recipients
        self._webhook_verifier = webhook_verifier
        self._environment = environment
        self._require_published_template = require_published_template
        self._max_attempts = max_attempts

    # ── User-facing reads and preference mutation ───────────────────────────

    async def get_preferences(self, ctx: RequestContext) -> list[NotificationPreference]:
        org_id = solo_organisation_id(ctx.actor_id)
        stored = await self._preferences.list_for_user(organisation_id=org_id, user_id=ctx.actor_id)
        by_channel = {p.channel: p for p in stored}
        return [
            by_channel.get(channel) or self._default_preference(org_id, ctx.actor_id, channel)
            for channel in DELIVERY_CHANNELS
        ]

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
        await self._publish(
            event_name="notification.preference-changed",
            organisation_id=org_id,
            correlation_id=ctx.correlation_id,
            actor_id=ctx.actor_id,
            idempotency_key=f"notification.preference-changed:{saved.id}:v{saved.version}",
            data={
                "userId": saved.user_id,
                "channel": saved.channel.value,
                "enabled": saved.enabled,
            },
        )
        return saved

    async def list_notifications(
        self,
        ctx: RequestContext,
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        cursor: str | None = None,
    ) -> PaginatedDeliveries:
        if limit < 1 or limit > MAX_PAGE_LIMIT:
            raise InvalidPreferencePatchError(
                f"limit must be between 1 and {MAX_PAGE_LIMIT}.",
            )
        org_id = solo_organisation_id(ctx.actor_id)
        return await self._deliveries.list_in_app_for_user(
            organisation_id=org_id,
            user_id=ctx.actor_id,
            limit=limit,
            cursor=cursor,
        )

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

    async def mark_notification_read(
        self, ctx: RequestContext, notification_id: str, *, expected_version: int | None = None
    ) -> NotificationDelivery:
        """Mark the actor's own in-app notification read. Idempotent."""
        row = await self.get_notification_for_actor(ctx, notification_id)
        if expected_version is not None and expected_version != row.version:
            raise PreconditionFailedError()
        if row.read_at is not None:
            return row

        row.read_at = self._clock.now()
        row.version += 1
        saved = await self._deliveries.update(row)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="notification.read",
                target_type="notification_delivery",
                target_id=saved.id,
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    # ── Idempotent event consumption ────────────────────────────────────────

    async def handle_event(self, payload: dict[str, Any]) -> ConsumeResult:
        """Consume one registered event exactly once (events.md §3, §7.5).

        Every write here — deliveries, delivery jobs, and the consumed-event row —
        happens in the caller's transaction, so a redelivery after a crash either
        finds the recorded consumption or replays into an empty state.
        """
        try:
            envelope = parse_envelope(payload)
        except InvalidEnvelopeError as exc:
            log.error("notification.consume.invalid_envelope", reason=str(exc))
            return ConsumeResult(outcome=ConsumeOutcome.DEAD_LETTER, reason="invalid_envelope")

        if await self._consumed.already_consumed(event_id=envelope.event_id):
            log.info(
                "notification.consume.duplicate",
                event_id=envelope.event_id,
                event_name=envelope.event_name,
            )
            return ConsumeResult(outcome=ConsumeOutcome.DUPLICATE)

        try:
            trigger = trigger_from_envelope(envelope)
        except UnroutableEventError:
            log.error(
                "notification.consume.unroutable",
                event_name=envelope.event_name,
                event_id=envelope.event_id,
            )
            await self._record_consumption(envelope, outcome="unroutable")
            return ConsumeResult(outcome=ConsumeOutcome.DEAD_LETTER, reason="unroutable_event")
        except SuppressedByPolicyError as exc:
            await self._record_consumption(envelope, outcome="policy-suppressed")
            return ConsumeResult(outcome=ConsumeOutcome.SUPPRESSED, reason=str(exc))

        if trigger.restricted and not await self._compliance.is_allowlisted(
            trigger.recipient_user_id
        ):
            # Ordinary matter access is never sufficient for a restricted alert.
            log.warning(
                "notification.consume.restricted_recipient_denied",
                event_id=envelope.event_id,
                event_name=envelope.event_name,
            )
            await self._record_consumption(envelope, outcome="restricted-recipient-denied")
            return ConsumeResult(
                outcome=ConsumeOutcome.SUPPRESSED, reason="recipient_not_permitted"
            )

        delivery_ids: list[str] = []
        for channel in DELIVERY_CHANNELS:
            delivery = await self._create_delivery_idempotent(trigger, channel)
            delivery_ids.append(delivery.id)
            if delivery.status == DeliveryStatus.QUEUED:
                await self._outbox.enqueue_job(
                    job_type=DELIVER_JOB_TYPE,
                    organisation_id=delivery.organisation_id,
                    idempotency_key=f"{DELIVER_JOB_TYPE}:{delivery.id}",
                    message={
                        "deliveryId": delivery.id,
                        "organisationId": delivery.organisation_id,
                        "correlationId": trigger.correlation_id,
                    },
                )

        await self._record_consumption(envelope, outcome="processed")
        return ConsumeResult(outcome=ConsumeOutcome.PROCESSED, delivery_ids=tuple(delivery_ids))

    async def _record_consumption(self, envelope: EventEnvelope, *, outcome: str) -> None:
        await self._consumed.record(
            event_id=envelope.event_id,
            event_name=envelope.event_name,
            organisation_id=envelope.organisation_id,
            outcome=outcome,
            correlation_id=envelope.correlation_id,
        )

    async def _create_delivery_idempotent(
        self, trigger: NotificationTrigger, channel: NotificationChannel
    ) -> NotificationDelivery:
        existing = await self._deliveries.get_idempotent(
            organisation_id=trigger.organisation_id,
            subject_ref=trigger.subject_ref,
            recipient_user_id=trigger.recipient_user_id,
            reminder_type=trigger.reminder_type,
            channel=channel,
        )
        if existing:
            return existing

        preference = await self._preferences.get(
            organisation_id=trigger.organisation_id,
            user_id=trigger.recipient_user_id,
            channel=channel,
        )
        enabled = preference.enabled if preference else True
        locale = preference.locale if preference else NotificationLocale.EN
        status = DeliveryStatus.QUEUED if enabled else DeliveryStatus.SUPPRESSED

        preview_title, preview_body = self._preview_for(trigger, locale=locale)
        delivery = NotificationDelivery(
            id=f"nd_{uuid.uuid4().hex}",
            organisation_id=trigger.organisation_id,
            source_event_id=trigger.event_id,
            subject_ref=trigger.subject_ref,
            obligation_id=trigger.obligation_id,
            # A restricted alert stores no matter context at all (§8.2).
            matter_id=None if trigger.restricted else trigger.matter_id,
            recipient_user_id=trigger.recipient_user_id,
            channel=channel,
            reminder_type=trigger.reminder_type,
            obligation_class=trigger.obligation_class,
            urgency=trigger.urgency,
            confidentiality_level=trigger.confidentiality_level,
            template_key=trigger.template_key,
            delivery_policy_key=trigger.delivery_policy_key,
            locale=locale,
            status=status,
            attempt_count=0,
            created_at=self._clock.now(),
            correlation_id=trigger.correlation_id,
            preview_title=preview_title,
            preview_body=preview_body,
        )
        saved = await self._deliveries.create(delivery)
        if status == DeliveryStatus.SUPPRESSED:
            await self._record_outcome(
                saved,
                action="notification.suppressed",
                data={
                    "deliveryId": saved.id,
                    "channel": saved.channel.value,
                    "reason": "preference_disabled",
                },
            )
        return saved

    def _preview_for(
        self, trigger: NotificationTrigger, *, locale: NotificationLocale
    ) -> tuple[str, str]:
        template = get_template(trigger.template_key)
        if template is None:
            return ("Draftly notification", "You have a notification in Draftly.")
        try:
            copy = render(
                template,
                locale=locale,
                variables=self._variables_for(trigger, template.required_variables),
            )
        except TemplateVariableError:
            entry = template.copy_for(locale)
            return (entry.subject, "You have a notification in Draftly.")
        return (copy.subject, copy.body)

    def _variables_for(
        self, trigger: NotificationTrigger, required: tuple[str, ...]
    ) -> dict[str, str]:
        """Supply only validated, privacy-classified variables (§8)."""
        available = {
            "actionUrl": ACTION_URL,
            "dueAt": trigger.due_at or "",
        }
        return {name: available.get(name, "") for name in required}

    # ── Delivery job ────────────────────────────────────────────────────────

    async def deliver(self, *, delivery_id: str, organisation_id: str) -> DeliveryOutcome:
        """Send one queued delivery. A failure here never touches the obligation."""
        delivery = await self._deliveries.get_by_id(
            organisation_id=organisation_id, delivery_id=delivery_id
        )
        if delivery is None:
            log.warning("notification.deliver.missing", delivery_id=delivery_id)
            return DeliveryOutcome.UNKNOWN_DELIVERY

        if delivery.status == DeliveryStatus.DELIVERED:
            return DeliveryOutcome.DELIVERED
        if delivery.status == DeliveryStatus.SUPPRESSED:
            return DeliveryOutcome.SUPPRESSED
        if delivery.status == DeliveryStatus.FAILED:
            if delivery.failure_class == FailureClass.DEAD_LETTER.value:
                return DeliveryOutcome.DEAD_LETTER
            return DeliveryOutcome.PERMANENT_FAILURE

        if delivery.channel == NotificationChannel.IN_APP:
            await self._mark_delivered(delivery)
            return DeliveryOutcome.DELIVERED

        preference = await self._preferences.get(
            organisation_id=organisation_id,
            user_id=delivery.recipient_user_id,
            channel=NotificationChannel.EMAIL,
        )
        if preference is not None and not preference.enabled:
            delivery.status = DeliveryStatus.SUPPRESSED
            await self._deliveries.update(delivery)
            await self._record_outcome(
                delivery,
                action="notification.suppressed",
                data={
                    "deliveryId": delivery.id,
                    "channel": delivery.channel.value,
                    "reason": "preference_disabled",
                },
            )
            return DeliveryOutcome.SUPPRESSED

        template = get_template(delivery.template_key)
        if template is None:
            return await self._dead_letter(delivery, failure_code="template_missing")
        if template.approval_state is not TemplateApprovalState.APPROVED:
            return await self._dead_letter(delivery, failure_code="template_not_approved")

        provider_template_id: str | None = None
        deployment = await self._deployments.resolve(
            environment=self._environment,
            template_key=template.key,
            locale=delivery.locale,
        )
        if deployment is not None:
            provider_template_id = deployment.provider_template_id
        elif self._require_published_template:
            return await self._dead_letter(delivery, failure_code="template_not_published")

        try:
            rendered = render(
                template,
                locale=delivery.locale,
                variables=self._delivery_variables(delivery, template.required_variables),
            )
        except TemplateVariableError:
            return await self._dead_letter(delivery, failure_code="template_variables_invalid")

        delivery.status = DeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        delivery.attempted_at = self._clock.now()
        await self._deliveries.update(delivery)

        address = await self._recipient_resolver.resolve_email(delivery.recipient_user_id)
        if not address:
            return await self._fail(delivery, failure_code="recipient_address_missing")

        try:
            result = await self._email.send(
                recipient_address=address,
                template_key=template.key,
                template_version=template.version,
                locale=delivery.locale.value,
                variables=self._delivery_variables(delivery, template.required_variables),
                idempotency_key=delivery.id,
                subject=rendered.subject,
                body=rendered.body,
                provider_template_id=provider_template_id,
            )
        except RetryableDeliveryFailure as exc:
            return await self._retry(delivery, failure_code=exc.failure_code)
        except (PermanentDeliveryFailure, DeliveryFailure) as exc:
            return await self._fail(delivery, failure_code=exc.failure_code)
        except Exception as exc:  # noqa: BLE001 - provider adapters must not leak detail
            log.warning(
                "notification.deliver.unexpected_error",
                delivery_id=delivery.id,
                error=type(exc).__name__,
            )
            return await self._retry(delivery, failure_code="transient_error")

        delivery.provider_message_id = result.provider_message_id
        await self._mark_delivered(delivery)
        return DeliveryOutcome.DELIVERED

    def _delivery_variables(
        self, delivery: NotificationDelivery, required: tuple[str, ...]
    ) -> dict[str, str]:
        available = {"actionUrl": ACTION_URL, "dueAt": "scheduled"}
        return {name: available.get(name, "") for name in required}

    # ── Provider webhooks ───────────────────────────────────────────────────

    async def handle_provider_webhook(self, *, headers: dict[str, str], raw_body: bytes) -> str:
        """Verify, store, and apply one Resend delivery event (§9.1).

        Delivery state moves only; no obligation, matter, or draft is touched.
        """
        if self._webhook_verifier is None:
            raise DomainRuleError("Provider webhooks are not configured.")

        payload = self._webhook_verifier.verify(headers=headers, raw_body=raw_body)
        event_type = str(payload.get("type", ""))
        data = payload.get("data")
        data_map: dict[str, Any] = data if isinstance(data, dict) else {}
        provider_event_id = str(
            payload.get("id") or headers.get("svix-id") or headers.get("webhook-id") or ""
        )
        if not provider_event_id:
            raise DomainRuleError("Provider webhook is missing an event id.")

        existing = await self._provider_events.find(
            provider="resend", provider_event_id=provider_event_id
        )
        if existing is not None:
            log.info("notification.webhook.duplicate", event_type=event_type)
            return "duplicate"

        raw_message_id = data_map.get("email_id") or data_map.get("id")
        provider_message_id = raw_message_id if isinstance(raw_message_id, str) else None
        delivery: NotificationDelivery | None = None
        if provider_message_id:
            delivery = await self._deliveries.find_by_provider_message_id(
                provider_message_id=provider_message_id
            )

        await self._provider_events.record(
            ProviderEvent(
                id=f"pe_{uuid.uuid4().hex}",
                provider="resend",
                provider_event_id=provider_event_id,
                event_type=event_type,
                provider_message_id=provider_message_id,
                delivery_id=delivery.id if delivery else None,
                received_at=self._clock.now(),
            )
        )

        state = PROVIDER_EVENT_STATES.get(event_type)
        if delivery is None or state is None:
            log.info("notification.webhook.recorded", event_type=event_type, matched=False)
            return "recorded"

        delivery.provider_state = state.value
        if state is ProviderDeliveryState.DELIVERED and delivery.delivered_at is None:
            delivery.delivered_at = self._clock.now()
        if state in (
            ProviderDeliveryState.BOUNCED,
            ProviderDeliveryState.FAILED,
            ProviderDeliveryState.SUPPRESSED,
        ):
            # Provider-side rejection is permanent; the obligation is untouched.
            delivery.status = DeliveryStatus.FAILED
            delivery.failure_code = "recipient_address_suppressed"
            delivery.failure_class = FailureClass.PERMANENT.value
        await self._deliveries.update(delivery)
        log.info("notification.webhook.applied", event_type=event_type, delivery_id=delivery.id)
        return "applied"

    # ── State transitions ───────────────────────────────────────────────────

    async def _mark_delivered(self, delivery: NotificationDelivery) -> None:
        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = self._clock.now()
        await self._deliveries.update(delivery)
        await self._record_outcome(
            delivery,
            action="notification.delivered",
            data={
                "deliveryId": delivery.id,
                "channel": delivery.channel.value,
                "providerMessageId": delivery.provider_message_id,
            },
        )

    async def _retry(self, delivery: NotificationDelivery, *, failure_code: str) -> DeliveryOutcome:
        if classify_failure(failure_code) is not FailureClass.RETRYABLE:
            return await self._fail(delivery, failure_code=failure_code)
        if delivery.attempt_count >= self._max_attempts:
            return await self._dead_letter(delivery, failure_code=failure_code)

        delivery.status = DeliveryStatus.QUEUED
        delivery.failure_code = failure_code
        delivery.failure_class = FailureClass.RETRYABLE.value
        delivery.next_attempt_at = self._clock.now() + timedelta(
            seconds=backoff_seconds(delivery.attempt_count)
        )
        await self._deliveries.update(delivery)
        await self._outbox.enqueue_job(
            job_type=DELIVER_JOB_TYPE,
            organisation_id=delivery.organisation_id,
            idempotency_key=f"{DELIVER_JOB_TYPE}:{delivery.id}:retry:{delivery.attempt_count}",
            message={
                "deliveryId": delivery.id,
                "organisationId": delivery.organisation_id,
                "correlationId": delivery.correlation_id,
            },
            available_at=delivery.next_attempt_at,
        )
        log.info(
            "notification.deliver.retry_scheduled",
            delivery_id=delivery.id,
            attempt=delivery.attempt_count,
            failure_code=failure_code,
        )
        return DeliveryOutcome.RETRY

    async def _fail(self, delivery: NotificationDelivery, *, failure_code: str) -> DeliveryOutcome:
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_code = failure_code
        delivery.failure_class = FailureClass.PERMANENT.value
        await self._deliveries.update(delivery)
        await self._record_outcome(
            delivery,
            action="notification.failed",
            data={
                "deliveryId": delivery.id,
                "channel": delivery.channel.value,
                "failureCode": failure_code,
                "terminal": True,
            },
        )
        return DeliveryOutcome.PERMANENT_FAILURE

    async def _dead_letter(
        self, delivery: NotificationDelivery, *, failure_code: str
    ) -> DeliveryOutcome:
        delivery.status = DeliveryStatus.FAILED
        delivery.failure_code = failure_code
        delivery.failure_class = FailureClass.DEAD_LETTER.value
        await self._deliveries.update(delivery)
        await self._record_outcome(
            delivery,
            action="notification.failed",
            data={
                "deliveryId": delivery.id,
                "channel": delivery.channel.value,
                "failureCode": failure_code,
                "terminal": True,
            },
        )
        log.error(
            "notification.deliver.dead_letter",
            delivery_id=delivery.id,
            failure_code=failure_code,
            attempts=delivery.attempt_count,
        )
        return DeliveryOutcome.DEAD_LETTER

    async def _record_outcome(
        self,
        delivery: NotificationDelivery,
        *,
        action: str,
        data: dict[str, Any],
    ) -> None:
        """One audit row plus one registered event per material outcome (§10)."""
        await self._audit.record(
            AuditEventInput(
                user_id=delivery.recipient_user_id,
                action=action,
                target_type="notification_delivery",
                target_id=delivery.id,
                after_ref=delivery.status.value,
                correlation_id=delivery.correlation_id,
            )
        )
        await self._publish(
            event_name=action,
            organisation_id=delivery.organisation_id,
            correlation_id=delivery.correlation_id,
            actor_id=None,
            idempotency_key=f"{action}:{delivery.id}:{delivery.attempt_count}",
            data=data,
            causation_id=delivery.source_event_id,
        )

    async def _publish(
        self,
        *,
        event_name: str,
        organisation_id: str,
        correlation_id: str,
        actor_id: str | None,
        idempotency_key: str,
        data: dict[str, Any],
        causation_id: str | None = None,
    ) -> None:
        envelope = EventEnvelope(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_name=event_name,
            event_version=1,
            occurred_at=self._clock.now(),
            organisation_id=organisation_id,
            correlation_id=correlation_id or "",
            idempotency_key=idempotency_key,
            data=data,
            actor_id=actor_id,
            causation_id=causation_id,
        )
        await self._outbox.publish_event(envelope)

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


__all__ = [
    "ACTION_URL",
    "DEFAULT_PAGE_LIMIT",
    "DELIVER_JOB_TYPE",
    "MAX_PAGE_LIMIT",
    "ConsumeOutcome",
    "ConsumeResult",
    "DeliveryOutcome",
    "NotificationService",
    "solo_organisation_id",
]
