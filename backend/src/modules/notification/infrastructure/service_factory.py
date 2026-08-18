"""Wire NotificationService for API requests and workers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.notification.application.notification_service import NotificationService
from src.modules.notification.infrastructure.clock import SystemClock
from src.modules.notification.infrastructure.compliance_recipients import (
    ConfiguredComplianceRecipients,
)
from src.modules.notification.infrastructure.config_lists import parse_allowlist
from src.modules.notification.infrastructure.recipient_resolver import (
    SqlRecipientEmailResolver,
)
from src.modules.notification.infrastructure.repository import (
    SqlConsumedEventRepository,
    SqlDeliveryRepository,
    SqlPreferenceRepository,
    SqlProviderEventRepository,
    SqlTemplateDeploymentRepository,
)
from src.modules.notification.ports import WebhookVerifierPort
from src.platform.config import Settings, get_settings
from src.platform.messaging.outbox import SqlOutboxRepository


def build_notification_service(
    session: AsyncSession, settings: Settings | None = None
) -> NotificationService:
    cfg = settings or get_settings()
    audit = AuditService(repository=SqlAuditRepository(session))

    from src.bootstrap import build_email_adapter

    webhook_verifier: WebhookVerifierPort | None = None
    if cfg.resend_webhook_secret:
        from src.modules.notification.infrastructure.email.resend_webhook import (
            ResendWebhookVerifier,
        )

        webhook_verifier = ResendWebhookVerifier(cfg.resend_webhook_secret)

    return NotificationService(
        preferences=SqlPreferenceRepository(session),
        deliveries=SqlDeliveryRepository(session),
        consumed_events=SqlConsumedEventRepository(session),
        provider_events=SqlProviderEventRepository(session),
        template_deployments=SqlTemplateDeploymentRepository(session),
        email_port=build_email_adapter(),
        audit_port=audit,
        outbox=SqlOutboxRepository(session),
        clock=SystemClock(),
        recipient_resolver=SqlRecipientEmailResolver(session),
        compliance_recipients=ConfiguredComplianceRecipients(
            parse_allowlist(cfg.notification_compliance_allowlist)
        ),
        webhook_verifier=webhook_verifier,
        environment=cfg.environment,
        require_published_template=cfg.notification_require_published_template,
    )
