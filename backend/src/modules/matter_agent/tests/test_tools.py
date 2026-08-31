"""Tool registry and the one write the agent owns end to end."""

from __future__ import annotations

import pytest

from src.modules.matter_agent.application.tools import (
    IMPLEMENTED_TOOLS,
    OUT_OF_SCOPE,
    SaveWorkingNoteTool,
    build_tool_registry,
    unimplemented_tools,
)
from src.modules.matter_agent.domain.allowlist import TOOL_ALLOWLIST
from src.modules.matter_agent.domain.models import SuggestionOrigin
from src.modules.matter_agent.ports import ToolInvocation
from src.modules.matter_agent.tests.fakes import RecordingTool


class FakeNotes:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    async def create_note(
        self,
        *,
        user_id: str,
        matter_id: str,
        author_id: str,
        body: str,
        origin: str,
        session_id: str | None,
    ) -> str:
        self.created.append(
            {
                "user_id": user_id,
                "matter_id": matter_id,
                "author_id": author_id,
                "body": body,
                "origin": origin,
                "session_id": session_id,
            }
        )
        return "note-1"


def invocation(**arguments: object) -> ToolInvocation:
    return ToolInvocation(
        tool_name="save_working_note",
        arguments=dict(arguments),
        matter_id="mat-1",
        actor_id="usr-1",
    )


class TestTheRegistry:
    def test_a_tool_outside_the_allowlist_cannot_be_registered(self) -> None:
        """You cannot widen the agent's authority by adding a class."""
        with pytest.raises(ValueError, match="not allowlisted"):
            build_tool_registry({"delete_everything": RecordingTool("delete_everything")})

    def test_an_allowlisted_tool_registers(self) -> None:
        registry = build_tool_registry({"run_checks": RecordingTool("run_checks")})
        assert set(registry) == {"run_checks"}

    def test_unimplemented_tools_are_reported_rather_than_discovered(self) -> None:
        registry = build_tool_registry({"run_checks": RecordingTool("run_checks")})
        pending = unimplemented_tools(registry)
        assert "run_checks" not in pending
        assert "save_working_note" in pending
        assert set(pending) < set(TOOL_ALLOWLIST)

    def test_every_allowlisted_tool_is_implemented_or_has_a_stated_reason(self) -> None:
        """A gap must be reviewable, not discovered when a user hits it."""
        assert IMPLEMENTED_TOOLS | set(OUT_OF_SCOPE) == set(TOOL_ALLOWLIST)
        assert not (IMPLEMENTED_TOOLS & set(OUT_OF_SCOPE)), "a tool cannot be both"
        for name, reason in OUT_OF_SCOPE.items():
            assert reason.strip(), f"{name} needs a stated reason"

    def test_the_composition_root_wires_exactly_the_implemented_set(self) -> None:
        """The declared set and the real registry cannot drift apart.

        Constructing the registry needs no live session: every builder binds a
        repository to the session lazily and nothing queries until a tool runs.
        """
        from src.bootstrap import build_agent_tools

        registry = build_agent_tools(None, session_id="asess-1", memory=None)  # type: ignore[arg-type]
        assert set(registry) == IMPLEMENTED_TOOLS
        assert set(unimplemented_tools(registry)) == set(OUT_OF_SCOPE)


class TestSaveWorkingNote:
    async def test_the_note_is_labelled_ai_suggested_in_the_database(self) -> None:
        """A stored column, not a rendering convention."""
        notes = FakeNotes()
        tool = SaveWorkingNoteTool(notes, session_id="asess-1")

        result = await tool.execute(invocation(body="Follow up on the survey plan."))

        assert notes.created[0]["origin"] == SuggestionOrigin.AI_SUGGESTED.value
        assert notes.created[0]["session_id"] == "asess-1"
        assert result.resource_refs == ("note-1",)

    async def test_the_summary_names_the_artefact_without_quoting_it(self) -> None:
        notes = FakeNotes()
        tool = SaveWorkingNoteTool(notes)
        secret = "NIC 199012345678 appears on the deed"

        result = await tool.execute(invocation(body=secret))

        assert secret not in result.summary
        assert result.summary == "Saved a working note."

    async def test_an_empty_note_is_refused_rather_than_stored(self) -> None:
        notes = FakeNotes()
        tool = SaveWorkingNoteTool(notes)

        result = await tool.execute(invocation(body="   "))

        assert notes.created == []
        assert result.resource_refs == ()

    def test_the_declaration_matches_the_allowlist_entry(self) -> None:
        declaration = SaveWorkingNoteTool(FakeNotes()).declaration()
        assert declaration.name in TOOL_ALLOWLIST
        assert declaration.description == TOOL_ALLOWLIST[declaration.name].summary
