"""Unit tests for AuthService.authorize — no DB required.

These tests use in-memory fakes so they run instantly in CI.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from dataclasses import dataclass

from src.modules.auth.domain.errors import (
    AccountPendingError,
    CapabilityDeniedError,
    NotFoundError,
)
from src.modules.auth.domain.models import (
    AccountStatus,
    MatterMembership,
    MatterMembershipRole,
    OrgRole,
    Role,
    User,
)
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.ports import AuditEventInput
from src.platform.request_context import MatterMembershipCtx, RequestContext


# ── Fakes ─────────────────────────────────────────────────────────────────────


class FakeIdentityPort:
    async def validate_token(self, token: str):  # type: ignore[no-untyped-def]
        from src.modules.auth.ports import IdentityClaims
        return IdentityClaims(issuer="stub", subject=token, verified_email="t@t.com")


class FakeUserIdentityRepo:
    def __init__(self, identity=None):  # type: ignore[no-untyped-def]
        self._identity = identity

    async def find_by_subject(self, issuer, subject):  # type: ignore[no-untyped-def]
        return self._identity

    async def create(self, identity):  # type: ignore[no-untyped-def]
        return identity


class FakeUserRepo:
    def __init__(self, user=None):  # type: ignore[no-untyped-def]
        self._user = user

    async def get(self, user_id):  # type: ignore[no-untyped-def]
        return self._user

    async def get_by_email(self, email):  # type: ignore[no-untyped-def]
        return None

    async def create(self, user):  # type: ignore[no-untyped-def]
        return user

    async def update(self, user):  # type: ignore[no-untyped-def]
        return user


class FakeOrgRepo:
    def __init__(self, org=None):  # type: ignore[no-untyped-def]
        self._org = org

    async def get(self, org_id):  # type: ignore[no-untyped-def]
        return self._org


class FakeOrgMembershipRepo:
    def __init__(self, membership=None):  # type: ignore[no-untyped-def]
        self._membership = membership

    async def find(self, org_id, user_id):  # type: ignore[no-untyped-def]
        return self._membership

    async def create(self, m):  # type: ignore[no-untyped-def]
        return m

    async def count_owners(self, org_id):  # type: ignore[no-untyped-def]
        return 1


class FakeMatterMembershipRepo:
    def __init__(self, memberships=None):  # type: ignore[no-untyped-def]
        self._memberships = memberships or []
        self._created = []

    async def list_for_user(self, org_id, user_id):  # type: ignore[no-untyped-def]
        return self._memberships

    async def find(self, org_id, matter_id, user_id):  # type: ignore[no-untyped-def]
        for m in self._memberships:
            if m.matter_id == matter_id and m.user_id == user_id:
                return m
        return None

    async def create(self, m):  # type: ignore[no-untyped-def]
        self._created.append(m)
        return m

    async def update(self, m):  # type: ignore[no-untyped-def]
        return m


class FakeInvitationRepo:
    async def find_active(self, org_id, email):  # type: ignore[no-untyped-def]
        return None

    async def mark_accepted(self, invitation_id):  # type: ignore[no-untyped-def]
        pass


class FakeAuditPort:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


def make_ctx(
    role: Role = Role.REVIEWER,
    org_role: OrgRole = OrgRole.MEMBER,
    matter_memberships: frozenset = frozenset(),
) -> RequestContext:
    return RequestContext(
        actor_id="usr_test",
        organisation_id="org_test",
        account_role=role,
        organisation_role=org_role,
        matter_memberships=matter_memberships,
        correlation_id="corr_test",
    )


def make_service(**kwargs) -> AuthService:  # type: ignore[no-untyped-def]
    defaults = dict(
        identity_port=FakeIdentityPort(),
        user_identity_repo=FakeUserIdentityRepo(),
        user_repo=FakeUserRepo(),
        org_repo=FakeOrgRepo(),
        org_membership_repo=FakeOrgMembershipRepo(),
        matter_membership_repo=FakeMatterMembershipRepo(),
        invitation_repo=FakeInvitationRepo(),
        audit_port=FakeAuditPort(),
    )
    defaults.update(kwargs)
    return AuthService(**defaults)


# ── authorize tests ───────────────────────────────────────────────────────────


class TestAuthorize:
    @pytest.mark.asyncio
    async def test_reviewer_denied_approve_capability(self):
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_approver_granted_approve_capability(self):
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER)
        await svc.authorize(ctx, "draft.approve")  # must not raise

    @pytest.mark.asyncio
    async def test_non_member_matter_returns_404(self):
        """Non-member must get 404, not 403, to hide matter existence."""
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER, matter_memberships=frozenset())
        with pytest.raises(NotFoundError):
            await svc.authorize(ctx, "particular.verify", matter_id="matter-secret")

    @pytest.mark.asyncio
    async def test_member_matter_denied_capability_returns_403(self):
        """A member who lacks the capability gets 403, not 404."""
        matter_ctx = frozenset(
            [MatterMembershipCtx(matter_id="m1", role=MatterMembershipRole.ASSIGNEE)]
        )
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER, matter_memberships=matter_ctx)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve", matter_id="m1")

    @pytest.mark.asyncio
    async def test_member_matter_granted_capability_passes(self):
        matter_ctx = frozenset(
            [MatterMembershipCtx(matter_id="m1", role=MatterMembershipRole.ASSIGNEE)]
        )
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER, matter_memberships=matter_ctx)
        await svc.authorize(ctx, "particular.verify", matter_id="m1")


# ── assign_membership tests ───────────────────────────────────────────────────


class TestAssignMembership:
    @pytest.mark.asyncio
    async def test_assignment_is_audited(self):
        audit = FakeAuditPort()
        svc = make_service(audit_port=audit)
        ctx = make_ctx(role=Role.ADMINISTRATOR)
        await svc.assign_membership(ctx, "matter-1", "usr_target", MatterMembershipRole.ASSIGNEE)
        assert len(audit.events) == 1
        event = audit.events[0]
        assert event.action == "matter.membership.assigned"
        assert event.target_type == "permission"
        assert event.target_id == "usr_target"

    @pytest.mark.asyncio
    async def test_reviewer_cannot_assign_membership(self):
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.assign_membership(ctx, "m1", "usr2", MatterMembershipRole.ASSIGNEE)


# ── admin lockout guard ───────────────────────────────────────────────────────


class TestAdminLockout:
    @pytest.mark.asyncio
    async def test_last_owner_cannot_be_demoted(self):
        from src.modules.auth.domain.errors import AdminLockoutError
        from src.modules.auth.domain.models import OrganisationMembership

        owner_membership = OrganisationMembership(
            organisation_id="org_test",
            user_id="usr_test",
            org_role=OrgRole.OWNER,
            joined_at=datetime.now(tz=timezone.utc),
        )
        user = User(
            id="usr_test",
            display_name="Admin",
            account_status=AccountStatus.ACTIVE,
            role=Role.ADMINISTRATOR,
            notary_registration=None,
            jurisdiction=None,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        org_membership_repo = FakeOrgMembershipRepo(membership=owner_membership)
        org_membership_repo._owner_count = 1

        class SingleOwnerOrgRepo(FakeOrgMembershipRepo):
            async def count_owners(self, org_id):  # type: ignore[no-untyped-def]
                return 1

        svc = make_service(
            user_repo=FakeUserRepo(user=user),
            org_membership_repo=SingleOwnerOrgRepo(membership=owner_membership),
        )
        ctx = make_ctx(role=Role.ADMINISTRATOR)
        with pytest.raises(AdminLockoutError):
            await svc.set_user_role(ctx, "usr_test", Role.REVIEWER)
