"""Tool implementations and the registry that binds them to the allowlist.

A tool implements ``AgentToolPort``. It is reached only after
``ToolExecutor`` has cleared the allowlist, matter ownership, the capability
set and practising status, so a tool never re-checks authority — it does the
work and returns a safe summary.

Two rules every tool obeys:

* ``ToolResult.summary`` is safe for memory, logs and the transcript.
  ``ToolResult.payload`` may hold matter content and goes to the model
  transiently only.
* Anything the agent creates carries ``SuggestionOrigin.AI_SUGGESTED``. It is a
  stored column, so no downstream gate can mistake it for a human decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from src.modules.matter_agent.domain.allowlist import TOOL_ALLOWLIST
from src.modules.matter_agent.domain.models import SuggestionOrigin
from src.modules.matter_agent.ports import (
    AgentToolPort,
    ToolDeclaration,
    ToolInvocation,
    ToolResult,
)


class MatterNoteWriter(Protocol):
    """Persists a non-authoritative working note."""

    async def create_note(
        self,
        *,
        user_id: str,
        matter_id: str,
        author_id: str,
        body: str,
        origin: str,
        session_id: str | None,
    ) -> str: ...


class SaveWorkingNoteTool:
    """``note.create`` — the one write the agent owns end to end.

    A note is explicitly non-authoritative: it never satisfies a requirement,
    never feeds a draft, and is labelled AI_SUGGESTED when the agent wrote it.
    """

    name = "save_working_note"

    def __init__(self, notes: MatterNoteWriter, *, session_id: str | None = None) -> None:
        self._notes = notes
        self._session_id = session_id

    def declaration(self) -> ToolDeclaration:
        return ToolDeclaration(
            name=self.name,
            description=TOOL_ALLOWLIST[self.name].summary,
            parameters={
                "type": "object",
                "properties": {
                    "body": {
                        "type": "string",
                        "description": "The note text. Plain prose, no legal conclusions.",
                    }
                },
                "required": ["body"],
                "additionalProperties": False,
            },
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        body = str(invocation.arguments.get("body", "")).strip()
        if not body:
            return ToolResult(summary="No note was saved because no text was supplied.")

        note_id = await self._notes.create_note(
            user_id=invocation.actor_id,
            matter_id=invocation.matter_id,
            author_id=invocation.actor_id,
            body=body,
            origin=SuggestionOrigin.AI_SUGGESTED.value,
            session_id=self._session_id,
        )
        # The summary names the artefact, never quotes its content.
        return ToolResult(
            summary="Saved a working note.",
            resource_refs=(note_id,),
            payload={"noteId": note_id},
        )


def build_tool_registry(tools: Mapping[str, AgentToolPort]) -> dict[str, AgentToolPort]:
    """Bind implementations to allowlisted names, refusing anything unknown.

    A tool that is not in the allowlist cannot be registered at all. That keeps
    the allowlist the single place authority is described: you cannot add a
    capability to the agent by adding a class.
    """
    unknown = sorted(set(tools) - set(TOOL_ALLOWLIST))
    if unknown:
        raise ValueError(f"tools are not allowlisted: {', '.join(unknown)}")
    return dict(tools)


#: Allowlisted tools that are deliberately **not** implemented, with the reason.
#: Recorded here rather than discovered at runtime, so the gap is reviewable.
#: The executor denies each with `tool_not_implemented` and audits the denial.
OUT_OF_SCOPE: Mapping[str, str] = MappingProxyType(
    {
        "generate_working_draft": "Deferred until the scoped draft contract is implemented in Task 7.",
        "update_field_candidate": "Use the canonical human review flow; no automatic candidate edits.",
        "propose_document_link": "Use the versioned, confirmed propose_requirement_link tool.",
        "compare_parcel_identity": (
            "No parcel aggregate exists in the domain. Implementing this would "
            "mean inventing a shape the rest of the system does not have."
        ),
        "create_field_candidate": (
            "Candidates are created by the extraction pipeline, not by hand. "
            "review_service exposes edit and approve, but no create."
        ),
        "propose_form_field_correction": "Confirmation cards are not wired yet.",
        "propose_issue_resolution": "Confirmation cards are not wired yet.",
        "propose_step_completion": "Confirmation cards are not wired yet.",
    }
)


#: Names the composition root wires to a real implementation. Kept beside
#: OUT_OF_SCOPE so the two together must account for the whole allowlist; a
#: tool added without either an implementation or a stated reason fails a test.
IMPLEMENTED_TOOLS: frozenset[str] = frozenset(set(TOOL_ALLOWLIST) - set(OUT_OF_SCOPE))


def unimplemented_tools(registry: Mapping[str, AgentToolPort]) -> tuple[str, ...]:
    """Allowlisted names the given registry does not implement.

    Surfaced deliberately rather than discovered at runtime. Every name here is
    refused with `tool_not_implemented` and audited, so a missing feature is a
    visible refusal and never a silent success.
    """
    return tuple(sorted(set(TOOL_ALLOWLIST) - set(registry)))
