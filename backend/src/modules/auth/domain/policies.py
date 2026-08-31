"""Capability policy map — the single server-side policy implementation.

Source of truth: security-model.md §3.2.  No capability grants are invented
here; if the map does not grant a capability it is denied.

Roles map to capability keys, not to prose. Every service cites a capability
key; this module resolves whether the actor's role grants it.
"""

from __future__ import annotations

from src.modules.auth.domain.models import Role

# ── Full capability catalogue (security-model.md §3.1 and §3.2) ──────────────
#
# Keys exactly match the capability strings used in every service doc.
# A capability absent from a role's frozenset is denied.

CAPABILITY_MAP: dict[Role, frozenset[str]] = {
    Role.REVIEWER: frozenset(
        {
            # Matter
            "matter.create",
            # Evidence
            "document.upload",
            "document.replace",
            "requirement.review",
            # Verified record
            "particular.verify",
            "particular.correct",
            "particular.add",
            # Findings
            "finding.resolve",
            # Workflow
            "step.complete",
            # Matter administration
            "check.run",
            "note.create",
            "checklist.administer",
            "checklist.assign",
            "checklist.update-due-date",
            "checklist.request-collection",
            "checklist.record-receipt",
            "checklist.suggest-item",
            # Candidates and links
            "candidate.create",
            "candidate.update",
            "document.propose-link",
            # Drafting
            "draft.create",
            "draft.save",
            "draft.restore",
            "draft.submit-for-review",
            # Party identity (gated; read requires purpose recording)
            "party.read-identity",
            "party.record-identity",
        }
    ),
    Role.APPROVER: frozenset(
        {
            # All reviewer capabilities
            "matter.create",
            "matter.reclassify",
            "matter.close",
            "matter.reopen",
            "matter.archive",
            "document.upload",
            "document.replace",
            "requirement.review",
            "particular.verify",
            "particular.correct",
            "particular.add",
            "finding.resolve",
            "finding.waive",
            "step.complete",
            "step.override",
            "deadline.confirm",
            # Matter administration
            "check.run",
            "note.create",
            "checklist.administer",
            "checklist.assign",
            "checklist.update-due-date",
            "checklist.request-collection",
            "checklist.record-receipt",
            "checklist.suggest-item",
            # Candidates and links
            "candidate.create",
            "candidate.update",
            "document.propose-link",
            "draft.create",
            "draft.save",
            "draft.restore",
            "draft.submit-for-review",
            # Approval-tier capabilities
            "draft.approve",
            "export.create",
            "instrument.attest",
            "register.certify-return",
            "party.read-identity",
            "party.record-identity",
            # Solo practitioner admin surface
            "billing.manage",
            "retention.hold",
            "retention.release",
            "retention.approve-destruction",
            "user.role.set",
        }
    ),
    Role.MAINTAINER: frozenset(
        {
            # Content and corpus governance only
            "content.author",
            "content.approve",
            "content.retire",
            "corpus.review",
            "corpus.approve",
            "corpus.quarantine",
        }
    ),
    Role.ADMINISTRATOR: frozenset(
        {
            # Accounts and roles
            "user.role.set",
            # Matter lifecycle
            "matter.create",
            "matter.close",
            "matter.reopen",
            "matter.archive",
            # Party identity
            "party.read-identity",
            "party.record-identity",
            # Retention and billing
            "retention.hold",
            "retention.release",
            "retention.approve-destruction",
            "billing.manage",
        }
    ),
}

# Capabilities that are NOT reachable through any of the four roles and are
# granted only by an audited administrative action (security-model.md §3.4).
SPECIAL_CAPABILITIES: frozenset[str] = frozenset(
    {
        "compliance.view",
        "compliance.act",
        "platform.administer",
    }
)


def is_capability_granted(role: Role, capability: str) -> bool:
    """Return True if the given role grants the requested capability."""
    return capability in CAPABILITY_MAP.get(role, frozenset())
