"""The agent tool allowlist — a positive registry, not a refusal in the prompt.

`matter-agent-service.md` §Effective permission: a capability absent from this
registry is unreachable even for a user who holds it. That is what makes a
prompt injection reaching for a prohibited action fail at the executor rather
than at the model's discretion, so this module is the security boundary and not
a convenience index.

Tool names are function-calling identifiers sent to the model, so they are
snake_case. Capability keys are the catalogue strings from
`security-model.md` §3.1 and are never invented here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class ToolKind(StrEnum):
    """What executing a tool actually does."""

    READ = "read"
    """Returns matter data. No capability beyond matter ownership."""

    WRITE = "write"
    """Mutates automatically, when the authenticated user holds the capability."""

    PROPOSE = "propose"
    """Creates a pending action. A human confirms it before anything changes."""


@dataclass(frozen=True)
class AgentTool:
    """One allowlisted tool and the capabilities its execution requires."""

    name: str
    kind: ToolKind
    capabilities: frozenset[str] = field(default_factory=frozenset)
    requires_practising: bool = False
    summary: str = ""


def _tool(
    name: str,
    kind: ToolKind,
    *capabilities: str,
    requires_practising: bool = False,
    summary: str = "",
) -> AgentTool:
    return AgentTool(
        name=name,
        kind=kind,
        capabilities=frozenset(capabilities),
        requires_practising=requires_practising,
        summary=summary,
    )


# ── Read tools ───────────────────────────────────────────────────────────────
#
# Reads are gated by matter ownership alone. They return matter data the
# authenticated user can already reach through the ordinary screens.

_READ_TOOLS: Final[tuple[AgentTool, ...]] = (
    _tool(
        "read_matter_readiness",
        ToolKind.READ,
        summary="Current operational dependencies, unknown states and next action.",
    ),
    _tool(
        "research_legal_question",
        ToolKind.READ,
        summary="Grounded legal analysis over selected controlled statute/case sources; abstains without supported citations.",
    ),
    _tool("read_matter_summary", ToolKind.READ, summary="Matter summary and routing state."),
    _tool("read_document_status", ToolKind.READ, summary="Source-file and processing status."),
    _tool(
        "read_document_extraction",
        ToolKind.READ,
        summary="Extraction data, candidate fields and confidence.",
    ),
    _tool(
        "read_document_ocr_pages",
        ToolKind.READ,
        summary="Complete OCR for a source, page by page.",
    ),
    _tool(
        "read_verified_facts",
        ToolKind.READ,
        summary="Canonical fact register with exact scope, evidence, versions and review states; paginated.",
    ),
    _tool(
        "read_checklist_state",
        ToolKind.READ,
        summary="Current requirement checklist states and blocking requirements.",
    ),
    _tool(
        "read_draft_preflight",
        ToolKind.READ,
        summary="Page through existing working forms and their saved state; does not evaluate preflight.",
    ),
    _tool("search_matter_memory", ToolKind.READ, summary="Non-authoritative matter memory search."),
    _tool(
        "list_matter_inventory",
        ToolKind.READ,
        summary="Explicit matter subjects and transactions with current association revisions.",
    ),
    _tool(
        "compare_parcel_identity",
        ToolKind.READ,
        summary="Compare a document against known matter records. Returns evidence, does not decide.",
    ),
)


# ── Automatic write tools ────────────────────────────────────────────────────
#
# Each executes as the authenticated actor and only when that actor holds every
# listed capability. `checklist.administer` is the umbrella: a checklist write
# needs it and the narrow key for the field being changed
# (`security-model.md` §3.1).

_WRITE_TOOLS: Final[tuple[AgentTool, ...]] = (
    _tool("run_checks", ToolKind.WRITE, "check.run", summary="Run deterministic checks."),
    _tool(
        "generate_working_draft",
        ToolKind.WRITE,
        "draft.create",
        summary="Draft from an approved template and verified facts.",
    ),
    _tool(
        "save_working_note",
        ToolKind.WRITE,
        "note.create",
        summary="Save a non-authoritative working note.",
    ),
    _tool(
        "assign_checklist_item",
        ToolKind.WRITE,
        "checklist.administer",
        "checklist.assign",
        summary="Change a checklist item's assignee.",
    ),
    _tool(
        "update_checklist_due_date",
        ToolKind.WRITE,
        "checklist.administer",
        "checklist.update-due-date",
        summary="Change a checklist item's due date.",
    ),
    _tool(
        "request_checklist_collection",
        ToolKind.WRITE,
        "checklist.administer",
        "checklist.request-collection",
        summary="Move collection state to REQUESTED. Never downgrades received evidence.",
    ),
    _tool(
        "record_document_receipt",
        ToolKind.WRITE,
        "checklist.administer",
        "checklist.record-receipt",
        summary="Record that a document was physically received. Never SATISFIED.",
    ),
    _tool(
        "suggest_checklist_item",
        ToolKind.WRITE,
        "checklist.administer",
        "checklist.suggest-item",
        summary="Add an ad-hoc AI_SUGGESTED item. Never edits a governed template.",
    ),
    _tool(
        "propose_document_link",
        ToolKind.WRITE,
        "document.propose-link",
        summary="Offer a document towards a checklist requirement. Unconfirmed.",
    ),
    _tool(
        "create_field_candidate",
        ToolKind.WRITE,
        "candidate.create",
        summary="Create an unverified structured-field candidate.",
    ),
    _tool(
        "update_field_candidate",
        ToolKind.WRITE,
        "candidate.update",
        summary="Update an unverified candidate. Never overwrites a verified field.",
    ),
)


# ── Inline confirmation tools ────────────────────────────────────────────────
#
# These only create a pending action. The capability listed is the one the
# confirmation will require, and it is checked at proposal time too: the agent
# does not offer a card the authenticated user could never confirm, because
# that would advertise an escalation that does not exist.

_PROPOSE_TOOLS: Final[tuple[AgentTool, ...]] = (
    _tool(
        "propose_candidate_approval",
        ToolKind.PROPOSE,
        "particular.verify",
        requires_practising=True,
        summary="Card: approve or edit a candidate field.",
    ),
    _tool(
        "propose_checklist_decision",
        ToolKind.PROPOSE,
        "requirement.review",
        summary="Card: a non-administrative checklist decision.",
    ),
    _tool(
        "propose_requirement_link",
        ToolKind.PROPOSE,
        "requirement.review",
        summary="Card: link a document to a requirement.",
    ),
    _tool(
        "propose_form_field_correction",
        ToolKind.PROPOSE,
        "draft.save",
        summary="Card: confirm or correct a form field.",
    ),
    _tool(
        "propose_issue_resolution",
        ToolKind.PROPOSE,
        "finding.resolve",
        summary="Card: resolve an ordinary issue.",
    ),
    _tool(
        "propose_step_completion",
        ToolKind.PROPOSE,
        "step.complete",
        summary="Card: complete a workflow step.",
    ),
)


TOOL_ALLOWLIST: Final[Mapping[str, AgentTool]] = MappingProxyType(
    {tool.name: tool for tool in (*_READ_TOOLS, *_WRITE_TOOLS, *_PROPOSE_TOOLS)}
)
"""Every tool the agent can reach. Absence from this mapping is a refusal."""


ALLOWLISTED_CAPABILITIES: Final[frozenset[str]] = frozenset(
    capability for tool in TOOL_ALLOWLIST.values() for capability in tool.capabilities
)
"""The capability ceiling. The agent cannot reach a capability outside this set."""


PROHIBITED_CAPABILITIES: Final[frozenset[str]] = frozenset(
    {
        # Verification and legal judgement
        "particular.correct",
        "particular.add",
        "finding.waive",
        "step.override",
        "deadline.confirm",
        # Approval, export, attestation
        "draft.approve",
        "export.create",
        "instrument.attest",
        "register.certify-return",
        # Retention and destruction
        "retention.hold",
        "retention.release",
        "retention.approve-destruction",
        # Accounts, billing, platform
        "user.role.set",
        "billing.manage",
        "platform.administer",
        # Restricted compliance
        "compliance.view",
        "compliance.act",
        # Governed content and corpus
        "content.author",
        "content.approve",
        "content.retire",
        "corpus.review",
        "corpus.approve",
        "corpus.quarantine",
    }
)
"""Capabilities the agent must never reach, asserted against the allowlist.

`particular.verify` is absent from this set on purpose: the agent may *propose*
a candidate approval, and a human confirms it. Executing the verification is
still not something the agent does.
"""


def get_tool(name: str) -> AgentTool | None:
    """Return the allowlisted tool, or None when the name is not allowlisted."""
    return TOOL_ALLOWLIST.get(name)


def tools_of_kind(kind: ToolKind) -> tuple[AgentTool, ...]:
    """Return every allowlisted tool of the given kind, in registration order."""
    return tuple(tool for tool in TOOL_ALLOWLIST.values() if tool.kind is kind)
