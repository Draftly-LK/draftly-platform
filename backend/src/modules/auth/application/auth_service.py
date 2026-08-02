"""auth_service — core application service.

Implements all eight methods from auth-service.md §5.  Imports no FastAPI,
no SQLAlchemy, and no Clerk SDK — all provider interaction is behind ports.

The service enforces every invariant from auth-service.md §6:
- Authentication is not authorisation
- External identity is stable (issuer, subject key)
- Role is server-derived, never client-supplied
- Organisation and membership are server-derived
- Permission changes are audited
- Cross-matter and cross-organisation access is denied
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import structlog

from src.modules.auth.domain.errors import (
    AccountPendingError,
    AccountSuspendedError,
    AdminLockoutError,
    CapabilityDeniedError,
    MembershipNotFoundError,
    NotFoundError,
    OrganisationNotFoundError,
    OrganisationSuspendedError,
    PracticeStatusError,
    StepUpRequiredError,
)
from src.modules.auth.domain.models import (
    AccountStatus,
    MatterMembership,
    MatterMembershipRole,
    OrgRole,
    OrgStatus,
    Role,
    User,
    UserIdentity,
)
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.auth.ports import (
    AuditEventInput,
    AuditPort,
    IdentityPort,
    InvitationRepository,
    MatterMembershipRepository,
    OrganisationMembershipRepository,
    OrganisationRepository,
    UserIdentityRepository,
    UserRepository,
)
from src.platform.config import get_settings
from src.platform.request_context import MatterMembershipCtx, RequestContext

log = structlog.get_logger(__name__)


class AuthService:
    """Core auth application service — no FastAPI, SQLAlchemy, or Clerk imports."""

    def __init__(
        self,
        *,
        identity_port: IdentityPort,
        user_identity_repo: UserIdentityRepository,
        user_repo: UserRepository,
        org_repo: OrganisationRepository,
        org_membership_repo: OrganisationMembershipRepository,
        matter_membership_repo: MatterMembershipRepository,
        invitation_repo: InvitationRepository,
        audit_port: AuditPort,
    ) -> None:
        self._identity = identity_port
        self._user_identities = user_identity_repo
        self._users = user_repo
        self._orgs = org_repo
        self._org_memberships = org_membership_repo
        self._matter_memberships = matter_membership_repo
        self._invitations = invitation_repo
        self._audit = audit_port

    # ── build_request_context ────────────────────────────────────────────────

    async def build_request_context(
        self,
        token: str,
        requested_org_id: str,
        correlation_id: str = "",
    ) -> RequestContext:
        """Validate the token and assemble a server-authoritative RequestContext.

        Called by api/deps.py on every authenticated request.
        The browser never supplies role, membership, or matter access.
        """
        # 1. Validate the token via IdentityPort
        claims = await self._identity.validate_token(token)

        # 2. Resolve (issuer, subject) → UserIdentity
        identity = await self._user_identities.find_by_subject(claims.issuer, claims.subject)
        if identity is None:
            # Unknown identity — provision as pending; return minimal context
            raise AccountPendingError("Identity not yet linked to a Draftly account.")

        # 3. Load User and check account status
        user = await self._users.get(identity.user_id)
        if user is None:
            raise AccountPendingError("User record not found.")
        if user.account_status == AccountStatus.SUSPENDED:
            raise AccountSuspendedError()
        if user.account_status == AccountStatus.PENDING:
            raise AccountPendingError()
        if user.role is None:
            raise AccountPendingError("User has no assigned role.")

        # 4. Verify organisation membership
        org = await self._orgs.get(requested_org_id)
        if org is None:
            raise OrganisationNotFoundError()
        if org.status == OrgStatus.SUSPENDED or org.status == OrgStatus.CLOSED:
            raise OrganisationSuspendedError()

        org_membership = await self._org_memberships.find(requested_org_id, identity.user_id)
        if org_membership is None:
            # Non-member: treat the organisation as not found (existence hiding)
            raise OrganisationNotFoundError()

        # 5. Load matter memberships for this org
        matter_memberships = await self._matter_memberships.list_for_user(
            requested_org_id, identity.user_id
        )
        membership_ctx = frozenset(
            MatterMembershipCtx(matter_id=m.matter_id, role=m.role)
            for m in matter_memberships
        )

        return RequestContext(
            actor_id=identity.user_id,
            organisation_id=requested_org_id,
            account_role=user.role,
            organisation_role=org_membership.org_role,
            matter_memberships=membership_ctx,
            correlation_id=correlation_id,
        )

    # ── get_current_user ─────────────────────────────────────────────────────

    async def get_current_user(self, ctx: RequestContext) -> User:
        """Return the actor's own User record.

        Backs GET /api/v1/me — mirrors frontend User shape
        (id, displayName, role, notaryRegistration, jurisdiction).
        """
        user = await self._users.get(ctx.actor_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    # ── provision_identity ───────────────────────────────────────────────────

    async def provision_identity(
        self,
        token: str,
        org_id: str,
        correlation_id: str = "",
    ) -> User:
        """Called after IdentityPort has validated the token.

        Creates a UserIdentity + pending User. A valid invitation activates the
        user and applies only the role and memberships on that invitation.
        The browser cannot approve its own account or select a role.
        """
        claims = await self._identity.validate_token(token)

        # Idempotent: if already linked, return the existing user
        existing_identity = await self._user_identities.find_by_subject(
            claims.issuer, claims.subject
        )
        if existing_identity:
            user = await self._users.get(existing_identity.user_id)
            if user:
                return user

        # Create a pending User
        user_id = f"usr_{uuid.uuid4().hex}"
        user = User(
            id=user_id,
            display_name=claims.verified_email or claims.subject,
            account_status=AccountStatus.PENDING,
            role=None,
            notary_registration=None,
            jurisdiction=None,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        user = await self._users.create(user)

        # Link the external identity
        identity = UserIdentity(
            user_id=user_id,
            provider=claims.provider,
            issuer=claims.issuer,
            subject=claims.subject,
            verified_email=claims.verified_email,
            linked_at=datetime.now(tz=timezone.utc),
        )
        await self._user_identities.create(identity)

        # Check for a valid invitation — only the invitation activates the account
        if claims.verified_email:
            invitation = await self._invitations.find_active(org_id, claims.verified_email)
            if invitation and not invitation.is_expired and not invitation.is_accepted:
                user.account_status = AccountStatus.ACTIVE
                user.role = invitation.assigned_role
                user = await self._users.update(user)
                await self._invitations.mark_accepted(invitation.id)

                await self._audit.record(
                    AuditEventInput(
                        organisation_id=org_id,
                        action="user.activated",
                        target_type="permission",
                        target_id=user_id,
                        reason="Invitation accepted",
                        correlation_id=correlation_id,
                    )
                )
            else:
                # No valid invitation — stays pending
                await self._audit.record(
                    AuditEventInput(
                        organisation_id=org_id,
                        action="user.provisioned_pending",
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
        """Enforce capability + org + matter membership.

        Raises:
        - CapabilityDeniedError (403) if the role does not grant the capability
          AND the caller already knows the matter exists (is a member).
        - NotFoundError (404) if matter_id is provided and the actor is not a
          member — existence hiding (auth-service.md §6, security-model.md §5).
        """
        # 1. Role → capability check
        if not is_capability_granted(ctx.account_role, capability):
            if matter_id and not ctx.has_matter_membership(matter_id):
                # Non-member cannot learn that the matter exists
                raise NotFoundError()
            raise CapabilityDeniedError(
                f"Capability '{capability}' is not granted to role '{ctx.account_role}'.",
                capability=capability,
            )

        # 2. Matter membership (if matter-scoped)
        if matter_id is not None and not ctx.has_matter_membership(matter_id):
            # 404-not-403: non-member cannot infer matter existence
            raise NotFoundError()

    # ── assign_membership ────────────────────────────────────────────────────

    async def assign_membership(
        self,
        ctx: RequestContext,
        matter_id: str,
        user_id: str,
        role: MatterMembershipRole,
    ) -> MatterMembership:
        """Administrator-only. Audited as a permission change."""
        await self.authorize(ctx, "matter.membership.assign")

        existing = await self._matter_memberships.find(
            ctx.organisation_id, matter_id, user_id
        )
        if existing:
            before = existing.role.value
            updated = MatterMembership(
                organisation_id=ctx.organisation_id,
                matter_id=matter_id,
                user_id=user_id,
                role=role,
                assigned_at=existing.assigned_at,
            )
            result = await self._matter_memberships.update(updated)
        else:
            before = None
            new_membership = MatterMembership(
                organisation_id=ctx.organisation_id,
                matter_id=matter_id,
                user_id=user_id,
                role=role,
                assigned_at=datetime.now(tz=timezone.utc),
            )
            result = await self._matter_memberships.create(new_membership)

        await self._audit.record(
            AuditEventInput(
                organisation_id=ctx.organisation_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="matter.membership.assigned",
                target_type="permission",
                target_id=user_id,
                before_ref=before,
                after_ref=role.value,
                correlation_id=ctx.correlation_id,
            )
        )
        return result

    # ── set_user_role ────────────────────────────────────────────────────────

    async def set_user_role(
        self,
        ctx: RequestContext,
        user_id: str,
        new_role: Role,
    ) -> User:
        """Administrator-only. Role changes are audited. Admin lockout guard active."""
        await self.authorize(ctx, "user.role.set")

        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        before_role = user.role

        # Admin lockout guard: if changing from administrator, check remaining admins
        if before_role == Role.ADMINISTRATOR and new_role != Role.ADMINISTRATOR:
            # Count remaining admins in this org (including the actor)
            # If actor is the only admin they cannot demote themselves
            org_membership = await self._org_memberships.find(
                ctx.organisation_id, user_id
            )
            if org_membership and org_membership.org_role == OrgRole.OWNER:
                owner_count = await self._org_memberships.count_owners(ctx.organisation_id)
                if owner_count <= 1:
                    raise AdminLockoutError(
                        "Cannot change role: this user is the only organisation owner."
                    )

        user.role = new_role
        updated_user = await self._users.update(user)

        await self._audit.record(
            AuditEventInput(
                organisation_id=ctx.organisation_id,
                actor=ctx.actor_id,
                action="user.role.changed",
                target_type="permission",
                target_id=user_id,
                before_ref=before_role.value if before_role else None,
                after_ref=new_role.value,
                reason="Role changed by administrator",
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
        """Assert that the actor holds a current practice certificate.

        Required by: instrument.attest, draft.approve, particular.verify,
        finding.waive, step.override, deadline.confirm (security-model.md §3.3).
        """
        user = await self._users.get(ctx.actor_id)
        if user is None or not user.notary_registration:
            raise PracticeStatusError(
                "A notary registration is required for this action."
            )

        # Certificate currency check — simplified for V0; the obligations_service
        # owns the annual certificate obligation (obligations-service.md §7.1).
        # TODO(obligations-service): replace with obligations_service check
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

        V0 checks that the Clerk session auth_time is within the configured
        threshold. MFA or passkeys can be added behind the same check later.
        """
        settings = get_settings()
        if token is None:
            raise StepUpRequiredError(
                f"Step-up authentication is required for '{action}'."
            )

        try:
            claims = await self._identity.validate_token(token)
        except Exception:
            raise StepUpRequiredError(
                f"Step-up authentication is required for '{action}'."
            )

        auth_time = claims.auth_time
        if auth_time is None:
            raise StepUpRequiredError(
                f"Session age cannot be verified for '{action}'."
            )

        age_seconds = int(time.time()) - auth_time
        if age_seconds > settings.step_up_max_age_seconds:
            raise StepUpRequiredError(
                f"Session is too old for '{action}'. Please re-authenticate."
            )
