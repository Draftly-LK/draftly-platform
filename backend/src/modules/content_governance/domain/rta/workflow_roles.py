"""Matter-scoped RTA workflow roles and the capabilities they carry.

The RTA spec §12.5 requires six distinguishable actors: case assistant, lawyer
reviewer, responsible lawyer, template counsel, office administrator, and
auditor. The repository's account-role vocabulary is fixed at four values by
`auth-service.md` §10.6 and is **not** extended here — inventing a fifth
account role is a product decision, not an implementation detail.

So the six are modelled as *workflow roles*: a pure function of the account
role plus this actor's relationship to this matter. The account role says what
kind of user this is; the matter assignment says what they are on this file.

```text
account role + matter assignment  ->  workflow role  ->  RTA capabilities
```

The rule that matters: only ``RESPONSIBLE_LAWYER`` carries
``rta.form.approve``. Being an approver-tier account is not enough — the actor
must be the lawyer responsible for that matter. No service account and no
automated path can hold it (§12.5: "No system/service account may impersonate a
human approval").

This module takes the account role as a plain string so `content_governance`
does not import another module's domain.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.content_governance.domain.enums import RtaWorkflowRole

# Account-role values as persisted by auth (`auth/domain/models.py::Role`).
ACCOUNT_ROLE_REVIEWER = "reviewer"
ACCOUNT_ROLE_APPROVER = "approver"
ACCOUNT_ROLE_MAINTAINER = "maintainer"
ACCOUNT_ROLE_ADMINISTRATOR = "administrator"


# ── RTA capability keys ──────────────────────────────────────────────────────
#
# Namespaced `rta.*` so they never collide with the existing catalogue in
# `auth/domain/policies.py`, which stays the single server-side policy map.

CAP_MATTER_ROUTE = "rta.matter.route"
CAP_MATTER_CONFIRM_SUBTYPE = "rta.matter.confirm-subtype"
CAP_CHECKLIST_COMPILE = "rta.checklist.compile"
CAP_CHECKLIST_DECIDE = "rta.checklist.decide"
CAP_CHECKLIST_WAIVE = "rta.checklist.waive"
CAP_ORIGINAL_INSPECT = "rta.original.record-inspection"
CAP_SOURCE_UPLOAD = "rta.source.upload"
CAP_DOCUMENT_CLASSIFY = "rta.document.classify"
CAP_FACT_CONFIRM_NONCRITICAL = "rta.fact.confirm-noncritical"
CAP_FACT_CONFIRM_CRITICAL = "rta.fact.confirm-critical"
CAP_ISSUE_TRIAGE = "rta.issue.triage"
CAP_ISSUE_ACCEPT_RISK = "rta.issue.accept-risk"
CAP_ISSUE_OVERRIDE_OFFICE_POLICY = "rta.issue.override-office-policy"
CAP_FORM_GENERATE = "rta.form.generate"
CAP_FORM_FIELD_DECIDE = "rta.form.field-decide"
CAP_FORM_APPROVE = "rta.form.approve"
CAP_FORM_EXPORT = "rta.form.export"
CAP_REGISTRATION_EVENT_RECORD = "rta.registration.record-event"
CAP_TEMPLATE_VALIDATE = "rta.template.validate"
CAP_OFFICE_POLICY_CONFIGURE = "rta.office.configure-policy"
CAP_AUDIT_READ = "rta.audit.read"


RTA_CAPABILITY_MAP: dict[RtaWorkflowRole, frozenset[str]] = {
    RtaWorkflowRole.CASE_ASSISTANT: frozenset(
        {
            CAP_SOURCE_UPLOAD,
            CAP_DOCUMENT_CLASSIFY,
            CAP_CHECKLIST_COMPILE,
            CAP_AUDIT_READ,
        }
    ),
    RtaWorkflowRole.LAWYER_REVIEWER: frozenset(
        {
            CAP_SOURCE_UPLOAD,
            CAP_DOCUMENT_CLASSIFY,
            CAP_CHECKLIST_COMPILE,
            CAP_CHECKLIST_DECIDE,
            CAP_ORIGINAL_INSPECT,
            CAP_FACT_CONFIRM_NONCRITICAL,
            CAP_FACT_CONFIRM_CRITICAL,
            CAP_ISSUE_TRIAGE,
            CAP_FORM_GENERATE,
            CAP_FORM_FIELD_DECIDE,
            CAP_MATTER_ROUTE,
            CAP_AUDIT_READ,
        }
    ),
    RtaWorkflowRole.RESPONSIBLE_LAWYER: frozenset(
        {
            CAP_SOURCE_UPLOAD,
            CAP_DOCUMENT_CLASSIFY,
            CAP_CHECKLIST_COMPILE,
            CAP_CHECKLIST_DECIDE,
            CAP_CHECKLIST_WAIVE,
            CAP_ORIGINAL_INSPECT,
            CAP_FACT_CONFIRM_NONCRITICAL,
            CAP_FACT_CONFIRM_CRITICAL,
            CAP_ISSUE_TRIAGE,
            CAP_ISSUE_ACCEPT_RISK,
            CAP_ISSUE_OVERRIDE_OFFICE_POLICY,
            CAP_FORM_GENERATE,
            CAP_FORM_FIELD_DECIDE,
            CAP_FORM_APPROVE,
            CAP_FORM_EXPORT,
            CAP_REGISTRATION_EVENT_RECORD,
            CAP_MATTER_ROUTE,
            CAP_MATTER_CONFIRM_SUBTYPE,
            CAP_AUDIT_READ,
        }
    ),
    RtaWorkflowRole.TEMPLATE_COUNSEL: frozenset(
        {
            CAP_TEMPLATE_VALIDATE,
            CAP_AUDIT_READ,
        }
    ),
    RtaWorkflowRole.OFFICE_ADMIN: frozenset(
        {
            CAP_OFFICE_POLICY_CONFIGURE,
            CAP_ISSUE_OVERRIDE_OFFICE_POLICY,
            CAP_AUDIT_READ,
        }
    ),
    RtaWorkflowRole.AUDITOR: frozenset({CAP_AUDIT_READ}),
}

#: Capabilities that only the responsible lawyer for *this* matter may hold.
#: Kept as an explicit set so the invariant is testable rather than implied by
#: the map above.
RESPONSIBLE_LAWYER_ONLY: frozenset[str] = frozenset(
    {
        CAP_FORM_APPROVE,
        CAP_FORM_EXPORT,
        CAP_MATTER_CONFIRM_SUBTYPE,
        CAP_ISSUE_ACCEPT_RISK,
        CAP_CHECKLIST_WAIVE,
        CAP_REGISTRATION_EVENT_RECORD,
    }
)


@dataclass(frozen=True)
class MatterAssignment:
    """This actor's relationship to one matter, as the server knows it."""

    is_member: bool
    is_responsible_lawyer: bool


def resolve_workflow_role(
    account_role: str,
    assignment: MatterAssignment,
) -> RtaWorkflowRole | None:
    """Map an account role plus matter assignment onto one workflow role.

    Returns ``None`` when the actor has no standing on this matter at all;
    callers translate that to 404, not 403, so a non-member cannot infer the
    matter's existence (`security-model.md`, api-conventions §5).

    ``maintainer`` is template counsel and deliberately has **no** matter
    access: governed content is validated without reading client files
    (§12.5 "cannot access client matters by default").
    """
    if account_role == ACCOUNT_ROLE_MAINTAINER:
        return RtaWorkflowRole.TEMPLATE_COUNSEL
    if not assignment.is_member:
        return None
    if account_role == ACCOUNT_ROLE_APPROVER:
        return (
            RtaWorkflowRole.RESPONSIBLE_LAWYER
            if assignment.is_responsible_lawyer
            else RtaWorkflowRole.LAWYER_REVIEWER
        )
    if account_role == ACCOUNT_ROLE_REVIEWER:
        return RtaWorkflowRole.CASE_ASSISTANT
    if account_role == ACCOUNT_ROLE_ADMINISTRATOR:
        return RtaWorkflowRole.OFFICE_ADMIN
    return None


def is_rta_capability_granted(
    workflow_role: RtaWorkflowRole | None,
    capability: str,
) -> bool:
    """Deny by default: an unmapped role or capability grants nothing."""
    if workflow_role is None:
        return False
    return capability in RTA_CAPABILITY_MAP.get(workflow_role, frozenset())


def all_rta_capabilities() -> frozenset[str]:
    return frozenset().union(*RTA_CAPABILITY_MAP.values())
