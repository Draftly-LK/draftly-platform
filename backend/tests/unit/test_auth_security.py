"""Security tests for capability enforcement (single-user model)."""

from __future__ import annotations

import pytest

from src.modules.auth.domain.errors import CapabilityDeniedError
from src.modules.auth.domain.models import Role
from tests.unit.test_auth_service import make_ctx, make_service


class TestSecurityCapabilities:
    @pytest.mark.asyncio
    async def test_approver_can_use_legal_capabilities_without_matter_membership(self):
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER)
        await svc.authorize(ctx, "draft.approve", matter_id="secret-matter")

    @pytest.mark.asyncio
    async def test_reviewer_denied_approve_on_matter(self):
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve", matter_id="m1")

    @pytest.mark.asyncio
    async def test_reviewer_cannot_manage_roles(self):
        svc = make_service()
        ctx = make_ctx(role=Role.REVIEWER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "user.role.set")

    @pytest.mark.asyncio
    async def test_maintainer_is_not_legal_approver(self):
        svc = make_service()
        ctx = make_ctx(role=Role.MAINTAINER)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_administrator_is_not_legal_approver(self):
        svc = make_service()
        ctx = make_ctx(role=Role.ADMINISTRATOR)
        with pytest.raises(CapabilityDeniedError):
            await svc.authorize(ctx, "draft.approve")

    @pytest.mark.asyncio
    async def test_approver_is_solo_admin_for_billing(self):
        svc = make_service()
        ctx = make_ctx(role=Role.APPROVER)
        await svc.authorize(ctx, "billing.manage")
