"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import IdentityPort
from src.modules.billing.infrastructure.platform_admin import (
    DenyAllPlatformAdminAdapter,
    SettingsPlatformAdminAdapter,
)
from src.modules.billing.ports import BillingProviderPort, PlatformAdminPort
from src.modules.document.ports import SourceFileStoragePort
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
from src.platform.errors import ServiceMisconfiguredError
from src.platform.messaging.dispatcher import MessageDispatcher
from src.platform.request_context import RequestContext

if TYPE_CHECKING:
    from src.modules.auth.application.auth_service import AuthService
    from src.modules.document.application.review_service import DocumentReviewService
    from src.modules.matter.application.scope_service import MatterScopeService
    from src.modules.matter_agent.application.agent_service import AgentService
    from src.modules.verification.application.review_service import FactReviewService

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
    from src.modules.verification.application.fact_query_service import FactQueryService


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
    from src.modules.library.api.case_router import router as case_library_router
    from src.modules.library.api.router import router as library_router
    from src.modules.matter.api.router import router as matter_router
    from src.modules.matter_agent.api.router import router as matter_agent_router
    from src.modules.notarial_register.api.router import router as notarial_register_router
    from src.modules.notification.api.router import router as notification_router
    from src.modules.obligations.api.router import router as obligations_router
    from src.modules.party.api.router import router as party_router
    from src.modules.research.api.case_router import router as case_research_router
    from src.modules.research.api.router import router as research_router
    from src.modules.task.api.router import router as checklist_router
    from src.modules.verification.api.router import router as verification_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(rule_pack_router, prefix="/api/v1")
    app.include_router(matter_router, prefix="/api/v1")
    app.include_router(checklist_router, prefix="/api/v1")
    app.include_router(document_router, prefix="/api/v1")
    app.include_router(verification_router, prefix="/api/v1")
    app.include_router(check_router, prefix="/api/v1")
    app.include_router(draft_router, prefix="/api/v1")
    app.include_router(case_library_router, prefix="/api/v1")
    app.include_router(library_router, prefix="/api/v1")
    app.include_router(matter_agent_router, prefix="/api/v1")
    app.include_router(approval_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(billing_admin_router, prefix="/api/v1")
    app.include_router(party_router, prefix="/api/v1")
    app.include_router(research_router, prefix="/api/v1")
    app.include_router(case_research_router, prefix="/api/v1")
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

#: Where local-disk storage of client evidence is tolerated. Same membership as
#: the stub sets, but named separately: this gate is about durability and access
#: control, not about bypassing a provider, and the two could diverge.
LOCAL_ONLY_STORAGE_ENVIRONMENTS = frozenset({"local", "test", "ci"})


def build_identity_adapter() -> IdentityPort:
    """Return the appropriate IdentityPort implementation for this environment."""
    settings = get_settings()
    stub_allowed = settings.environment in STUB_IDENTITY_ENVIRONMENTS

    if settings.use_stub_identity:
        if not stub_allowed:
            raise ServiceMisconfiguredError(
                f"USE_STUB_IDENTITY is not permitted in environment "
                f"'{settings.environment}'. The stub adapter accepts any bearer "
                f"token as a fixed identity and is limited to "
                f"{sorted(STUB_IDENTITY_ENVIRONMENTS)}."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    if not settings.clerk_configured:
        if not stub_allowed:
            raise ServiceMisconfiguredError(
                f"Clerk identity is not configured and environment "
                f"'{settings.environment}' does not permit the stub adapter. "
                f"Set CLERK_ISSUER, CLERK_SECRET_KEY and CLERK_AUTHORIZED_PARTY."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter

    if not settings.clerk_authorized_parties:
        raise ServiceMisconfiguredError(
            "CLERK_AUTHORIZED_PARTY is required when Clerk identity is enabled."
        )
    return ClerkIdentityAdapter(
        issuer=settings.clerk_issuer,
        secret_key=settings.clerk_secret_key,
        audience=settings.clerk_audience or None,
        authorized_parties=settings.clerk_authorized_parties,
        leeway_seconds=settings.clerk_leeway_seconds,
    )


def build_checklist_service(session: AsyncSession) -> ChecklistService:
    """Assemble the checklist service over one request's session."""
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.document.infrastructure.requirement_reader import SqlRequirementDocumentReader
    from src.modules.task.application.checklist_service import ChecklistService
    from src.modules.task.infrastructure.repository import SqlChecklistRepository
    from src.modules.verification.infrastructure.repository import SqlEvidenceReader

    return ChecklistService(
        documents=SqlRequirementDocumentReader(session, build_source_file_storage()),
        evidence=SqlEvidenceReader(session),
        matter_lock=_build_document_matter_lock(session),
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
    from src.platform.db.idempotency import SqlIdempotencyStore

    return MatterService(
        replay=SqlIdempotencyStore(session),
        matters=SqlMatterRepository(session),
        answers=SqlIntakeAnswerRepository(session),
        facts=SqlMatterFactAdapter(session),
        checklist=build_checklist_service(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_agent_service(session: AsyncSession) -> AgentService:
    """Assemble the matter agent over one request's session.

    Memory is the null implementation unless Supermemory is both enabled and
    approved, so the default deployment runs Neon-only and a missing provider
    is a configuration, not a failure (`matter-agent-service.md` §Failure
    Modes).
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.matter_agent.application.actions import ActionExecutor
    from src.modules.matter_agent.application.agent_service import AgentService, AgentSettings
    from src.modules.matter_agent.infrastructure.event_publisher import AgentEventPublisher
    from src.modules.matter_agent.infrastructure.job_repository import SqlAgentJobPort
    from src.modules.matter_agent.infrastructure.matter_access import (
        SqlMatterAccessAdapter,
        SqlTargetVersionAdapter,
    )
    from src.modules.matter_agent.infrastructure.repository import (
        NeonConversationAdapter,
        SqlAgentSessionRepository,
        SqlPendingActionRepository,
    )

    settings = get_settings()
    return AgentService(
        sessions=SqlAgentSessionRepository(session),
        conversation=NeonConversationAdapter(session),
        matters=SqlMatterAccessAdapter(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
        settings=AgentSettings(
            enabled=settings.matter_agent_enabled,
            model=settings.matter_agent_model,
            max_tool_calls=settings.matter_agent_max_tool_calls,
            turn_timeout_seconds=settings.matter_agent_turn_timeout_seconds,
        ),
        jobs=SqlAgentJobPort(session),
        actions=SqlPendingActionRepository(session),
        targets=SqlTargetVersionAdapter(session),
        events=AgentEventPublisher(session),
        authorizer=_build_agent_authorizer(session),
        action_executor=ActionExecutor(checklist=build_checklist_service(session)),
    )


def _build_agent_authorizer(session: AsyncSession) -> Any:
    """The real `auth_service`, so confirmation re-checks the live role map."""
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.auth.application.auth_service import AuthService
    from src.modules.auth.infrastructure.repository import (
        SqlUserIdentityRepository,
        SqlUserRepository,
    )

    return AuthService(
        identity_port=build_identity_adapter(),
        user_identity_repo=SqlUserIdentityRepository(session),
        user_repo=SqlUserRepository(session),
        audit_port=AuditService(repository=SqlAuditRepository(session)),
    )


async def run_agent_turn(
    session: AsyncSession,
    *,
    job_id: str,
    chat_session: Any,
    user_message: Any,
) -> Any:
    """Assemble and run one agent turn inside the worker's transaction.

    The user's role is re-read here rather than trusted from the queued
    payload, so a role change between enqueue and execution takes effect
    immediately and a stale payload cannot widen authority.
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.auth.domain.policies import CAPABILITY_MAP
    from src.modules.auth.infrastructure.repository import SqlUserRepository
    from src.modules.matter_agent.application.tool_executor import ExecutionContext, ToolExecutor
    from src.modules.matter_agent.application.turn_runner import TurnRequest, TurnRunner
    from src.modules.matter_agent.domain.models import AgentSession, SessionState, TurnBudget
    from src.modules.matter_agent.infrastructure.event_publisher import AgentEventPublisher
    from src.modules.matter_agent.infrastructure.repository import (
        NeonConversationAdapter,
        SqlToolCallRepository,
    )
    from src.platform.request_context import RequestContext

    settings = get_settings()
    user = await SqlUserRepository(session).get(chat_session.user_id)
    if user is None:
        from src.modules.matter_agent.domain.models import JobState, TurnResult

        return TurnResult(
            job_id=job_id, outcome=JobState.FAILED, tool_call_count=0, failure_class="unknown_actor"
        )

    role = user.role
    if role is None:
        from src.modules.matter_agent.domain.models import JobState, TurnResult

        return TurnResult(
            job_id=job_id, outcome=JobState.FAILED, tool_call_count=0, failure_class="unknown_role"
        )
    capabilities = CAPABILITY_MAP.get(role, frozenset())
    domain_session = AgentSession(
        id=chat_session.id,
        user_id=chat_session.user_id,
        matter_id=chat_session.matter_id,
        model_version=chat_session.model_version,
        prompt_version=chat_session.prompt_version,
        state=SessionState(chat_session.state),
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        active_conversation_id=user_message.conversation_id,
    )
    ctx = RequestContext(actor_id=chat_session.user_id, account_role=role)
    execution = ExecutionContext(
        ctx=ctx,
        session_id=chat_session.id,
        matter_id=chat_session.matter_id,
        job_id=job_id,
        model_version=chat_session.model_version,
        prompt_version=chat_session.prompt_version,
        user_capabilities=frozenset(capabilities),
        matter_owned=True,
        is_practising_notary=bool(user.notary_registration),
    )
    tools = build_agent_tools(session, session_id=chat_session.id, memory=build_agent_memory())
    runner = TurnRunner(
        model=build_agent_model(),
        conversation=NeonConversationAdapter(session),
        memory=build_agent_memory(),
        executor=ToolExecutor(
            tools=tools,
            tool_calls=SqlToolCallRepository(session),
            audit=AuditService(repository=SqlAuditRepository(session)),
            events=AgentEventPublisher(session),
        ),
    )
    result = await runner.run(
        TurnRequest(
            session=domain_session,
            job_id=job_id,
            user_message=user_message.content,
            execution=execution,
            budget=TurnBudget(
                max_tool_calls=settings.matter_agent_max_tool_calls,
                timeout_seconds=settings.matter_agent_turn_timeout_seconds,
            ),
        )
    )

    from src.modules.matter_agent.domain.models import JobState as _JobState
    from src.modules.matter_agent.infrastructure.stream_repository import (
        SqlStreamEventRepository,
    )

    succeeded = result.outcome is _JobState.SUCCEEDED
    await AgentEventPublisher(session).publish(
        "agent.turn-completed" if succeeded else "agent.turn-failed",
        user_id=chat_session.user_id,
        matter_id=chat_session.matter_id,
        actor_id=chat_session.user_id,
        correlation_id=ctx.correlation_id,
        idempotency_key=f"agent.turn:{job_id}",
        data=(
            {
                "jobId": job_id,
                "toolCallCount": result.tool_call_count,
                "outcome": result.outcome.value,
            }
            if succeeded
            else {"jobId": job_id, "failureClass": result.failure_class or "unknown"}
        ),
    )
    # A progress frame so a reconnecting client sees the outcome without a poll.
    await SqlStreamEventRepository(session).append(
        job_id=job_id,
        user_id=chat_session.user_id,
        event_type="turn-finished",
        data={
            "jobId": job_id,
            "state": result.outcome.value,
            "toolCallCount": result.tool_call_count,
            "pendingActionIds": list(result.pending_action_ids),
        },
    )
    return result


def build_agent_tools(session: AsyncSession, *, session_id: str, memory: Any) -> dict[str, Any]:
    """Bind every implemented tool to the application service that owns it.

    Tools call services, never repositories: the agent inherits each service's
    rules rather than re-deriving them. A name absent from this registry is
    denied with `tool_not_implemented` and audited — see
    `matter_agent.application.tools.OUT_OF_SCOPE` for why each gap exists.
    """
    from src.modules.matter_agent.application import read_adapters as ra
    from src.modules.matter_agent.application import read_tools as rt
    from src.modules.matter_agent.application import write_tools as wt
    from src.modules.matter_agent.application.tools import SaveWorkingNoteTool, build_tool_registry
    from src.modules.matter_agent.infrastructure.note_repository import SqlMatterNoteRepository
    from src.modules.matter_agent.infrastructure.repository import SqlPendingActionRepository
    from src.modules.verification.application.fact_query_service import FactQueryService
    from src.modules.verification.infrastructure.repository import SqlVerificationRepository

    matters = build_matter_service(session)
    checklist = build_checklist_service(session)
    ingestion = build_ingestion_service(session)
    review = build_document_review_service(session)
    checks = build_check_service(session)
    drafts = build_draft_service(session)
    facts = FactQueryService(repository=SqlVerificationRepository(session))

    documents = ra.DocumentReadAdapter(ingestion=ingestion, review=review)

    return build_tool_registry(
        {
            # Reads
            rt.ReadMatterSummaryTool.name: rt.ReadMatterSummaryTool(
                ra.MatterSummaryAdapter(matters)
            ),
            rt.ReadChecklistStateTool.name: rt.ReadChecklistStateTool(
                ra.ChecklistSummaryAdapter(checklist)
            ),
            rt.ReadDocumentStatusTool.name: rt.ReadDocumentStatusTool(documents),
            rt.ReadDocumentExtractionTool.name: rt.ReadDocumentExtractionTool(documents),
            rt.ReadDocumentOcrPagesTool.name: rt.ReadDocumentOcrPagesTool(documents),
            rt.ReadVerifiedFactsTool.name: rt.ReadVerifiedFactsTool(ra.FactReadAdapter(facts)),
            rt.ReadDraftPreflightTool.name: rt.ReadDraftPreflightTool(ra.DraftReadAdapter(drafts)),
            rt.SearchMatterMemoryTool.name: rt.SearchMatterMemoryTool(memory),
            rt.ListMatterInventoryTool.name: rt.ListMatterInventoryTool(
                ra.InventoryAdapter(matters=matters, documents=documents)
            ),
            # Writes
            wt.RunChecksTool.name: wt.RunChecksTool(checks, matters),
            wt.GenerateWorkingDraftTool.name: wt.GenerateWorkingDraftTool(drafts, matters),
            SaveWorkingNoteTool.name: SaveWorkingNoteTool(
                SqlMatterNoteRepository(session), session_id=session_id
            ),
            wt.AssignChecklistItemTool.name: wt.AssignChecklistItemTool(checklist),
            wt.UpdateChecklistDueDateTool.name: wt.UpdateChecklistDueDateTool(checklist),
            wt.RequestChecklistCollectionTool.name: wt.RequestChecklistCollectionTool(checklist),
            wt.RecordDocumentReceiptTool.name: wt.RecordDocumentReceiptTool(checklist),
            wt.ProposeDocumentLinkTool.name: wt.ProposeDocumentLinkTool(checklist),
            wt.UpdateFieldCandidateTool.name: wt.UpdateFieldCandidateTool(review),
            wt.ProposeChecklistDecisionTool.name: wt.ProposeChecklistDecisionTool(
                SqlPendingActionRepository(session), session_id=session_id
            ),
        }
    )


def build_agent_model() -> Any:
    """The model adapter. Deterministic fake unless Gemini is configured.

    Falling back to the fake rather than raising means a missing key degrades
    the assistant instead of breaking the deployment, and no test ever reaches
    a provider by accident.
    """
    settings = get_settings()
    if settings.matter_agent_enabled and settings.gemini_api_key:
        from src.modules.matter_agent.infrastructure.gemini_adapter import GeminiAgentAdapter

        return GeminiAgentAdapter(
            api_key=settings.gemini_api_key, model=settings.matter_agent_model
        )
    from src.modules.matter_agent.infrastructure.fake_model import FakeAgentModelAdapter

    return FakeAgentModelAdapter()


def build_agent_memory() -> Any:
    """Semantic memory, or the null implementation.

    Supermemory needs both the feature switch and the data-transfer approval.
    Either one absent means no recall, never an error
    (`memory-service.md` §11.2).
    """
    settings = get_settings()
    if settings.supermemory_enabled and settings.supermemory_real_data_approved:
        from src.modules.matter_agent.infrastructure.supermemory_adapter import (
            SupermemoryMemoryAdapter,
        )

        return SupermemoryMemoryAdapter(
            api_key=settings.supermemory_api_key,
            base_url=settings.supermemory_base_url,
            hmac_key=settings.supermemory_container_hmac_key,
        )
    from src.modules.matter_agent.ports import NullMemoryPort

    return NullMemoryPort()


def build_check_service(session: AsyncSession) -> CheckService:
    """Assemble the check engine over one request's session.

    The service is also its own `check.contracts.IssueGatePort`, which is how
    drafting and approval read their gates without importing this module.
    """
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.check.application.check_service import CheckService
    from src.modules.check.infrastructure.repository import SqlCheckRepository
    from src.modules.matter.infrastructure.scope_repository import SqlMatterScopeRepository
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

    return CheckService(
        matter_lock=_build_document_matter_lock(session),
        scopes=SqlMatterScopeRepository(session),
        repository=SqlCheckRepository(session),
        facts=SqlConfirmedFactReader(session),
        audit=AuditService(repository=SqlAuditRepository(session)),
    )


def build_fact_query_service(session: AsyncSession) -> FactQueryService:
    """Assemble the tenant-scoped verified-facts query service."""
    from src.modules.verification.application.fact_query_service import FactQueryService
    from src.modules.verification.infrastructure.repository import SqlVerificationRepository

    return FactQueryService(repository=SqlVerificationRepository(session))


def build_matter_scope_service(session: AsyncSession) -> MatterScopeService:
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.check.infrastructure.evidence_invalidation import SqlCheckInputInvalidation
    from src.modules.draft.infrastructure.evidence_invalidation import SqlFormInputInvalidation
    from src.modules.matter.application.association_invalidation import (
        MatterAssociationInvalidation,
    )
    from src.modules.matter.application.scope_service import MatterScopeService
    from src.modules.matter.infrastructure.scope_repository import SqlMatterScopeRepository
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader
    from src.platform.db.idempotency import SqlIdempotencyStore

    return MatterScopeService(
        SqlMatterScopeRepository(session),
        build_matter_service(session),
        AuditService(repository=SqlAuditRepository(session)),
        SqlIdempotencyStore(session),
        MatterAssociationInvalidation(
            SqlCheckInputInvalidation(
                session, AuditService(repository=SqlAuditRepository(session))
            ),
            SqlConfirmedFactReader(session),
            SqlFormInputInvalidation(session, AuditService(repository=SqlAuditRepository(session))),
        ),
    )


def build_fact_review_service(session: AsyncSession) -> FactReviewService:
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.check.infrastructure.evidence_invalidation import SqlCheckInputInvalidation
    from src.modules.document.infrastructure.fact_reader import SqlDocumentFactReader
    from src.modules.draft.infrastructure.evidence_invalidation import SqlFormInputInvalidation
    from src.modules.verification.application.review_service import FactReviewService
    from src.modules.verification.infrastructure.repository import (
        SqlConfirmedFactReader,
        SqlVerificationRepository,
    )
    from src.platform.db.idempotency import SqlIdempotencyStore

    return FactReviewService(
        SqlVerificationRepository(session),
        build_matter_service(session),
        build_matter_scope_service(session),
        SqlDocumentFactReader(session, build_source_file_storage()),
        AuthPractisingNotaryAdapter(_build_agent_authorizer(session)),
        SqlIdempotencyStore(session),
        AuditService(repository=SqlAuditRepository(session)),
        SqlConfirmedFactReader(session),
        SqlCheckInputInvalidation(session, AuditService(repository=SqlAuditRepository(session))),
        SqlFormInputInvalidation(session, AuditService(repository=SqlAuditRepository(session))),
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
    from src.modules.matter.infrastructure.workflow_commands import (
        SqlMatterWorkflowCommandAdapter,
    )
    from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

    facts, checklist, matter_workflow = _approval_gate_inputs(
        session, SqlConfirmedFactReader(session), SqlMatterWorkflowCommandAdapter(session)
    )
    return DraftService(
        matter_lock=_build_document_matter_lock(session),
        repository=SqlGeneratedFormRepository(session),
        facts=facts,
        issues=build_check_service(session),
        checklist=checklist,
        audit=AuditService(repository=SqlAuditRepository(session)),
        matter_workflow=matter_workflow,
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

    facts, checklist, matter_commands = _approval_gate_inputs(
        session, SqlConfirmedFactReader(session), SqlMatterWorkflowCommandAdapter(session)
    )
    return ApprovalService(
        matter_lock=_build_document_matter_lock(session),
        approvals=SqlApprovalRepository(session),
        exports=SqlFormExportRepository(session),
        events=SqlRegistrationEventRepository(session),
        forms=build_draft_service(session),
        facts=facts,
        issues=build_check_service(session),
        checklist=checklist,
        audit=AuditService(repository=SqlAuditRepository(session)),
        form_commands=SqlGeneratedFormCommandAdapter(session),
        matter_commands=matter_commands,
    )


def _approval_gate_inputs(
    session: AsyncSession, facts: Any, matter_workflow: Any
) -> tuple[Any, Any, Any]:
    """The fact, checklist and matter-state ports drafting and approval share.

    ``DEMO_RELAXED_GATES`` swaps in the overrides from `src/demo_gates.py`, and
    like the other stand-ins it is refused outside the stub environments.
    """
    settings = get_settings()
    if not settings.demo_relaxed_gates:
        return facts, build_checklist_service(session), matter_workflow
    if settings.environment not in STUB_IDENTITY_ENVIRONMENTS:
        raise ServiceMisconfiguredError(
            f"DEMO_RELAXED_GATES is not permitted in environment '{settings.environment}'. "
            f"It sets approval rules aside for synthetic demos and is limited to "
            f"{sorted(STUB_IDENTITY_ENVIRONMENTS)}."
        )
    from src.demo_gates import FormScopedFactReader, NonBlockingChecklist
    from src.modules.matter.infrastructure.workflow_commands import (
        DemoMatterWorkflowCommandAdapter,
    )

    return (
        FormScopedFactReader(facts),
        NonBlockingChecklist(),
        DemoMatterWorkflowCommandAdapter(session),
    )


@lru_cache(maxsize=1)
def _gcs_client(project: str, bucket_name: str) -> Any:
    """One storage client per process, with the bucket policy checked once.

    `build_ingestion_service` runs per HTTP request (the router resolves it
    through `Depends`), so building a client here rather than caching would mean
    an ADC token refresh and a fresh connection pool on every upload.
    `storage.Client` is thread-safe, so one instance is safe across the
    `asyncio.to_thread` hops the adapter uses.

    The bucket-policy check rides along for the same reason: it costs one API
    call per process instead of one per request.

    Tests that change storage settings must call ``_gcs_client.cache_clear()``
    as well as resetting the settings cache, or a client built under one
    configuration leaks into the next test.
    """
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import storage  # type: ignore[attr-defined]

    try:
        # Passed explicitly rather than inferred from ADC: the bucket does not
        # necessarily live in the caller's default gcloud project.
        client = storage.Client(project=project)
    except DefaultCredentialsError as exc:
        # Reported like every other wiring failure here — naming what to set —
        # rather than as a provider stack trace from the composition root.
        raise ServiceMisconfiguredError(
            "SOURCE_FILE_STORAGE=gcs found no Application Default Credentials. "
            "In a deployed environment attach a workload identity; locally run "
            "'gcloud auth application-default login'."
        ) from exc
    _assert_bucket_policy(client, bucket_name)
    return client


def _assert_bucket_policy(client: Any, bucket_name: str) -> None:
    """Refuse to start against a bucket that is not configured to hold evidence.

    `storage-service.md` §7 requires startup to refuse a missing bucket, public
    access, disabled uniform access, or an unapproved location. Finding this at
    boot is the difference between a deployment that fails and a deployment that
    quietly stores client evidence somewhere readable.

    Note for deployment: this calls `get_bucket`, which needs
    `storage.buckets.get`. `roles/storage.objectAdmin` does not grant it — the
    runtime identity also needs `roles/storage.legacyBucketReader` or a custom
    role, or boot fails with a 403.
    """
    from google.api_core.exceptions import GoogleAPIError

    settings = get_settings()
    try:
        bucket = client.get_bucket(bucket_name)
    except GoogleAPIError as exc:
        raise ServiceMisconfiguredError(
            f"DRAFTLY_GCS_BUCKET '{bucket_name}' could not be read at startup: "
            f"{type(exc).__name__}. Check the bucket exists and the runtime "
            f"identity has storage.buckets.get."
        ) from exc

    iam = bucket.iam_configuration
    if not iam.uniform_bucket_level_access_enabled:
        raise ServiceMisconfiguredError(
            f"Bucket '{bucket_name}' does not have uniform bucket-level access "
            f"enabled. Object ACLs are never used for client evidence."
        )
    if iam.public_access_prevention != "enforced":
        raise ServiceMisconfiguredError(
            f"Bucket '{bucket_name}' does not enforce public access prevention."
        )
    expected = settings.gcs_location
    if expected and (bucket.location or "").lower() != expected.lower():
        raise ServiceMisconfiguredError(
            f"Bucket '{bucket_name}' is in '{bucket.location}', not the approved "
            f"DRAFTLY_GCS_LOCATION '{expected}'. Data residency is an approval item."
        )


def build_source_file_storage() -> SourceFileStoragePort:
    """Select the object store for uploaded evidence.

    Filesystem is confined to local/test/ci because it has no encryption at
    rest, no object versioning, and no lifecycle policy. GCS carries no
    environment restriction — a developer working against the staging bucket is
    a supported case — but it is gated on the real-data approval instead, since
    a matter's uploaded evidence is client material by definition.
    """
    settings = get_settings()

    if settings.source_file_storage == "filesystem":
        if settings.environment not in LOCAL_ONLY_STORAGE_ENVIRONMENTS:
            raise ServiceMisconfiguredError(
                f"SOURCE_FILE_STORAGE=filesystem is not permitted in environment "
                f"'{settings.environment}'. Local-disk storage of client evidence is "
                f"limited to {sorted(LOCAL_ONLY_STORAGE_ENVIRONMENTS)}."
            )
        from src.modules.document.infrastructure.storage_filesystem import (
            FilesystemSourceFileStorage,
        )

        return FilesystemSourceFileStorage(settings.source_file_storage_dir)

    if settings.source_file_storage == "gcs":
        if not settings.gcs_bucket:
            raise ServiceMisconfiguredError(
                "DRAFTLY_GCS_BUCKET is required when SOURCE_FILE_STORAGE=gcs."
            )
        if not settings.gcs_project_id:
            raise ServiceMisconfiguredError(
                "DRAFTLY_GCS_PROJECT_ID is required when SOURCE_FILE_STORAGE=gcs."
            )
        if not settings.storage_real_data_approved:
            raise ServiceMisconfiguredError(
                "DRAFTLY_STORAGE_REAL_DATA_APPROVED must be true before "
                "SOURCE_FILE_STORAGE=gcs can accept client evidence. Record the "
                "bucket region, retention, access, and deletion terms first."
            )
        from src.modules.document.infrastructure.storage_gcs import GcsSourceFileStorage

        return GcsSourceFileStorage(
            client=_gcs_client(settings.gcs_project_id, settings.gcs_bucket),
            bucket_name=settings.gcs_bucket,
            real_data_approved=settings.storage_real_data_approved,
        )

    raise ServiceMisconfiguredError(
        f"Unknown SOURCE_FILE_STORAGE '{settings.source_file_storage}'. Valid: filesystem, gcs."
    )


def build_ingestion_service(session: AsyncSession) -> SourceFileIngestionService:
    """Assemble source-file ingestion and the document inbox.

    Storage follows the same fail-closed posture as identity and extraction —
    see `build_source_file_storage`.

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
    from src.modules.matter.infrastructure.workflow_commands import (
        SqlMatterWorkflowCommandAdapter,
    )

    settings = get_settings()
    storage = build_source_file_storage()

    v1_providers = {"vision-gemini", "vision-stub"}
    provider_configured = settings.extraction_provider in {"stub", "vision-stub"} or (
        settings.extraction_provider in {"gemini", "vision-gemini"}
        and bool(settings.gemini_api_key)
    )
    pipeline = (
        build_processing_service()
        if provider_configured and settings.extraction_provider not in v1_providers
        else None
    )
    v1_pipeline = (
        build_v1_processing_pipeline()
        if provider_configured and settings.extraction_provider in v1_providers
        else None
    )
    matter_types = None
    if v1_pipeline is not None:
        from src.modules.document.infrastructure.matter_document_types import (
            GovernedMatterDocumentTypesAdapter,
        )

        matter_types = GovernedMatterDocumentTypesAdapter()

    return SourceFileIngestionService(
        repository=SqlDocumentIngestionRepository(session),
        storage=storage,
        jobs=SynchronousProcessingJob(
            storage=storage,
            pipeline=pipeline,
            provider_name=settings.extraction_provider,
            data_protection_approved=settings.provider_data_approval,
            v1_pipeline=v1_pipeline,
            matter_document_types=matter_types,
        ),
        audit=AuditService(repository=SqlAuditRepository(session)),
        max_upload_bytes=settings.max_source_file_bytes,
        max_page_count=settings.max_source_file_pages,
        checklist_links=build_checklist_service(session),
        matter_lock=_build_document_matter_lock(session),
        fact_invalidation=_build_fact_evidence_invalidation(session),
        refresh_extractor=v1_pipeline,
        matter_document_types=matter_types,
        refresh_provider=settings.extraction_provider,
        refresh_data_approved=settings.provider_data_approval,
        matter_workflow=SqlMatterWorkflowCommandAdapter(session),
    )


def _build_document_matter_lock(session: AsyncSession) -> Any:
    from src.modules.matter.infrastructure.scope_repository import SqlMatterScopeRepository

    return SqlMatterScopeRepository(session)


def _build_fact_evidence_invalidation(session: AsyncSession) -> Any:
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.check.infrastructure.evidence_invalidation import SqlCheckInputInvalidation
    from src.modules.document.application.invalidation import DocumentEvidenceInvalidation
    from src.modules.draft.infrastructure.evidence_invalidation import SqlFormInputInvalidation
    from src.modules.task.infrastructure.evidence_invalidation import SqlDocumentLinkInvalidation
    from src.modules.verification.infrastructure.evidence_invalidation import (
        SqlFactEvidenceInvalidation,
    )

    audit = AuditService(repository=SqlAuditRepository(session))
    return DocumentEvidenceInvalidation(
        SqlFactEvidenceInvalidation(session, audit),
        SqlDocumentLinkInvalidation(session, audit),
        SqlCheckInputInvalidation(session, audit),
        SqlFormInputInvalidation(session, audit),
    )


def build_document_review_service(session: AsyncSession) -> DocumentReviewService:
    from src.modules.audit.application.audit_service import AuditService
    from src.modules.audit.infrastructure.repository import SqlAuditRepository
    from src.modules.document.application.review_service import DocumentReviewService
    from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
    from src.modules.verification.application.candidate_approval import (
        VerificationCandidateApprovalAdapter,
    )
    from src.modules.verification.infrastructure.repository import SqlVerificationRepository

    return DocumentReviewService(
        repository=SqlDocumentIngestionRepository(session),
        storage=build_source_file_storage(),
        audit=AuditService(repository=SqlAuditRepository(session)),
        candidate_approval=VerificationCandidateApprovalAdapter(
            build_fact_review_service(session), SqlVerificationRepository(session)
        ),
    )


def build_v1_processing_pipeline() -> Any:
    """Wire the proposal's Vision OCR + Flash-Lite path using ADC and one model.

    ``vision-stub`` runs the same pipeline with deterministic local stand-ins,
    so the review, fact and drafting steps can be exercised without a provider.
    Like ``stub`` it is confined to the stub environments.
    """
    settings = get_settings()
    if settings.extraction_provider == "vision-stub":
        if settings.environment not in STUB_EXTRACTION_ENVIRONMENTS:
            raise ServiceMisconfiguredError(
                f"EXTRACTION_PROVIDER=vision-stub is not permitted in environment "
                f"'{settings.environment}'. It returns canned candidate fields and is "
                f"limited to {sorted(STUB_EXTRACTION_ENVIRONMENTS)}."
            )
        from src.modules.document.application.v1_pipeline import V1DocumentPipeline
        from src.modules.document.infrastructure.rasterizer_pypdfium import PypdfiumRasterizer
        from src.modules.document.infrastructure.vision_stub_adapter import VisionStubAdapter

        stand_in = VisionStubAdapter()
        return V1DocumentPipeline(
            rasterizer=PypdfiumRasterizer(dpi=settings.raster_dpi),
            ocr=stand_in,
            classifier=stand_in,
            extractor=stand_in,
            classification_confidence_threshold=settings.confidence_threshold,
        )
    if settings.extraction_provider != "vision-gemini":
        raise ServiceMisconfiguredError("V1 processing requires EXTRACTION_PROVIDER=vision-gemini.")
    if not settings.gemini_api_key:
        raise ServiceMisconfiguredError("GEMINI_API_KEY is required for V1 document processing.")

    from google import genai
    from google.cloud import vision

    from src.modules.document.application.v1_pipeline import V1DocumentPipeline
    from src.modules.document.infrastructure.gemini_adapter import GeminiExtractionAdapter
    from src.modules.document.infrastructure.rasterizer_pypdfium import PypdfiumRasterizer
    from src.modules.document.infrastructure.vision_adapter import GoogleVisionOcrAdapter

    gemini = GeminiExtractionAdapter(
        client=genai.Client(api_key=settings.gemini_api_key),
        classify_model=settings.gemini_classify_model,
        extract_model=settings.gemini_extract_model,
    )
    return V1DocumentPipeline(
        rasterizer=PypdfiumRasterizer(dpi=settings.raster_dpi),
        ocr=GoogleVisionOcrAdapter(client=vision.ImageAnnotatorClient()),
        classifier=gemini,
        extractor=gemini,
        classification_confidence_threshold=settings.confidence_threshold,
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
            raise ServiceMisconfiguredError(
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
        raise ServiceMisconfiguredError(
            f"Unknown EXTRACTION_PROVIDER '{settings.extraction_provider}'. Valid: gemini, stub."
        )
    if not settings.gemini_api_key:
        raise ServiceMisconfiguredError(
            "GEMINI_API_KEY is required when EXTRACTION_PROVIDER=gemini."
        )

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

    from src.modules.matter_agent.jobs import RUN_TURN_JOB_TYPE, run_turn_job

    async def agent_turn_handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        outcome = await run_turn_job(session, message.payload)
        if outcome in {"completed", "unknown-job"}:
            return MessageResult.DONE
        if outcome == "retry":
            return MessageResult.RETRY
        # A failed turn is a finished job with a recorded failure, not a
        # message to redeliver: replaying it would answer the user twice.
        return MessageResult.DONE

    dispatcher.register_job(RUN_TURN_JOB_TYPE, agent_turn_handler)

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
