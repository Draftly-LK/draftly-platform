"""RequestContext — server-built auth context attached to every authenticated request.

The browser never supplies a trusted role or unrestricted matter access. All
fields here are derived server-side from persisted records (auth-service.md §2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.auth.domain.models import Role


@dataclass(frozen=True)
class RequestContext:
    """Immutable, server-built context for every authenticated request.

    Created by auth_service.build_request_context; consumed by every downstream
    service. Billing state is intentionally absent — billing_service reads it
    server-side per operation.
    """

    actor_id: str
    account_role: Role
    correlation_id: str = ""
