"""Read tools, each backed by an existing application service.

No tool touches a repository or the database directly. Every one calls the
service that owns the concept, so the agent inherits that service's rules
rather than re-deriving them.

Two shapes appear in every tool:

* ``summary`` is safe for memory, logs and the transcript — counts, states and
  identifiers. ``payload`` may hold matter content and is sent to the model
  transiently only.
* Matter content returned to the model is wrapped as untrusted data. It may
  supply facts; it may never supply instructions.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.modules.matter_agent.domain.allowlist import TOOL_ALLOWLIST
from src.modules.matter_agent.ports import ToolDeclaration, ToolInvocation, ToolResult
from src.platform.errors import DraftlyError

#: Matter text handed to the model is fenced so the boundary is explicit.
UNTRUSTED_OPEN = "<untrusted-data>"
UNTRUSTED_CLOSE = "</untrusted-data>"

#: OCR can be very large. A page is truncated rather than blowing the turn
#: budget, and the truncation is reported so the model does not treat a partial
#: page as the whole page.
MAX_OCR_CHARS = 6_000


def untrusted(text: str) -> str:
    return f"{UNTRUSTED_OPEN}\n{text}\n{UNTRUSTED_CLOSE}"


def _declaration(name: str, properties: dict[str, Any], required: list[str]) -> ToolDeclaration:
    return ToolDeclaration(
        name=name,
        description=TOOL_ALLOWLIST[name].summary,
        parameters={"type": "object", "properties": properties, "required": required},
    )


class _BaseTool:
    """Shared plumbing: declaration from the allowlist, matter from the call."""

    name: str
    properties: dict[str, Any] = {}
    required: list[str] = []

    def declaration(self) -> ToolDeclaration:
        return _declaration(self.name, self.properties, self.required)


# ── Matter ───────────────────────────────────────────────────────────────────


class MatterReadPort(Protocol):
    async def summary_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...


class ReadMatterSummaryTool(_BaseTool):
    """Matter identity, routing state and lifecycle."""

    name = "read_matter_summary"

    def __init__(self, matters: MatterReadPort) -> None:
        self._matters = matters

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._matters.summary_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        return ToolResult(
            summary=(
                f"Matter {data.get('reference', '')}: "
                f"{data.get('rtaState', 'unknown')} / {data.get('lifecycleStatus', 'unknown')}."
            ),
            payload=data,
            resource_refs=(invocation.matter_id,),
        )


# ── Checklist ────────────────────────────────────────────────────────────────


class ChecklistReadPort(Protocol):
    async def checklist_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...


class ReadChecklistStateTool(_BaseTool):
    """Checklist items with their seven statuses, plus what blocks approval."""

    name = "read_checklist_state"

    def __init__(self, checklist: ChecklistReadPort) -> None:
        self._checklist = checklist

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._checklist.checklist_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        items = data.get("items", [])
        blocking = data.get("blockingRequirementIds", [])
        return ToolResult(
            summary=f"{len(items)} checklist items, {len(blocking)} blocking approval.",
            payload=data,
            resource_refs=tuple(str(item.get("itemId")) for item in items if item.get("itemId")),
        )


# ── Documents ────────────────────────────────────────────────────────────────


class DocumentReadPort(Protocol):
    async def documents_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...

    async def extraction_for_agent(
        self, *, user_id: str, detected_document_id: str
    ) -> dict[str, Any]: ...

    async def ocr_pages_for_agent(
        self, *, user_id: str, detected_document_id: str, page_no: int | None
    ) -> dict[str, Any]: ...


class ReadDocumentStatusTool(_BaseTool):
    """Source files and their processing state."""

    name = "read_document_status"

    def __init__(self, documents: DocumentReadPort) -> None:
        self._documents = documents

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._documents.documents_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        sources = data.get("sourceFiles", [])
        return ToolResult(
            summary=f"{len(sources)} source files on this matter.",
            payload=data,
            resource_refs=tuple(
                str(item.get("sourceFileId")) for item in sources if item.get("sourceFileId")
            ),
        )


class ReadDocumentExtractionTool(_BaseTool):
    """Candidate fields and confidence for one detected document."""

    name = "read_document_extraction"
    properties = {
        "detectedDocumentId": {"type": "string", "description": "The detected document id."}
    }
    required = ["detectedDocumentId"]

    def __init__(self, documents: DocumentReadPort) -> None:
        self._documents = documents

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        document_id = str(invocation.arguments.get("detectedDocumentId", ""))
        if not document_id:
            return ToolResult(summary="No document id was supplied.")
        data = await self._documents.extraction_for_agent(
            user_id=invocation.actor_id, detected_document_id=document_id
        )
        candidates = data.get("candidates", [])
        return ToolResult(
            summary=(
                f"{len(candidates)} candidate fields on document {document_id}. "
                "All unverified until a lawyer approves them."
            ),
            payload=data,
            resource_refs=(
                document_id,
                *(str(item.get("candidateId")) for item in candidates if item.get("candidateId")),
            ),
        )


class ReadDocumentOcrPagesTool(_BaseTool):
    """Full OCR text, page by page.

    The largest untrusted surface in the product: this is exactly where an
    instruction can be hidden inside a scanned document. Text is fenced and
    truncated, and it never reaches memory or a log.
    """

    name = "read_document_ocr_pages"
    properties = {
        "detectedDocumentId": {"type": "string", "description": "The detected document id."},
        "pageNo": {"type": "integer", "description": "Optional single page number."},
    }
    required = ["detectedDocumentId"]

    def __init__(self, documents: DocumentReadPort) -> None:
        self._documents = documents

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        document_id = str(invocation.arguments.get("detectedDocumentId", ""))
        if not document_id:
            return ToolResult(summary="No document id was supplied.")
        raw_page = invocation.arguments.get("pageNo")
        page_no = (
            int(raw_page) if isinstance(raw_page, int | str) and str(raw_page).isdigit() else None
        )

        data = await self._documents.ocr_pages_for_agent(
            user_id=invocation.actor_id,
            detected_document_id=document_id,
            page_no=page_no,
        )
        pages = data.get("pages", [])
        fenced = []
        for page in pages:
            text = str(page.get("text", ""))
            truncated = len(text) > MAX_OCR_CHARS
            fenced.append(
                {
                    "pageNo": page.get("pageNo"),
                    "truncated": truncated,
                    "text": untrusted(text[:MAX_OCR_CHARS]),
                }
            )
        return ToolResult(
            # Never quotes the OCR: the summary is what may enter memory.
            summary=f"Read OCR for {len(fenced)} page(s) of document {document_id}.",
            payload={"documentId": document_id, "pages": fenced},
            resource_refs=(document_id,),
        )


# ── Verified facts ───────────────────────────────────────────────────────────


class FactReadPort(Protocol):
    async def facts_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...


class ReadVerifiedFactsTool(_BaseTool):
    """Verified facts, kept visibly apart from unverified candidates."""

    name = "read_verified_facts"

    def __init__(self, facts: FactReadPort) -> None:
        self._facts = facts

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._facts.facts_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        facts = data.get("facts", [])
        return ToolResult(
            summary=f"{len(facts)} verified facts. These are the only values a draft may use.",
            payload=data,
            resource_refs=tuple(str(item.get("factId")) for item in facts if item.get("factId")),
        )


# ── Drafts ───────────────────────────────────────────────────────────────────


class DraftReadPort(Protocol):
    async def drafts_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...


class ReadDraftPreflightTool(_BaseTool):
    """Working forms and their preflight state."""

    name = "read_draft_preflight"

    def __init__(self, drafts: DraftReadPort) -> None:
        self._drafts = drafts

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._drafts.drafts_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        forms = data.get("forms", [])
        return ToolResult(
            summary=f"{len(forms)} working forms on this matter.",
            payload=data,
            resource_refs=tuple(str(item.get("formId")) for item in forms if item.get("formId")),
        )


# ── Memory ───────────────────────────────────────────────────────────────────


class SearchMatterMemoryTool(_BaseTool):
    """Non-authoritative recall. Absent memory is a normal answer, not an error."""

    name = "search_matter_memory"
    properties = {"query": {"type": "string", "description": "What to recall."}}
    required = ["query"]

    def __init__(self, memory: Any) -> None:
        self._memory = memory

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        query = str(invocation.arguments.get("query", "")).strip()
        if not query:
            return ToolResult(summary="No query was supplied.")
        try:
            hits = await self._memory.retrieve(matter_id=invocation.matter_id, probe=query, limit=8)
        except (DraftlyError, TimeoutError, OSError):
            return ToolResult(summary="Matter memory is unavailable; answer without recall.")
        return ToolResult(
            summary=f"{len(hits)} remembered items. Non-authoritative — verify before acting.",
            payload={
                "hits": [
                    {
                        "text": untrusted(hit.text),
                        "resourceId": hit.resource_id,
                        "resourceVersion": hit.resource_version,
                    }
                    for hit in hits
                ]
            },
        )


# ── Inventory ────────────────────────────────────────────────────────────────


class InventoryReadPort(Protocol):
    async def inventory_for_agent(self, *, user_id: str, matter_id: str) -> dict[str, Any]: ...


class ListMatterInventoryTool(_BaseTool):
    """Parties and documents on the matter.

    Parcels are named in the specification but no parcel aggregate exists in
    the domain yet, so this returns parties and documents and says so rather
    than inventing a shape the rest of the system does not have.
    """

    name = "list_matter_inventory"

    def __init__(self, inventory: InventoryReadPort) -> None:
        self._inventory = inventory

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        data = await self._inventory.inventory_for_agent(
            user_id=invocation.actor_id, matter_id=invocation.matter_id
        )
        return ToolResult(
            summary=(
                f"{len(data.get('parties', []))} parties, "
                f"{len(data.get('documents', []))} documents. "
                "Parcel records are not modelled in this release."
            ),
            payload=data,
            resource_refs=tuple(
                str(item.get("partyId")) for item in data.get("parties", []) if item.get("partyId")
            )
            + tuple(
                str(item.get("sourceFileId"))
                for item in data.get("documents", [])
                if item.get("sourceFileId")
            ),
        )
