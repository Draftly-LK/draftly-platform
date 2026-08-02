"""Unit tests for the capability policy map.

These tests run with no DB, no Clerk, no FastAPI. They verify the exact
grants from security-model.md §3.2 and the negative cases that are
release-gating invariants.
"""

from __future__ import annotations

import pytest

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import is_capability_granted


class TestReviewerCapabilities:
    def test_reviewer_can_verify_particular(self):
        assert is_capability_granted(Role.REVIEWER, "particular.verify")

    def test_reviewer_can_create_draft(self):
        assert is_capability_granted(Role.REVIEWER, "draft.create")

    def test_reviewer_can_upload_document(self):
        assert is_capability_granted(Role.REVIEWER, "document.upload")

    def test_reviewer_cannot_approve_draft(self):
        """Security invariant: reviewer must not approve final drafts."""
        assert not is_capability_granted(Role.REVIEWER, "draft.approve")

    def test_reviewer_cannot_export(self):
        assert not is_capability_granted(Role.REVIEWER, "export.create")

    def test_reviewer_cannot_set_user_role(self):
        assert not is_capability_granted(Role.REVIEWER, "user.role.set")

    def test_reviewer_cannot_manage_billing(self):
        assert not is_capability_granted(Role.REVIEWER, "billing.manage")


class TestApproverCapabilities:
    def test_approver_can_approve_draft(self):
        assert is_capability_granted(Role.APPROVER, "draft.approve")

    def test_approver_can_export(self):
        assert is_capability_granted(Role.APPROVER, "export.create")

    def test_approver_can_waive_finding(self):
        assert is_capability_granted(Role.APPROVER, "finding.waive")

    def test_approver_cannot_manage_billing(self):
        assert not is_capability_granted(Role.APPROVER, "billing.manage")

    def test_approver_cannot_set_user_role(self):
        assert not is_capability_granted(Role.APPROVER, "user.role.set")


class TestMaintainerCapabilities:
    def test_maintainer_can_author_content(self):
        assert is_capability_granted(Role.MAINTAINER, "content.author")

    def test_maintainer_can_approve_corpus(self):
        assert is_capability_granted(Role.MAINTAINER, "corpus.approve")

    def test_maintainer_cannot_approve_draft(self):
        """Maintainer is for content governance only — not legal workflow."""
        assert not is_capability_granted(Role.MAINTAINER, "draft.approve")

    def test_maintainer_cannot_create_matter(self):
        assert not is_capability_granted(Role.MAINTAINER, "matter.create")

    def test_maintainer_cannot_set_user_role(self):
        assert not is_capability_granted(Role.MAINTAINER, "user.role.set")


class TestAdministratorCapabilities:
    def test_administrator_can_set_user_role(self):
        assert is_capability_granted(Role.ADMINISTRATOR, "user.role.set")

    def test_administrator_can_assign_membership(self):
        assert is_capability_granted(Role.ADMINISTRATOR, "matter.membership.assign")

    def test_administrator_can_manage_billing(self):
        assert is_capability_granted(Role.ADMINISTRATOR, "billing.manage")

    def test_administrator_cannot_approve_draft(self):
        """Administrator is not a legal approver — separate from Approver role."""
        assert not is_capability_granted(Role.ADMINISTRATOR, "draft.approve")


class TestInvalidCapability:
    def test_unknown_capability_is_denied_for_all_roles(self):
        for role in Role:
            assert not is_capability_granted(role, "made_up.capability")
