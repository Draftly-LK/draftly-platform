"""Effective permission for an agent tool call.

`matter-agent-service.md` §Effective permission:

    effective = authenticated user's capabilities
              ∩ agent tool allowlist
              ∩ matter ownership

It is an intersection in every direction. The agent can never exceed the user
who is typing, and a user can never reach a capability the allowlist omits by
asking the agent. This module is pure: it takes a decided set of capabilities
and returns a decision, so it can be exhaustively tested without a database,
a model provider, or a request.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from enum import StrEnum

from src.modules.matter_agent.domain.allowlist import (
    ALLOWLISTED_CAPABILITIES,
    TOOL_ALLOWLIST,
    AgentTool,
    get_tool,
)


class DenialReason(StrEnum):
    """Closed set of refusal reasons, recorded on the tool call and audited.

    These are reason codes, not messages: they are safe to store and to alert
    on, and they carry no matter content.
    """

    TOOL_NOT_ALLOWLISTED = "tool_not_allowlisted"
    TOOL_NOT_IMPLEMENTED = "tool_not_implemented"
    """Allowlisted and authorised, but no implementation is wired yet.

    Kept distinct from ``TOOL_NOT_ALLOWLISTED`` on purpose: one means *you may
    not*, the other means *we cannot yet*. Collapsing them would make a missing
    feature look like a security refusal in the audit trail.
    """

    MATTER_NOT_OWNED = "matter_not_owned"
    CAPABILITY_NOT_HELD = "capability_not_held"
    PRACTISING_STATUS_ABSENT = "practising_status_absent"
    STALE_TARGET_VERSION = "stale_target_version"
    DOMAIN_REFUSED = "domain_refused"


@dataclass(frozen=True)
class ToolAuthorization:
    """The decision for one attempted tool call."""

    tool_name: str
    granted: bool
    reason: DenialReason | None = None
    missing_capabilities: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        return self.granted


def _granted(tool: AgentTool) -> ToolAuthorization:
    return ToolAuthorization(tool_name=tool.name, granted=True)


def _denied(
    tool_name: str,
    reason: DenialReason,
    missing: AbstractSet[str] = frozenset(),
) -> ToolAuthorization:
    return ToolAuthorization(
        tool_name=tool_name,
        granted=False,
        reason=reason,
        missing_capabilities=frozenset(missing),
    )


def authorize_tool(
    *,
    tool_name: str,
    user_capabilities: AbstractSet[str],
    matter_owned: bool,
    is_practising_notary: bool = False,
) -> ToolAuthorization:
    """Decide whether this tool call may execute.

    The order of checks is deliberate. The allowlist is consulted **first**, so
    a prohibited tool is refused identically for every caller and a matter
    owner with a wide role learns nothing from the refusal. Ownership is
    checked before capabilities for the same reason existence hiding puts 404
    before 403 (`security-model.md` §5).
    """
    tool = get_tool(tool_name)
    if tool is None:
        return _denied(tool_name, DenialReason.TOOL_NOT_ALLOWLISTED)

    if not matter_owned:
        return _denied(tool.name, DenialReason.MATTER_NOT_OWNED)

    missing = tool.capabilities - set(user_capabilities)
    if missing:
        return _denied(tool.name, DenialReason.CAPABILITY_NOT_HELD, missing)

    if tool.requires_practising and not is_practising_notary:
        return _denied(tool.name, DenialReason.PRACTISING_STATUS_ABSENT)

    return _granted(tool)


def effective_capabilities(user_capabilities: AbstractSet[str]) -> frozenset[str]:
    """The capabilities actually reachable through the agent.

    The intersection of what the user holds with what the allowlist exposes.
    Holding `draft.approve` adds nothing here, because no tool requires it.
    """
    return frozenset(user_capabilities) & ALLOWLISTED_CAPABILITIES


def reachable_tools(
    *,
    user_capabilities: AbstractSet[str],
    matter_owned: bool,
    is_practising_notary: bool = False,
) -> frozenset[str]:
    """Names of every tool this caller could execute right now.

    Used to build the function declarations offered to the model, so the model
    is never shown a tool the caller cannot use.
    """
    return frozenset(
        name
        for name in TOOL_ALLOWLIST
        if authorize_tool(
            tool_name=name,
            user_capabilities=user_capabilities,
            matter_owned=matter_owned,
            is_practising_notary=is_practising_notary,
        ).granted
    )
