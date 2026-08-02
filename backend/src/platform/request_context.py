"""RequestContext — server-built auth context attached to every authenticated request.

The browser never supplies a trusted role, organisation membership, or unrestricted
matter access. All fields here are derived server-side from persisted records
(auth-service.md §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.auth.domain.models import MatterMembershipRole, OrgRole, Role


@dataclass(frozen=True)
class MatterMembershipCtx:
    """Compact membership snapshot carried in the request context."""

    matter_id: str
    role: "MatterMembershipRole"


@dataclass(frozen=True)
class RequestContext:
    """Immutable, server-built context for every authenticated request.

    Created by auth_service.build_request_context; consumed by every downstream
    service. Billing state is intentionally absent — billing_service reads it
    server-side per operation.
    """

    actor_id: str
    organisation_id: str
    account_role: "Role"
    organisation_role: "OrgRole"
    matter_memberships: frozenset[MatterMembershipCtx] = field(default_factory=frozenset)
    correlation_id: str = ""

    def has_matter_membership(self, matter_id: str) -> bool:
        return any(m.matter_id == matter_id for m in self.matter_memberships)

    def matter_role(self, matter_id: str) -> "MatterMembershipRole | None":
        for m in self.matter_memberships:
            if m.matter_id == matter_id:
                return m.role
        return None
