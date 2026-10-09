"""Domain errors for the matter master agent."""

from __future__ import annotations

from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    DraftlyError,
    NotFoundError,
)

__all__ = [
    "AgentDisabledError",
    "AgentSessionNotFoundError",
    "AgentRetryUnavailableError",
    "LegalResearchUnavailableError",
    "MemoryScopeNotReadyError",
    "ModelProviderError",
    "PendingActionExpiredError",
    "PendingActionNotFoundError",
    "PendingActionStaleError",
    "ToolNotAllowlistedError",
    "TurnBudgetExceededError",
    "VerifiedFieldOverwriteError",
]


class AgentSessionNotFoundError(NotFoundError):
    """The session does not exist, or belongs to another user or matter.

    Byte-identical to a genuinely missing session (`security-model.md` §5).
    """

    code = "agent_session_not_found"
    message = "No agent session was found."


class AgentDisabledError(DomainRuleError):
    code = "matter_agent_disabled"
    message = "The matter agent is not enabled for this deployment."


class AgentRetryUnavailableError(ConflictError):
    code = "agent_retry_unavailable"
    message = "This turn cannot be retried. Review the conversation and send a new message."


class ToolNotAllowlistedError(CapabilityDeniedError):
    """A tool outside the allowlist was requested.

    Raised by the executor, never decided by the model.
    """

    code = "tool_not_allowlisted"
    message = "That action is not available to the assistant."


class TurnBudgetExceededError(DomainRuleError):
    code = "agent_turn_budget_exceeded"
    message = "The assistant reached its limit for this turn."


class PendingActionNotFoundError(NotFoundError):
    code = "pending_action_not_found"
    message = "No pending action was found."


class PendingActionStaleError(ConflictError):
    """The target moved under the proposal; the card must be regenerated."""

    code = "pending_action_stale"
    http_status = 412
    message = "This suggestion is out of date. Ask the assistant to propose it again."


class PendingActionExpiredError(DomainRuleError):
    code = "pending_action_expired"
    message = "This suggestion has expired."


class VerifiedFieldOverwriteError(DomainRuleError):
    """A candidate contradicted a verified value.

    Raised as a conflict for a human rather than applied
    (`matter-agent-service.md` §Document processing follow-through).
    """

    code = "verified_field_overwrite_refused"
    message = "A verified field cannot be changed by a candidate."


class MemoryScopeNotReadyError(DraftlyError):
    """Internal signal, never surfaced: a non-READY scope means no recall."""

    code = "memory_scope_not_ready"
    http_status = 503
    message = "Matter memory is not ready."


class ModelProviderError(DraftlyError):
    code = "agent_model_unavailable"
    http_status = 503
    message = "The assistant is temporarily unavailable."


class LegalResearchUnavailableError(DomainRuleError):
    """The fixed abstention until a retrieval engine is connected.

    `matter-agent-service.md` §Agent loop: a legal question is never answered
    from model knowledge.
    """

    code = "legal_research_unavailable"
    message = "Legal research is not available yet, so this question cannot be answered here."
