"""Session provisioning, transcript reads, and message append.

Matter ownership is resolved here through ``MatterAccessPort`` and a foreign or
missing matter produces the same ``AgentSessionNotFoundError`` — a 404 that is
byte-identical to a genuinely absent session (``security-model.md`` §5).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.matter.contracts import MatterScopePort
from src.modules.matter_agent.application.actions import (
    ACTION_SPECS,
    ActionExecutor,
    AuthorizationPort,
    UnknownActionKindError,
    build_pending_action,
    guard_target_version,
)
from src.modules.matter_agent.domain.errors import (
    AgentDisabledError,
    AgentRetryUnavailableError,
    AgentSessionNotFoundError,
    PendingActionExpiredError,
    PendingActionNotFoundError,
    PendingActionStaleError,
)
from src.modules.matter_agent.domain.models import (
    AgentConversation,
    AgentMessage,
    AgentSession,
    JobState,
    MessageRole,
    PendingAction,
    PendingActionState,
    SessionState,
)
from src.modules.matter_agent.ports import (
    AgentEventPort,
    AgentSessionRepository,
    ConversationPort,
    MessagePage,
    PendingActionRepository,
)
from src.platform import ids
from src.platform.errors import DraftlyError, PreconditionFailedError
from src.platform.idempotency import fingerprint
from src.platform.pagination import Cursor
from src.platform.request_context import RequestContext


class MatterAccessPort(Protocol):
    """Minimal ownership question, answered by ``matter_service``."""

    async def owns_matter(self, *, user_id: str, matter_id: str) -> bool: ...


class TargetVersionPort(Protocol):
    """Current optimistic version of whatever a pending action points at.

    Kept as a narrow port so a card can target a fact, a checklist item or a
    draft without this service knowing any of those aggregates.
    """

    async def current_version(self, *, matter_id: str, target_ref: str) -> int: ...


@dataclass(frozen=True)
class AgentJob:
    """A queued or finished turn, as the API reports it."""

    job_id: str
    state: JobState
    tool_call_count: int = 0
    failure_class: str | None = None


@dataclass(frozen=True)
class RetrySource:
    job: AgentJob
    message: AgentMessage
    has_tool_calls: bool
    is_latest_message: bool
    existing_retry: AgentJob | None = None


class AgentJobPort(Protocol):
    """Job rows plus the outbox enqueue, both inside the caller's transaction."""

    async def create(
        self,
        *,
        session_id: str,
        user_id: str,
        matter_id: str,
        correlation_id: str,
        retry_of_job_id: str | None = None,
    ) -> AgentJob: ...

    async def enqueue(
        self, *, job_id: str, session_id: str, message_id: str, user_id: str
    ) -> None: ...

    async def get(self, *, job_id: str, user_id: str) -> AgentJob | None: ...

    async def latest(
        self, *, session_id: str, user_id: str, conversation_id: str | None
    ) -> AgentJob | None: ...

    async def retry_source(
        self, *, job_id: str, user_id: str, matter_id: str
    ) -> RetrySource | None: ...


@dataclass(frozen=True)
class AgentSettings:
    """Deployment switches (``matter-agent-service.md`` §Configuration)."""

    enabled: bool = False
    model: str = "gemini-flash-latest"
    prompt_version: str = "v1"
    max_tool_calls: int = 8
    turn_timeout_seconds: int = 120


class AgentService:
    """Reads and writes the matter session and its active conversation."""

    def __init__(
        self,
        *,
        sessions: AgentSessionRepository,
        conversation: ConversationPort,
        matters: MatterAccessPort,
        audit: AuditPort,
        settings: AgentSettings,
        jobs: AgentJobPort,
        actions: PendingActionRepository,
        targets: TargetVersionPort,
        events: AgentEventPort | None = None,
        authorizer: AuthorizationPort | None = None,
        action_executor: ActionExecutor | None = None,
        scopes: MatterScopePort | None = None,
    ) -> None:
        self._sessions = sessions
        self._conversation = conversation
        self._matters = matters
        self._audit = audit
        self._settings = settings
        self._jobs = jobs
        self._actions = actions
        self._targets = targets
        self._events = events
        self._authorizer = authorizer
        self._action_executor = action_executor
        self._scopes = scopes

    async def get_or_create_session(self, ctx: RequestContext, matter_id: str) -> AgentSession:
        """Return the matter's session, provisioning it lazily on first use."""
        if not self._settings.enabled:
            raise AgentDisabledError()
        await self._require_matter(ctx, matter_id)

        existing = await self._sessions.find(user_id=ctx.actor_id, matter_id=matter_id)
        if existing is not None:
            if existing.active_conversation_id is None:
                return await self._sessions.start_conversation(existing)
            return existing

        now = datetime.now(tz=UTC)
        session = AgentSession(
            id=ids.new_id(ids.AGENT_SESSION),
            user_id=ctx.actor_id,
            matter_id=matter_id,
            model_version=self._settings.model,
            prompt_version=self._settings.prompt_version,
            state=SessionState.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        created = await self._sessions.create(session)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="agent.session-created",
                target_type="agent_session",
                target_id=created.id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._publish(
            "agent.session-created",
            ctx,
            matter_id,
            key=f"agent.session-created:{created.id}",
            data={"sessionId": created.id},
        )
        return created

    async def list_messages(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        limit: int,
        cursor: Cursor | None = None,
    ) -> MessagePage:
        """The authoritative transcript, read from Neon. Never from a provider."""
        session = await self.get_or_create_session(ctx, matter_id)
        return await self._conversation.page(
            session_id=session.id,
            conversation_id=session.active_conversation_id,
            limit=limit,
            cursor=cursor,
        )

    async def list_conversations(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[AgentConversation, ...]:
        session = await self.get_or_create_session(ctx, matter_id)
        return await self._sessions.list_conversations(session)

    async def start_conversation(self, ctx: RequestContext, matter_id: str) -> AgentConversation:
        """Archive the visible segment and begin a clean one without deleting audit history."""
        await self.lock(ctx, matter_id)
        session = await self.get_or_create_session(ctx, matter_id)
        updated = await self._sessions.start_conversation(session)
        conversations = await self._sessions.list_conversations(updated)
        created = next(item for item in conversations if item.id == updated.active_conversation_id)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="agent.conversation-started",
                target_type="agent_conversation",
                target_id=created.id,
                correlation_id=ctx.correlation_id,
            )
        )
        return created

    async def retry_turn(self, ctx: RequestContext, matter_id: str, job_id: str) -> AgentJob:
        """Retry a failed answer using its saved message, without replaying tools.

        The locked original job serializes competing retries. Existing attempts
        converge, and transcript content and the original failure stay intact.
        """
        session = await self.get_or_create_session(ctx, matter_id)
        source = await self._jobs.retry_source(
            job_id=job_id, user_id=ctx.actor_id, matter_id=matter_id
        )
        if source is None or source.message.session_id != session.id:
            raise AgentSessionNotFoundError()
        if source.existing_retry is not None:
            return source.existing_retry
        if (
            source.job.state is not JobState.FAILED
            or source.job.failure_class != "model_unavailable"
            or source.has_tool_calls
            or not source.is_latest_message
            or source.message.conversation_id != session.active_conversation_id
        ):
            raise AgentRetryUnavailableError()
        job = await self._jobs.create(
            session_id=session.id,
            user_id=ctx.actor_id,
            matter_id=matter_id,
            correlation_id=ctx.correlation_id,
            retry_of_job_id=job_id,
        )
        await self._jobs.enqueue(
            job_id=job.job_id,
            session_id=session.id,
            message_id=source.message.id,
            user_id=ctx.actor_id,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="agent.turn-retried",
                target_type="agent_job",
                target_id=job.job_id,
                correlation_id=ctx.correlation_id,
            )
        )
        return job

    async def append_user_message(
        self, ctx: RequestContext, matter_id: str, *, content: str, job_id: str
    ) -> AgentMessage:
        """Append the user's turn. Commits with its outbox event."""
        session = await self.get_or_create_session(ctx, matter_id)
        message = await self._conversation.append(
            session=session,
            role=MessageRole.USER,
            content=content,
            job_id=job_id,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="agent.message-appended",
                target_type="agent_message",
                target_id=message.id,
                correlation_id=ctx.correlation_id,
            )
        )
        return message

    async def start_turn(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        content: str,
    ) -> AgentJob:
        """Append the user's message and queue the turn.

        The message row, the job row and the outbox entry commit together, so a
        queued turn always has a message behind it and a rollback leaves
        neither. The request never waits on the model.
        """
        session = await self.get_or_create_session(ctx, matter_id)
        job = await self._jobs.create(
            session_id=session.id,
            user_id=ctx.actor_id,
            matter_id=matter_id,
            correlation_id=ctx.correlation_id,
        )
        message = await self._conversation.append(
            session=session,
            role=MessageRole.USER,
            content=content,
            job_id=job.job_id,
        )
        await self._jobs.enqueue(
            job_id=job.job_id,
            session_id=session.id,
            message_id=message.id,
            user_id=ctx.actor_id,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="agent.message-appended",
                target_type="agent_message",
                target_id=message.id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._publish(
            "agent.message-appended",
            ctx,
            matter_id,
            key=f"agent.message-appended:{message.id}",
            data={
                "sessionId": session.id,
                "messageId": message.id,
                "sequence": message.sequence,
                "role": message.role.value,
            },
        )
        return job

    async def latest_job(self, ctx: RequestContext, matter_id: str) -> AgentJob | None:
        session = await self.get_or_create_session(ctx, matter_id)
        return await self._jobs.latest(
            session_id=session.id,
            user_id=ctx.actor_id,
            conversation_id=session.active_conversation_id,
        )

    async def read_job(self, ctx: RequestContext, job_id: str) -> AgentJob:
        """A job owned by another user is absent, not forbidden."""
        job = await self._jobs.get(job_id=job_id, user_id=ctx.actor_id)
        if job is None:
            raise AgentSessionNotFoundError()
        return job

    async def lock(self, ctx: RequestContext, matter_id: str) -> None:
        await self._require_matter(ctx, matter_id)
        if self._scopes is not None:
            await self._scopes.lock(ctx, matter_id)

    async def read_action(
        self, ctx: RequestContext, matter_id: str, action_id: str
    ) -> PendingAction:
        await self.lock(ctx, matter_id)
        action = await self._actions.get(action_id=action_id, matter_id=matter_id)
        if action is None or action.user_id != ctx.actor_id:
            raise PendingActionNotFoundError()
        if action.state is PendingActionState.PROPOSED and not action.is_open(
            now=datetime.now(tz=UTC)
        ):
            action = replace(
                action, state=PendingActionState.EXPIRED, reason_code="pending_action_expired"
            )
            await self._actions.update(action)
            await self._action_audit(action, ctx, "expired")
        return action

    async def _authorize_action(self, action: PendingAction, ctx: RequestContext) -> None:
        try:
            spec = ACTION_SPECS.get(action.action_kind)
            if spec is None:
                raise UnknownActionKindError()
            if self._authorizer is not None:
                await self._authorizer.authorize(ctx, spec.capability, action.matter_id)
                if spec.requires_practising:
                    await self._authorizer.require_practising_notary(ctx, action.matter_id)
            if self._action_executor is not None:
                await self._action_executor.authorize(action, ctx)

        except DraftlyError as exc:
            await self._action_audit(replace(action, reason_code=exc.code), ctx, "denied")
            raise

    async def propose_action(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        session_id: str,
        kind: str,
        arguments: dict[str, object],
        target_ref: str,
        target_version: int,
    ) -> PendingAction:
        await self.lock(ctx, matter_id)
        action = build_pending_action(
            session_id=session_id,
            matter_id=matter_id,
            user_id=ctx.actor_id,
            kind=kind,
            arguments=arguments,
            target_ref=target_ref,
            target_version=target_version,
        )
        await self._authorize_action(action, ctx)
        if self._action_executor is None:
            raise UnknownActionKindError()
        current, pins = await self._action_executor.current(action, ctx)
        guard_target_version(action, current)
        if kind == "fact-accept" and pins.get("scopeToken") != arguments.get("expectedScopeToken"):
            raise PendingActionStaleError()
        action = replace(
            action, arguments={**arguments, "_pins": fingerprint(pins), "reviewed": pins}
        )
        await self._actions.create(action)
        await self._action_audit(action, ctx, "proposed")
        return action

    async def confirm_action(
        self, ctx: RequestContext, matter_id: str, *, action_id: str
    ) -> PendingAction:
        await self.lock(ctx, matter_id)
        action = await self.read_action(ctx, matter_id, action_id)
        # Re-authorize before ANY cached execution is returned.
        await self._authorize_action(action, ctx)
        if action.state in (PendingActionState.CONFIRMED, PendingActionState.EXECUTED):
            return action
        await self._require_confirmable(action, ctx)
        try:
            if self._action_executor is not None:
                current, pins = await self._action_executor.current(action, ctx)
                guard_target_version(action, current)
                if action.arguments.get("_pins") != fingerprint(pins):
                    raise PendingActionStaleError()
                async with self._actions.execution():
                    result = await self._action_executor.execute(action, ctx)
            else:
                current = await self._targets.current_version(
                    matter_id=matter_id, target_ref=action.target_ref
                )
                guard_target_version(action, current)
                result = {}
        except DraftlyError as exc:
            stale = isinstance(exc, (PreconditionFailedError, PendingActionStaleError))
            failed = replace(
                action,
                state=PendingActionState.STALE if stale else PendingActionState.FAILED,
                reason_code=exc.code,
            )
            await self._actions.update(failed)
            await self._action_audit(failed, ctx, "stale" if stale else "failed")
            raise
        confirmed = replace(
            action,
            state=PendingActionState.EXECUTED
            if self._action_executor
            else PendingActionState.CONFIRMED,
            confirmed_by=ctx.actor_id,
            confirmed_at=datetime.now(tz=UTC),
            result=result,
        )
        await self._actions.update(confirmed)
        await self._action_audit(confirmed, ctx, "confirmed")
        await self._publish(
            "agent.action-confirmed",
            ctx,
            matter_id,
            key=f"agent.action-confirmed:{action.id}",
            data={"actionId": action.id, "targetVersion": action.target_version},
        )
        return confirmed

    async def reject_action(
        self, ctx: RequestContext, matter_id: str, *, action_id: str, reason: str | None
    ) -> PendingAction:
        await self.lock(ctx, matter_id)
        action = await self.read_action(ctx, matter_id, action_id)
        await self._authorize_action(action, ctx)
        if action.state in (PendingActionState.DECLINED, PendingActionState.REJECTED):
            return action
        await self._require_confirmable(action, ctx)
        rejected = replace(
            action,
            state=PendingActionState.DECLINED,
            result={"declineReason": reason} if reason else {},
            reason_code="rejected_by_user",
            confirmed_by=ctx.actor_id,
            confirmed_at=datetime.now(tz=UTC),
        )
        await self._actions.update(rejected)
        # Free-form reasons remain in the command/proposal record, never audit.
        await self._action_audit(rejected, ctx, "rejected")
        await self._publish(
            "agent.action-rejected",
            ctx,
            matter_id,
            key=f"agent.action-rejected:{action.id}",
            data={"actionId": action.id, "reasonCode": "rejected_by_user"},
        )
        return rejected

    async def _require_confirmable(self, action: PendingAction, ctx: RequestContext) -> None:
        if action.is_open(now=datetime.now(tz=UTC)):
            return
        if action.state is PendingActionState.PROPOSED:
            expired = replace(
                action, state=PendingActionState.EXPIRED, reason_code="pending_action_expired"
            )
            await self._actions.update(expired)
            await self._action_audit(expired, ctx, "expired")
        raise PendingActionExpiredError()

    async def _action_audit(self, action: PendingAction, ctx: RequestContext, outcome: str) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=action.matter_id,
                actor=ctx.actor_id,
                action=f"agent.action-{outcome}",
                target_type="agent_pending_action",
                target_id=action.id,
                correlation_id=ctx.correlation_id,
                reason=action.reason_code,
            )
        )

    async def _publish(
        self,
        event_name: str,
        ctx: RequestContext,
        matter_id: str,
        *,
        key: str,
        data: dict[str, object],
    ) -> None:
        """Publish into the caller's transaction, or do nothing if unwired.

        Payloads carry identifiers and closed enums only; a consumer that needs
        the wording re-reads it from Neon (`events.md` §2).
        """
        if self._events is None:
            return
        await self._events.publish(
            event_name,
            user_id=ctx.actor_id,
            matter_id=matter_id,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
            idempotency_key=key,
            data=data,
        )

    async def _require_open_action(self, matter_id: str, action_id: str) -> PendingAction:
        action = await self._actions.get(action_id=action_id, matter_id=matter_id)
        if action is None:
            raise PendingActionNotFoundError()
        if not action.is_open(now=datetime.now(tz=UTC)):
            raise PendingActionExpiredError()
        return action

    async def _require_matter(self, ctx: RequestContext, matter_id: str) -> None:
        if not await self._matters.owns_matter(user_id=ctx.actor_id, matter_id=matter_id):
            raise AgentSessionNotFoundError()
