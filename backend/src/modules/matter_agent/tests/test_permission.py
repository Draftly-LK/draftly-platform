"""The agent's effective permission is an intersection, never a union.

These cover invariants 6, 7 and 8 in `matter-agent-service.md`. They are pure
domain tests: no database, no provider, no request.
"""

from __future__ import annotations

import pytest

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import CAPABILITY_MAP, is_capability_granted
from src.modules.matter_agent.domain.allowlist import (
    ALLOWLISTED_CAPABILITIES,
    PROHIBITED_CAPABILITIES,
    TOOL_ALLOWLIST,
    ToolKind,
    tools_of_kind,
)
from src.modules.matter_agent.domain.permission import (
    DenialReason,
    authorize_tool,
    effective_capabilities,
    reachable_tools,
)

REVIEWER_CAPS = CAPABILITY_MAP[Role.REVIEWER]
APPROVER_CAPS = CAPABILITY_MAP[Role.APPROVER]

TRIAGE_CAPABILITIES = (
    "document.propose-link",
    "checklist.record-receipt",
    "checklist.suggest-item",
    "candidate.create",
    "candidate.update",
)

MATTER_ADMIN_CAPABILITIES = (
    "check.run",
    "note.create",
    "checklist.administer",
    "checklist.assign",
    "checklist.update-due-date",
    "checklist.request-collection",
)


class TestTheAllowlistIsClosed:
    def test_an_unknown_tool_is_refused_before_anything_else_is_checked(self) -> None:
        decision = authorize_tool(
            tool_name="delete_the_matter",
            user_capabilities=APPROVER_CAPS,
            matter_owned=True,
            is_practising_notary=True,
        )
        assert not decision
        assert decision.reason is DenialReason.TOOL_NOT_ALLOWLISTED

    @pytest.mark.parametrize("capability", sorted(PROHIBITED_CAPABILITIES))
    def test_no_tool_requires_a_prohibited_capability(self, capability: str) -> None:
        assert capability not in ALLOWLISTED_CAPABILITIES

    def test_holding_a_prohibited_capability_reaches_no_extra_tool(self) -> None:
        """An approver holds draft.approve. No tool exposes it, so it buys nothing."""
        assert "draft.approve" in APPROVER_CAPS
        assert "draft.approve" not in effective_capabilities(APPROVER_CAPS)

    def test_a_wildly_over_privileged_caller_still_only_reaches_the_allowlist(self) -> None:
        everything = frozenset(APPROVER_CAPS | PROHIBITED_CAPABILITIES | {"platform.administer"})
        assert effective_capabilities(everything) <= ALLOWLISTED_CAPABILITIES


class TestTheIntersectionHoldsInEveryDirection:
    def test_the_agent_cannot_exceed_the_user(self) -> None:
        """A user without check.run cannot obtain it by asking the agent."""
        without = frozenset(REVIEWER_CAPS) - {"check.run"}
        decision = authorize_tool(
            tool_name="run_checks", user_capabilities=without, matter_owned=True
        )
        assert not decision
        assert decision.reason is DenialReason.CAPABILITY_NOT_HELD
        assert decision.missing_capabilities == frozenset({"check.run"})

    def test_matter_ownership_is_checked_before_capability(self) -> None:
        decision = authorize_tool(
            tool_name="run_checks",
            user_capabilities=frozenset(),
            matter_owned=False,
        )
        assert decision.reason is DenialReason.MATTER_NOT_OWNED

    def test_no_tool_is_reachable_on_a_matter_the_user_does_not_own(self) -> None:
        assert (
            reachable_tools(
                user_capabilities=APPROVER_CAPS,
                matter_owned=False,
                is_practising_notary=True,
            )
            == frozenset()
        )

    def test_a_reviewer_driving_the_agent_gets_reviewer_powers(self) -> None:
        reviewer = reachable_tools(user_capabilities=REVIEWER_CAPS, matter_owned=True)
        approver = reachable_tools(
            user_capabilities=APPROVER_CAPS, matter_owned=True, is_practising_notary=True
        )
        assert reviewer < approver, "a reviewer must not reach everything an approver reaches"


class TestUmbrellaAndNarrowCapabilities:
    @pytest.mark.parametrize(
        "tool_name,narrow",
        [
            ("assign_checklist_item", "checklist.assign"),
            ("update_checklist_due_date", "checklist.update-due-date"),
            ("request_checklist_collection", "checklist.request-collection"),
            ("record_document_receipt", "checklist.record-receipt"),
            ("suggest_checklist_item", "checklist.suggest-item"),
        ],
    )
    def test_the_umbrella_alone_grants_nothing(self, tool_name: str, narrow: str) -> None:
        decision = authorize_tool(
            tool_name=tool_name,
            user_capabilities=frozenset({"checklist.administer"}),
            matter_owned=True,
        )
        assert not decision
        assert decision.missing_capabilities == frozenset({narrow})

    def test_the_narrow_key_alone_grants_nothing(self) -> None:
        decision = authorize_tool(
            tool_name="assign_checklist_item",
            user_capabilities=frozenset({"checklist.assign"}),
            matter_owned=True,
        )
        assert not decision
        assert decision.missing_capabilities == frozenset({"checklist.administer"})


class TestPractisingStatus:
    def test_candidate_approval_cannot_be_proposed_without_a_practice_certificate(self) -> None:
        decision = authorize_tool(
            tool_name="propose_candidate_approval",
            user_capabilities=APPROVER_CAPS,
            matter_owned=True,
            is_practising_notary=False,
        )
        assert not decision
        assert decision.reason is DenialReason.PRACTISING_STATUS_ABSENT

    def test_no_matter_administration_tool_requires_practising_status(self) -> None:
        """None of the six is territorial (security-model.md §3.3)."""
        for tool in tools_of_kind(ToolKind.WRITE):
            if tool.capabilities & set(MATTER_ADMIN_CAPABILITIES):
                assert not tool.requires_practising, tool.name


class TestTriageCapabilities:
    """The five document-triage keys must be reachable, granted, and audited."""

    @pytest.mark.parametrize("capability", TRIAGE_CAPABILITIES)
    def test_is_exposed_by_a_tool(self, capability: str) -> None:
        assert capability in ALLOWLISTED_CAPABILITIES

    @pytest.mark.parametrize("capability", TRIAGE_CAPABILITIES + MATTER_ADMIN_CAPABILITIES)
    def test_is_granted_to_reviewer_and_approver_only(self, capability: str) -> None:
        assert is_capability_granted(Role.REVIEWER, capability)
        assert is_capability_granted(Role.APPROVER, capability)
        assert not is_capability_granted(Role.MAINTAINER, capability)
        assert not is_capability_granted(Role.ADMINISTRATOR, capability)


class TestHumanOnlyActions:
    """Invariant 8: the agent never crosses these lines."""

    @pytest.mark.parametrize(
        "capability",
        [
            "draft.approve",
            "export.create",
            "instrument.attest",
            "register.certify-return",
            "finding.waive",
            "step.override",
            "deadline.confirm",
            "retention.hold",
            "retention.approve-destruction",
            "user.role.set",
            "billing.manage",
            "platform.administer",
        ],
    )
    def test_is_unreachable_even_for_a_practising_approver(self, capability: str) -> None:
        assert capability not in effective_capabilities(APPROVER_CAPS | {capability})

    def test_receipt_is_reachable_but_evidence_acceptance_is_not(self) -> None:
        """We received something is not a lawyer accepted it as legally sufficient."""
        assert "checklist.record-receipt" in ALLOWLISTED_CAPABILITIES
        assert "requirement.review" not in {
            capability for tool in tools_of_kind(ToolKind.WRITE) for capability in tool.capabilities
        }


class TestTheRegistryIsWellFormed:
    def test_every_write_tool_declares_at_least_one_capability(self) -> None:
        for tool in tools_of_kind(ToolKind.WRITE):
            assert tool.capabilities, tool.name

    def test_read_tools_need_no_capability_beyond_matter_ownership(self) -> None:
        for tool in tools_of_kind(ToolKind.READ):
            assert tool.capabilities == frozenset(), tool.name

    def test_tool_names_are_valid_function_calling_identifiers(self) -> None:
        for name in TOOL_ALLOWLIST:
            assert name.replace("_", "").isalnum(), name
            assert name.islower(), name

    def test_every_allowlisted_capability_exists_in_the_role_map(self) -> None:
        """No tool may cite a capability the platform catalogue does not define."""
        known = frozenset().union(*CAPABILITY_MAP.values())
        assert ALLOWLISTED_CAPABILITIES <= known
