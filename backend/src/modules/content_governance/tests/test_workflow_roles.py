"""Workflow roles — the §12.5 separation, and who may approve.

The acceptance criterion this file guards is narrow and important: **only the
responsible lawyer for a matter may approve a registration-oriented form.**
Holding an approver-tier account is not enough.
"""

from __future__ import annotations

import pytest

from src.modules.content_governance.domain.enums import RtaWorkflowRole
from src.modules.content_governance.domain.rta.workflow_roles import (
    ACCOUNT_ROLE_ADMINISTRATOR,
    ACCOUNT_ROLE_APPROVER,
    ACCOUNT_ROLE_MAINTAINER,
    ACCOUNT_ROLE_REVIEWER,
    CAP_AUDIT_READ,
    CAP_CHECKLIST_WAIVE,
    CAP_FACT_CONFIRM_CRITICAL,
    CAP_FORM_APPROVE,
    CAP_FORM_EXPORT,
    CAP_ISSUE_ACCEPT_RISK,
    CAP_MATTER_CONFIRM_SUBTYPE,
    CAP_REGISTRATION_EVENT_RECORD,
    CAP_SOURCE_UPLOAD,
    CAP_TEMPLATE_VALIDATE,
    RESPONSIBLE_LAWYER_ONLY,
    RTA_CAPABILITY_MAP,
    MatterAssignment,
    all_rta_capabilities,
    is_rta_capability_granted,
    resolve_workflow_role,
)

MEMBER = MatterAssignment(is_member=True, is_responsible_lawyer=False)
RESPONSIBLE = MatterAssignment(is_member=True, is_responsible_lawyer=True)
OUTSIDER = MatterAssignment(is_member=False, is_responsible_lawyer=False)


def test_all_six_spec_roles_are_representable() -> None:
    assert set(RTA_CAPABILITY_MAP) == set(RtaWorkflowRole)
    assert len(RtaWorkflowRole) == 6


def test_an_approver_who_is_responsible_is_the_responsible_lawyer() -> None:
    assert (
        resolve_workflow_role(ACCOUNT_ROLE_APPROVER, RESPONSIBLE)
        is RtaWorkflowRole.RESPONSIBLE_LAWYER
    )


def test_an_approver_who_is_not_responsible_is_only_a_reviewer() -> None:
    assert resolve_workflow_role(ACCOUNT_ROLE_APPROVER, MEMBER) is RtaWorkflowRole.LAWYER_REVIEWER


def test_a_reviewer_account_is_a_case_assistant() -> None:
    assert resolve_workflow_role(ACCOUNT_ROLE_REVIEWER, MEMBER) is RtaWorkflowRole.CASE_ASSISTANT


def test_an_administrator_is_an_office_admin() -> None:
    assert resolve_workflow_role(ACCOUNT_ROLE_ADMINISTRATOR, MEMBER) is RtaWorkflowRole.OFFICE_ADMIN


def test_a_maintainer_is_template_counsel_and_needs_no_matter_membership() -> None:
    """§12.5 — template counsel cannot access client matters by default."""
    assert (
        resolve_workflow_role(ACCOUNT_ROLE_MAINTAINER, OUTSIDER) is RtaWorkflowRole.TEMPLATE_COUNSEL
    )


def test_a_non_member_has_no_workflow_role() -> None:
    for account_role in (
        ACCOUNT_ROLE_REVIEWER,
        ACCOUNT_ROLE_APPROVER,
        ACCOUNT_ROLE_ADMINISTRATOR,
    ):
        assert resolve_workflow_role(account_role, OUTSIDER) is None


def test_an_unknown_account_role_grants_nothing() -> None:
    assert resolve_workflow_role("superuser", RESPONSIBLE) is None
    assert is_rta_capability_granted(None, CAP_AUDIT_READ) is False


# ── Approval is responsible-lawyer only ──────────────────────────────────────


def test_only_the_responsible_lawyer_may_approve_a_form() -> None:
    granted = [
        role for role in RtaWorkflowRole if is_rta_capability_granted(role, CAP_FORM_APPROVE)
    ]
    assert granted == [RtaWorkflowRole.RESPONSIBLE_LAWYER]


@pytest.mark.parametrize(
    "capability",
    [
        CAP_FORM_APPROVE,
        CAP_FORM_EXPORT,
        CAP_MATTER_CONFIRM_SUBTYPE,
        CAP_ISSUE_ACCEPT_RISK,
        CAP_CHECKLIST_WAIVE,
        CAP_REGISTRATION_EVENT_RECORD,
    ],
)
def test_the_responsible_lawyer_only_capabilities_are_held_by_exactly_that_role(
    capability: str,
) -> None:
    holders = [role for role in RtaWorkflowRole if is_rta_capability_granted(role, capability)]
    assert holders == [RtaWorkflowRole.RESPONSIBLE_LAWYER], capability


def test_the_declared_responsible_lawyer_only_set_matches_the_capability_map() -> None:
    """Keeps the documented set and the implemented map from drifting apart."""
    for capability in RESPONSIBLE_LAWYER_ONLY:
        holders = {role for role in RtaWorkflowRole if is_rta_capability_granted(role, capability)}
        assert holders == {RtaWorkflowRole.RESPONSIBLE_LAWYER}, capability


def test_a_case_assistant_cannot_confirm_a_critical_fact() -> None:
    """§12.5 — the assistant may organise evidence, not confirm legal facts."""
    assert (
        is_rta_capability_granted(RtaWorkflowRole.CASE_ASSISTANT, CAP_FACT_CONFIRM_CRITICAL)
        is False
    )


def test_a_lawyer_reviewer_may_confirm_facts_but_not_approve() -> None:
    assert is_rta_capability_granted(RtaWorkflowRole.LAWYER_REVIEWER, CAP_FACT_CONFIRM_CRITICAL)
    assert is_rta_capability_granted(RtaWorkflowRole.LAWYER_REVIEWER, CAP_FORM_APPROVE) is False


def test_template_counsel_validates_templates_and_touches_no_matter_evidence() -> None:
    assert is_rta_capability_granted(RtaWorkflowRole.TEMPLATE_COUNSEL, CAP_TEMPLATE_VALIDATE)
    assert is_rta_capability_granted(RtaWorkflowRole.TEMPLATE_COUNSEL, CAP_SOURCE_UPLOAD) is False
    assert (
        is_rta_capability_granted(RtaWorkflowRole.TEMPLATE_COUNSEL, CAP_FACT_CONFIRM_CRITICAL)
        is False
    )


def test_an_office_admin_cannot_waive_a_statutory_gate_or_approve() -> None:
    """§12.5 — office admin configures policy; it cannot waive statutory gates."""
    assert is_rta_capability_granted(RtaWorkflowRole.OFFICE_ADMIN, CAP_CHECKLIST_WAIVE) is False
    assert is_rta_capability_granted(RtaWorkflowRole.OFFICE_ADMIN, CAP_FORM_APPROVE) is False


def test_an_auditor_can_only_read() -> None:
    assert RTA_CAPABILITY_MAP[RtaWorkflowRole.AUDITOR] == frozenset({CAP_AUDIT_READ})


def test_every_capability_is_namespaced_and_held_by_someone() -> None:
    for capability in all_rta_capabilities():
        assert capability.startswith("rta."), capability
        assert any(is_rta_capability_granted(role, capability) for role in RtaWorkflowRole), (
            capability
        )


def test_capabilities_are_denied_by_default() -> None:
    for role in RtaWorkflowRole:
        assert is_rta_capability_granted(role, "rta.form.invent-a-value") is False
