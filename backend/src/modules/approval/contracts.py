"""The only surface other modules may import from approval.

`draft` needs to know whether a form still carries a live approval before it
lets anything touch the snapshot. `matter` and `notification` need to know where
the instrument stands with the registry, and whether a forwarding deadline is
running.

Both are read ports. Nothing here can create an approval, revoke one, or record
a registry event: approving is a personal professional act and recording an
official result requires evidence a human saw, so neither is reachable from
another module's code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class ApprovalSummary:
    """One §9.6 approval, as another module needs to see it."""

    id: str
    matter_id: str
    target_id: str
    target_version: str
    approver_id: str
    #: The digest of exactly what was approved. A caller compares it rather than
    #: trusting a state flag: a form whose bindings moved is a different form.
    snapshot_hash: str
    confirmed_fact_hash: str
    declaration_version: str
    created_at: datetime
    revoked_by_approval_id: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_by_approval_id is not None


@dataclass(frozen=True)
class RegistrationSummary:
    """Where one matter stands with the registry, from recorded events only.

    Every field is ``None`` until a human recorded the event with its evidence.
    Time never fills one in (§10.1).
    """

    attested_on: date | None = None
    presented_on: date | None = None
    registered_on: date | None = None
    refused_on: date | None = None
    #: The s. 45(1) forwarding date, and always provisional: the Sri Lankan
    #: public-holiday calendar behind it is unverified (§16.4).
    forwarding_due_on: date | None = None
    forwarding_due_provisional: bool = True

    @property
    def is_registered(self) -> bool:
        return self.registered_on is not None


class ApprovalReadPort(Protocol):
    """Read the live approval of one generated form, if there is one."""

    async def current_approval(self, user_id: str, form_id: str) -> ApprovalSummary | None: ...


class RegistrationReadPort(Protocol):
    """Read one matter's recorded registry position."""

    async def registration_summary(self, user_id: str, matter_id: str) -> RegistrationSummary: ...


__all__ = [
    "ApprovalReadPort",
    "ApprovalSummary",
    "RegistrationReadPort",
    "RegistrationSummary",
]
