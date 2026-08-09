"""auth_service — core application service.

Implements auth flows for single-user Gmail accounts. Imports no FastAPI,
no SQLAlchemy, and no Clerk SDK — all provider interaction is behind ports.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import structlog

from src.modules.auth.domain.errors import (
    AccountPendingError,
    AccountSuspendedError,
    CapabilityDeniedError,
    EmailRequiredError,
    NotFoundError,
    PracticeStatusError,
    StepUpRequiredError,
)
from src.modules.auth.domain.models import AccountStatus, Role, User, UserIdentity
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.auth.ports import (
    AuditEventInput,
    AuditPort,
    IdentityPort,
    UserIdentityRepository,
    UserRepository,
)
from src.platform.config import get_settings
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)


class AuthService:
    """Core auth application service — no FastAPI, SQLAlchemy, or Clerk imports."""

    def __init__(
        self,
        *,
        identity_port: IdentityPort,
        user_identity_repo: UserIdentityRepository,
        user_repo: UserRepository,
        audit_port: AuditPort,
    ) -> None:
        self._identity = identity_port
        self._user_identities = user_identity_repo
        self._users = user_repo
        self._audit = audit_port

    # ── build_request_context ────────────────────────────────────────────────

    async def build_request_context(
        self,
        token: str,
        correlation_id: str = "",
    ) -> RequestContext:
        """Validate the token and assemble a server-authoritative RequestContext."""
        claims = await self._identity.validate_token(token)

        identity = await self._user_identities.find_by_subject(claims.issuer, claims.subject)
        if identity is None:
            raise AccountPendingError("Identity not yet linked to a Draftly account.")

        user = await self._users.get(identity.user_id)
        if user is None:
            raise AccountPendingError("User record not found.")
        if user.account_status == AccountStatus.SUSPENDED:
            raise AccountSuspendedError()
        if user.account_status == AccountStatus.PENDING:
            raise AccountPendingError()
        if user.role is None:
            raise AccountPendingError("User has no assigned role.")

        return RequestContext(
            actor_id=identity.user_id,
            account_role=user.role,
            correlation_id=correlation_id,
        )

    # ── get_current_user ─────────────────────────────────────────────────────

    async def get_current_user(self, ctx: RequestContext) -> User:
        """Return the actor's own User record."""
        user = await self._users.get(ctx.actor_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    # ── provision_identity ───────────────────────────────────────────────────

    async def provision_identity(
        self,
        token: str,
        correlation_id: str = "",
    ) -> User:
        """Link Google identity to a user — auto-active APPROVER on first login."""
        claims = await self._identity.validate_token(token)

        if not claims.verified_email:
            raise EmailRequiredError()

        existing_identity = await self._user_identities.find_by_subject(
            claims.issuer, claims.subject
        )
        if existing_identity:
            user = await self._users.get(existing_identity.user_id)
            if user:
                return user
            raise AccountPendingError("User record not found for linked identity.")

        identity_by_email = await self._user_identities.find_by_verified_email(
            claims.verified_email
        )
        if identity_by_email:
            user_id = identity_by_email.user_id
            identity = UserIdentity(
                user_id=user_id,
                provider=claims.provider,
                issuer=claims.issuer,
                subject=claims.subject,
                verified_email=claims.verified_email,
                linked_at=datetime.now(tz=UTC),
            )
            await self._user_identities.create(identity)
            user = await self._users.get(user_id)
            if user is None:
                raise NotFoundError("User not found.")
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    action="user.identity.linked",
                    target_type="permission",
                    target_id=user_id,
                    correlation_id=correlation_id,
                )
            )
            return user

        user_id = f"usr_{uuid.uuid4().hex}"
        now = datetime.now(tz=UTC)
        user = User(
            id=user_id,
            display_name=claims.verified_email,
            account_status=AccountStatus.ACTIVE,
            role=Role.APPROVER,
            notary_registration=None,
            jurisdiction=None,
            created_at=now,
            updated_at=now,
        )
        user = await self._users.create(user)

        identity = UserIdentity(
            user_id=user_id,
            provider=claims.provider,
            issuer=claims.issuer,
            subject=claims.subject,
            verified_email=claims.verified_email,
            linked_at=now,
        )
        await self._user_identities.create(identity)

        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                action="user.provisioned",
                target_type="permission",
                target_id=user_id,
                correlation_id=correlation_id,
            )
        )
        return user

    # ── authorize ────────────────────────────────────────────────────────────

    async def authorize(
        self,
        ctx: RequestContext,
        capability: str,
        matter_id: str | None = None,
    ) -> None:
        """Enforce role → capability. Matter ownership checks belong in matter_service."""
        _ = matter_id
        if not is_capability_granted(ctx.account_role, capability):
            raise CapabilityDeniedError(
                f"Capability '{capability}' is not granted to role '{ctx.account_role}'.",
                capability=capability,
            )

    # ── set_user_role ────────────────────────────────────────────────────────

    async def set_user_role(
        self,
        ctx: RequestContext,
        user_id: str,
        new_role: Role,
    ) -> User:
        """Change account role (capability-gated). Role changes are audited."""
        await self.authorize(ctx, "user.role.set")

        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        before_role = user.role
        user.role = new_role
        updated_user = await self._users.update(user)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                actor=ctx.actor_id,
                action="user.role.changed",
                target_type="permission",
                target_id=user_id,
                before_ref=before_role.value if before_role else None,
                after_ref=new_role.value,
                reason="Role changed",
                correlation_id=ctx.correlation_id,
            )
        )
        return updated_user

    # ── require_practising_notary ─────────────────────────────────────────────

    async def require_practising_notary(
        self,
        ctx: RequestContext,
        matter_id: str | None = None,
    ) -> None:
        """Assert that the actor holds a current practice certificate."""
        user = await self._users.get(ctx.actor_id)
        if user is None or not user.notary_registration:
            raise PracticeStatusError("A notary registration is required for this action.")

        now = datetime.now(tz=UTC)
        if user.certificate_valid_until is None or user.certificate_valid_until <= now:
            raise PracticeStatusError("A current notary practice certificate is required.")

        if matter_id is not None:
            if not user.jurisdiction:
                raise PracticeStatusError(
                    "Jurisdiction must be set for matter-scoped notary actions."
                )
            # TODO(api): enforce matter jurisdiction match via matter_service when available.

        log.debug(
            "practising_notary_check",
            actor=ctx.actor_id,
            registration=user.notary_registration,
        )

    # ── require_step_up ──────────────────────────────────────────────────────

    async def require_step_up(
        self,
        ctx: RequestContext,
        action: str,
        token: str | None = None,
    ) -> None:
        """Enforce step-up authentication for legally significant actions.

        Bind the token to the current actor before reading Settings, so unit
        tests (and early auth failures) never need database env vars loaded.
        """
        if token is None:
            raise StepUpRequiredError(f"Step-up authentication is required for '{action}'.")

        try:
            claims = await self._identity.validate_token(token)
        except Exception:
            raise StepUpRequiredError(f"Step-up authentication is required for '{action}'.")

        identity = await self._user_identities.find_by_subject(claims.issuer, claims.subject)
        if identity is None or identity.user_id != ctx.actor_id:
            raise StepUpRequiredError(f"Step-up authentication is required for '{action}'.")

        auth_time = claims.auth_time
        if auth_time is None:
            raise StepUpRequiredError(f"Session age cannot be verified for '{action}'.")

        settings = get_settings()
        age_seconds = int(time.time()) - auth_time
        if age_seconds > settings.step_up_max_age_seconds:
            raise StepUpRequiredError(f"Session is too old for '{action}'. Please re-authenticate.")
