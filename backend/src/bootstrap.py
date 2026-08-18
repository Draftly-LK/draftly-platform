"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import IdentityPort
from src.modules.billing.infrastructure.platform_admin import (
    DenyAllPlatformAdminAdapter,
    SettingsPlatformAdminAdapter,
)
from src.modules.billing.ports import BillingProviderPort, PlatformAdminPort
from src.modules.notification.infrastructure.email.resend_adapter import ResendEmailAdapter
from src.modules.notification.ports import EmailPort
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.modules.party.infrastructure.event_log import LoggingEventAdapter
from src.modules.party.infrastructure.field_encryption import (
    LocalFieldEncryptionAdapter,
    build_field_encryption_adapter,
)
from src.modules.party.infrastructure.matter_access_stub import (
    StubMatterAccessAdapter,
    build_matter_access_adapter,
)
from src.platform.config import get_settings
from src.platform.messaging.dispatcher import MessageDispatcher
from src.platform.request_context import RequestContext

if TYPE_CHECKING:
    from src.modules.auth.application.auth_service import AuthService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.modules.approval.application.approval_service import ApprovalService
    from src.modules.check.application.check_service import CheckService
    from src.modules.document.application.ingestion_service import (
        SourceFileIngestionService,
    )
    from src.modules.document.application.processing_service import (
        DocumentProcessingService,
    )
    from src.modules.draft.application.draft_service import DraftService
    from src.modules.matter.application.matter_service import MatterService
    from src.modules.task.application.checklist_service import ChecklistService


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.approval.api.router import router as approval_router
    from src.modules.auth.api.router import router as auth_router
    from src.modules.billing.api.admin_router import router as billing_admin_router
    from src.modules.billing.api.router import router as billing_router
    from src.modules.check.api.router import router as check_router
    from src.modules.content_governance.api.router import router as rule_pack_router
    from src.modules.document.api.router import router as document_router
    from src.modules.draft.api.router import router as draft_router
    from src.modules.matter.api.router import router as matter_router
    from src.modules.notarial_register.api.router import router as notarial_register_router
    from src.modules.notification.api.router import router as notification_router
    from src.modules.obligations.api.router import router as obligations_router
    from src.modules.party.api.router import router as party_router
    from src.modules.task.api.router import router as checklist_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(rule_pack_router, prefix="/api/v1")
    app.include_router(matter_router, prefix="/api/v1")
    app.include_router(checklist_router, prefix="/api/v1")
    app.include_router(document_router, prefix="/api/v1")
    app.include_router(check_router, prefix="/api/v1")
    app.include_router(draft_router, prefix="/api/v1")
    app.include_router(approval_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(billing_admin_router, prefix="/api/v1")
    app.include_router(party_router, prefix="/api/v1")
    app.include_router(notification_router, prefix="/api/v1")
    app.include_router(obligations_router, prefix="/api/v1")
    app.include_router(notarial_register_router, prefix="/api/v1")


"""Environments where stub adapters may be selected at all.

Stubs bypass real providers (any bearer token becomes a fixed identity; canned
extraction results), so they are confined to developer machines and CI.
Anywhere else, incomplete provider configuration is a startup failure rather
than an open door.
"""
STUB_IDENTITY_ENVIRONMENTS = frozenset({"local", "test", "ci"})
STUB_EXTRACTION_ENVIRONMENTS = STUB_IDENTITY_ENVIRONMENTS


def build_identity_adapter() -> IdentityPort:
    """Return the appropriate IdentityPort implementation for this environment."""
    settings = get_settings()
    stub_allowed = settings.environment in STUB_IDENTITY_ENVIRONMENTS

    if settings.use_stub_identity:
        if not stub_allowed:
            raise RuntimeError(
                f"USE_STUB_IDENTITY is not permitted in environment "
                f"'{settings.environment}'. The stub adapter accepts any bearer "
                f"token as a fixed identity and is limited to "
                f"{sorted(STUB_IDENTITY_ENVIRONMENTS)}."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    if not settings.clerk_configured:
        if not stub_allowed:
            raise RuntimeError(
                f"Clerk identity is not configured and environment "
                f"'{settings.environment}' does not permit the stub adapter. "
                f"Set CLERK_ISSUER, CLERK_SECRET_KEY and CLERK_AUTHORIZED_PARTY."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter

    if not settings.clerk_authorized_party:
        raise RuntimeError("CLERK_AUTHORIZED_PARTY is required when Clerk identity is enabled.")
    return ClerkIdentityAdapter(
        issuer=settings.clerk_issuer,
        secret_key=settings.clerk_secret_key,
        audience=settings.clerk_audience or None,
        authorized_party=settings.clerk_authorized_party,
        leeway_seconds=settings.clerk_leeway_seconds,
    )


def build_checklist_service(session: AsyncSession) -> ChecklistService:
    """Assemble the checklist service over one request's session."""
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.task.application.checklist_service import ChecklistService
    from src.modules.task.infrastructure.repository import SqlChecklistRepository

    return ChecklistService(
        repository=SqlChecklistRepository(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_matter_service(session: AsyncSession) -> MatterService:
    """Assemble the matter service, including the ports it reaches out through."""
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.matter.application.matter_service import MatterService
    from src.modules.matter.infrastructure.fact_snapshot import SqlMatterFactAdapter
    from src.modules.matter.infrastructure.repository import (
        SqlIntakeAnswerRepository,
        SqlMatterRepository,
    )

    return MatterService(
        matters=SqlMatterRepository(session),
        answers=SqlIntakeAnswerRepository(session),
        facts=SqlMatterFactAdapter(session),
        checklist=build_checklist_service(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_check_service(session: AsyncSession) -> CheckService:
    """Assemble the check engine over one request's session.

    The service is also its own `check.contracts.IssueGatePort`, which is how
    drafting and approval read their gates without importing this module.
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.check.application.check_service import CheckService
    from src.modules.check.infrastructure.repository import SqlCheckRepository
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

    return CheckService(
        repository=SqlCheckRepository(session),
        facts=SqlConfirmedFactReader(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_draft_service(session: AsyncSession) -> DraftService:
    """Assemble form generation and preflight.

    ``candidates`` is left unwired: no module owns a candidate-fact reader yet,
    and without one every non-critical field simply stays unresolved. That is
    the honest degradation — the alternative would be prefilling a value nobody
    extracted (§9.3).
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.draft.application.draft_service import DraftService
    from src.modules.draft.infrastructure.repository import SqlGeneratedFormRepository
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

    return DraftService(
        repository=SqlGeneratedFormRepository(session),
        facts=SqlConfirmedFactReader(session),
        issues=build_check_service(session),
        checklist=build_checklist_service(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_approval_service(session: AsyncSession) -> ApprovalService:
    """Assemble approval, export, and registration-event recording.

    ``form_commands`` and ``matter_commands`` are the two writes this module
    makes into aggregates it does not own. Both are wired here because the
    composition root is the only place permitted to see both sides.
    """
    from src.modules.approval.application.approval_service import ApprovalService
    from src.modules.approval.infrastructure.repository import (
        SqlApprovalRepository,
        SqlFormExportRepository,
        SqlRegistrationEventRepository,
    )
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.draft.infrastructure.form_commands import (
        SqlGeneratedFormCommandAdapter,
    )
    from src.modules.matter.infrastructure.workflow_commands import (
        SqlMatterWorkflowCommandAdapter,
    )
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

    return ApprovalService(
        approvals=SqlApprovalRepository(session),
        exports=SqlFormExportRepository(session),
        events=SqlRegistrationEventRepository(session),
        forms=build_draft_service(session),
        facts=SqlConfirmedFactReader(session),
        issues=build_check_service(session),
        checklist=build_checklist_service(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
        form_commands=SqlGeneratedFormCommandAdapter(session),
        matter_commands=SqlMatterWorkflowCommandAdapter(session),
    )


def build_ingestion_service(session: AsyncSession) -> SourceFileIngestionService:
    """Assemble source-file ingestion and the document inbox.

    Storage follows the same fail-closed posture as identity and extraction: the
    local filesystem adapter is confined to local/test/ci, because it is not a
    durable or access-controlled store for client evidence.

    When no extraction provider is configured, or the data-protection gate is
    closed, ``pipeline`` stays ``None`` and every run finishes as
    PROCESSING_FAILED / NOT_CONFIGURED. Nothing reports a document as processed
    that nothing processed (§6.1).
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.document.application.ingestion_service import (
        SourceFileIngestionService,
    )
    from src.modules.document.application.processing_job import SynchronousProcessingJob
    from src.modules.document.infrastructure.repository import (
        SqlDocumentIngestionRepository,
    )
    from src.modules.document.infrastructure.storage_filesystem import (
        FilesystemSourceFileStorage,
    )

    settings = get_settings()

    if settings.source_file_storage != "filesystem":
        raise RuntimeError(
            f"Unknown SOURCE_FILE_STORAGE '{settings.source_file_storage}'. Valid: filesystem."
        )
    if settings.environment not in STUB_EXTRACTION_ENVIRONMENTS:
        raise RuntimeError(
            f"SOURCE_FILE_STORAGE=filesystem is not permitted in environment "
            f"'{settings.environment}'. Local-disk storage of client evidence is "
            f"limited to {sorted(STUB_EXTRACTION_ENVIRONMENTS)}."
        )
    storage = FilesystemSourceFileStorage(settings.source_file_storage_dir)

    provider_configured = settings.extraction_provider == "stub" or (
        settings.extraction_provider == "gemini" and bool(settings.gemini_api_key)
    )
    pipeline = build_processing_service() if provider_configured else None

    return SourceFileIngestionService(
        repository=SqlDocumentIngestionRepository(session),
        storage=storage,
        jobs=SynchronousProcessingJob(
            storage=storage,
            pipeline=pipeline,
            provider_name=settings.extraction_provider,
            data_protection_approved=settings.provider_data_approval,
        ),
        audit=AuditService(repository=SqlAuditRepository(session)),
        max_upload_bytes=settings.max_source_file_bytes,
        max_page_count=settings.max_source_file_pages,
        checklist_links=build_checklist_service(session),
    )


def build_processing_service() -> DocumentProcessingService:
    """Assemble the document-processing pipeline for this environment.

    Same fail-closed posture as identity: the stub is confined to
    local/test/ci, and selecting Gemini without an API key fails at once
    rather than at the first document.
    """
    from src.modules.document.application.processing_service import (
        DocumentProcessingService,
    )
    from src.modules.document.infrastructure.rasterizer_pypdfium import (
        PypdfiumRasterizer,
    )

    settings = get_settings()
    rasterizer = PypdfiumRasterizer(dpi=settings.raster_dpi)

    if settings.extraction_provider == "stub":
        if settings.environment not in STUB_EXTRACTION_ENVIRONMENTS:
            raise RuntimeError(
                f"EXTRACTION_PROVIDER=stub is not permitted in environment "
                f"'{settings.environment}'. The stub returns canned candidate "
                f"fields and is limited to {sorted(STUB_EXTRACTION_ENVIRONMENTS)}."
            )
        from src.modules.document.infrastructure.stub_adapter import (
            StubExtractionAdapter,
        )

        stub = StubExtractionAdapter()
        return DocumentProcessingService(
            rasterizer=rasterizer,
            classifier=stub,
            extractor=stub,
            provider_name="stub",
        )

    if settings.extraction_provider != "gemini":
        raise RuntimeError(
            f"Unknown EXTRACTION_PROVIDER '{settings.extraction_provider}'. Valid: gemini, stub."
        )
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when EXTRACTION_PROVIDER=gemini.")

    from google import genai

    from src.modules.document.infrastructure.gemini_adapter import (
        GeminiExtractionAdapter,
    )

    adapter = GeminiExtractionAdapter(
        client=genai.Client(api_key=settings.gemini_api_key),
        classify_model=settings.gemini_classify_model,
        extract_model=settings.gemini_extract_model,
    )
    return DocumentProcessingService(
        rasterizer=rasterizer,
        classifier=adapter,
        extractor=adapter,
        provider_name="gemini",
    )


def build_billing_adapter() -> BillingProviderPort:
    """Return the billing provider adapter for this environment."""
    settings = get_settings()
    if settings.use_stub_billing or not settings.payhere_configured:
        from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter

        return StubBillingAdapter()
    from src.modules.billing.infrastructure.payhere_adapter import PayHereBillingAdapter

    return PayHereBillingAdapter(
        merchant_secret=settings.payhere_merchant_secret,
        checkout_base_url=settings.payhere_checkout_base_url,
    )


def build_platform_admin_adapter() -> PlatformAdminPort:
    """Resolve platform.administer from deployment config until auth owns the grant."""
    settings = get_settings()
    if settings.platform_admin_user_ids.strip():
        return SettingsPlatformAdminAdapter(settings.platform_admin_user_ids)
    return DenyAllPlatformAdminAdapter()


def build_email_adapter() -> EmailPort:
    """Console adapter for local/tests; Resend only when explicitly enabled."""
    settings = get_settings()
    if settings.resend_api_key and settings.resend_outbound_enabled:
        domains = frozenset(
            part.strip()
            for part in settings.resend_allowed_recipient_domains.split(",")
            if part.strip()
        )
        return ResendEmailAdapter(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
            outbound_enabled=True,
            allowed_recipient_domains=domains if domains else None,
        )
    from src.modules.notification.infrastructure.email.console_adapter import (
        ConsoleEmailAdapter,
    )

    return ConsoleEmailAdapter()


def build_deadline_rule_port() -> FixtureDeadlineRulePort:
    """Fixture-approved deadline rules for local and test environments."""
    return FixtureDeadlineRulePort()


class AuthPractisingNotaryAdapter:
    """Bridges party_service's PractisingNotaryPort to auth_service."""

    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    async def assert_practising(self, ctx: RequestContext) -> None:
        await self._auth.require_practising_notary(ctx)


def build_party_field_encryption() -> LocalFieldEncryptionAdapter:
    """Local adapter today; production KMS remains an open decision."""
    return build_field_encryption_adapter(get_settings())


def build_party_matter_access() -> StubMatterAccessAdapter:
    """Narrow stub — matter_service does not exist yet."""
    return build_matter_access_adapter(get_settings().environment)


def build_party_event_adapter() -> LoggingEventAdapter:
    """No broker chosen yet; events are recorded, not transported."""
    return LoggingEventAdapter()


def build_dispatcher() -> MessageDispatcher:
    """Register worker handlers for every module job and event consumer."""
    from src.modules.notification.application.notification_service import DELIVER_JOB_TYPE
    from src.modules.notification.jobs import (
        NOTIFICATION_CONSUMED_EVENTS,
        consume_registered_event,
        run_delivery_job,
    )
    from src.platform.messaging.dispatcher import Handler, MessageDispatcher, MessageResult
    from src.platform.messaging.outbox import ClaimedMessage

    dispatcher = MessageDispatcher()

    async def deliver_handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        outcome = await run_delivery_job(session, message.payload)
        if outcome in {"delivered", "suppressed", "permanent-failure", "unknown-delivery"}:
            return MessageResult.DONE
        if outcome == "retry":
            return MessageResult.RETRY
        if outcome == "dead-letter":
            return MessageResult.DEAD_LETTER
        return MessageResult.FAILED

    dispatcher.register_job(DELIVER_JOB_TYPE, deliver_handler)

    def make_event_handler(event_name: str) -> Handler:
        async def handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
            outcome = await consume_registered_event(session, message.payload)
            if outcome in {"processed", "duplicate", "suppressed"}:
                return MessageResult.DONE
            if outcome == "dead-letter":
                return MessageResult.DEAD_LETTER
            return MessageResult.FAILED

        _ = event_name
        return handler

    for event_name in NOTIFICATION_CONSUMED_EVENTS:
        dispatcher.register_event(event_name, make_event_handler(event_name))

    return dispatcher
