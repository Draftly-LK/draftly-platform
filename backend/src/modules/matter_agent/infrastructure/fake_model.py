"""Deterministic model adapter.

Used by every automated test and by local development, so the Neon-only path is
what runs continuously and no test depends on a provider or a signed DPA
(``matter-agent-service.md`` §Tests and Rollout).

It is scripted, not clever: you hand it the turns you want and it returns them
in order. Determinism matters more than realism here — a flaky assistant makes
a flaky security test.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.modules.matter_agent.domain.models import AgentMessage, MessageRole
from src.modules.matter_agent.ports import ModelTurn, ProposedToolCall, ToolDeclaration

FAKE_MODEL_VERSION = "fake-deterministic-1"


class FakeAgentModelAdapter:
    """Replays scripted turns and records what it was offered."""

    def __init__(self, turns: Sequence[ModelTurn] | None = None) -> None:
        self._turns = list(turns or [])
        self.calls = 0
        self.offered_tools: list[tuple[str, ...]] = []
        self.seen_history_lengths: list[int] = []
        self.seen_memory: list[tuple[str, ...]] = []
        self._proposed = False

    async def run_turn(
        self,
        *,
        system_prompt: str,
        history: Sequence[AgentMessage],
        memory_context: Sequence[str],
        tools: Sequence[ToolDeclaration],
    ) -> ModelTurn:
        self.calls += 1
        self.offered_tools.append(tuple(tool.name for tool in tools))
        self.seen_history_lengths.append(len(history))
        self.seen_memory.append(tuple(memory_context))

        if self._turns:
            return self._turns.pop(0)
        return self._unscripted(history)

    def _unscripted(self, history: Sequence[AgentMessage]) -> ModelTurn:
        """Deterministic stand-in behaviour for local development.

        With no script the adapter answers plainly, except for one recognised
        instruction: ``review item <id>`` proposes a checklist-decision card.
        That exists so the propose → confirm path is reachable without a
        provider key; it is a property of this test double, not of the agent.
        """
        last = next((m.content for m in reversed(history) if m.role is MessageRole.USER), "")
        item_id = _requested_item(last)
        # Propose once per turn. Re-proposing every iteration would run the
        # loop to its ceiling and create eight identical cards.
        if item_id is None or self._proposed:
            return ModelTurn(
                text=(
                    "I can read this matter and suggest next steps. "
                    'Try: "review item <checklist item id>".'
                )
                if not self._proposed
                else "I have suggested a change. Confirm it to apply it.",
                model_version=FAKE_MODEL_VERSION,
            )
        self._proposed = True
        return ModelTurn(
            text="",
            tool_calls=(
                ProposedToolCall(
                    name="propose_checklist_decision",
                    arguments={
                        "itemId": item_id,
                        "expectedVersion": 1,
                        "digitalReview": "LAWYER_CONFIRMED",
                    },
                ),
            ),
            model_version=FAKE_MODEL_VERSION,
        )


_REVIEW_PREFIX = "review item "


def _requested_item(message: str) -> str | None:
    lowered = message.strip().lower()
    if not lowered.startswith(_REVIEW_PREFIX):
        return None
    item_id = message.strip()[len(_REVIEW_PREFIX) :].strip()
    return item_id or None
