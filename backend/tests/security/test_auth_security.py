"""Security isolation tests — cross-org and non-member existence hiding.

Verified without a live DB using in-memory fakes.
"""

from __future__ import annotations

import pytest

from src.modules.auth.domain.errors import CapabilityDeniedError, NotFoundError
from src.modules.auth.domain.models import MatterMembershipRole, Role

# Reuse fakes from test_auth_service
from src.modules.auth.tests.test_auth_service import (
    make_ctx,
    make_service,
)
from src.platform.request_context import MatterMembershipCtx


class TestSecurityIsolation:
    @pytest.mark.asyncio
    async def test_non_member_matter_returns_404_not_403(self):
        """The backend must 404, not 403, for non-member matters (security-model.md §5)."""
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER, matter_memberships=frozenset())
        # Even an approver (who can draft.approve) gets 404 on a non-member matter
        with pytest.raises(NotFoundError):
            await svc.authorize(ctx, "draft.approve", matter_id="secret-matter")

    @pytest.mark.asyncio
    async def test_member_no_capability_returns_403_not_404(self):
        """Member who lacks the capability gets 403 (not 404)."""
        matter_ctx = frozenset(
            [MatterMembershipCtx(matter_id="m1", role=MatterMembershipRole.ASSIGNEE)]
        )
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER, matter_memberships=matter_ctx)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve", matter_id="m1")

    @pytest.mark.asyncio
    async def test_reviewer_cannot_manage_roles(self):
        """A reviewer must never be able to escalate privileges."""
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "user.role.set")

    @pytest.mark.asyncio
    async def test_maintainer_is_not_legal_approver(self):
        """Maintainer (content governance) must not inherit legal approver capabilities."""
        svc = make_service()
        ctx = make_ctx(role=Role.MAINTAINER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_administrator_is_not_legal_approver(self):
        """Administrator has account management, NOT legal workflow approval."""
        svc = make_service()
        ctx = make_ctx(role=Role.ADMINISTRATOR)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")
