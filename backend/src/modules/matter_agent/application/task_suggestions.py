"""Non-authoritative operational proposals; only a lawyer accepts them."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from src.modules.content_governance.contracts import (
    DocumentClassStatus,
    DocumentVersionRelationship,
)
from src.modules.matter_agent.application.read_tools import _BaseTool
from src.modules.matter_agent.ports import AgentEventPort, ToolInvocation, ToolResult
from src.modules.task.contracts import ReadinessReference
from src.platform.errors import DomainRuleError

if TYPE_CHECKING:
    from src.modules.document.application.ingestion_service import (
        ProcessingRunView,
        SourceFileIngestionService,
    )
    from src.modules.task.application.work_service import WorkTaskService
    from src.platform.request_context import RequestContext


async def current_source_document_pins(
    ingestion: SourceFileIngestionService, user_id: str, matter_id: str, source_file_id: str
) -> tuple[ReadinessReference, ...]:
    source = await ingestion.get_source_file(user_id=user_id, source_file_id=source_file_id)
    if source.source_file.matter_id != matter_id:
        raise DomainRuleError("The proposal source belongs to another matter.")
    pins = []
    for document_id in source.detected_document_ids:
        document = (
            await ingestion.get_detected_document(user_id=user_id, document_id=document_id)
        ).document
        if (
            document.version_relationship == DocumentVersionRelationship.SUPERSEDED
            or document.class_status == DocumentClassStatus.REJECTED
        ):
            continue
        pins.append(
            ReadinessReference(
                "document", document.id, document.version, document.interpretation_generation
            )
        )
    return tuple(pins)


async def publish_processing_followthrough(
    view: ProcessingRunView,
    ctx: RequestContext,
    events: AgentEventPort,
    *,
    ingestion: SourceFileIngestionService | None = None,
) -> None:
    """Queue source-bound review work in the processing transaction, without OCR."""
    if not view.run.succeeded:
        return
    source = view.source_file
    document_pins = tuple(
        ReadinessReference(
            "document",
            doc.document.id,
            doc.document.version,
            doc.document.interpretation_generation,
        )
        for doc in view.documents
    )
    if not document_pins and ingestion is not None:
        document_pins = await current_source_document_pins(
            ingestion, ctx.actor_id, source.matter_id, source.id
        )
    await events.publish(
        "document.processing-completed",
        user_id=ctx.actor_id,
        matter_id=source.matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        idempotency_key=f"document-followthrough:{view.run.id}",
        data={
            "sourceFileId": source.id,
            "sourceVersion": source.version,
            "documentVersionId": source.id,
            "processingRunId": view.run.id,
            "docClass": "unknown",
            "derivatives": [],
            "documentReferences": [
                {
                    "id": pin.id,
                    "version": pin.version,
                    "generation": pin.generation,
                }
                for pin in document_pins
            ],
        },
    )


class SuggestChecklistItemTool(_BaseTool):
    name = "suggest_checklist_item"
    properties = {
        "title": {"type": "string", "maxLength": 240},
        "reason": {"type": "string", "maxLength": 2000},
        "group": {
            "type": "string",
            "enum": [
                "documents",
                "evidence",
                "drafting",
                "execution",
                "registration",
                "completion",
            ],
        },
        "sourceFileId": {"type": "string", "maxLength": 128},
        "sourceVersion": {"type": "integer", "minimum": 1},
    }
    required = ["title", "reason", "group", "sourceFileId", "sourceVersion"]

    def __init__(
        self,
        tasks: WorkTaskService,
        *,
        ingestion: SourceFileIngestionService | None = None,
        session_id: str | None = None,
    ) -> None:
        self._tasks = tasks
        self._ingestion = ingestion
        self._session_id = session_id

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.context is None:
            raise DomainRuleError("An authenticated task proposal context is required.")
        arguments = invocation.arguments
        title = arguments["title"].strip()
        reason = arguments["reason"].strip()
        if not title or not reason:
            raise DomainRuleError("A task proposal needs a title and explanation.")
        canonical = {
            "title": " ".join(title.casefold().split()),
            "reason": " ".join(reason.casefold().split()),
            "group": arguments["group"],
            "sourceFileId": arguments["sourceFileId"],
            "sourceVersion": arguments["sourceVersion"],
        }
        evidence = [
            ReadinessReference("source-file", arguments["sourceFileId"], arguments["sourceVersion"])
        ]
        if self._ingestion is not None:
            evidence.extend(
                await current_source_document_pins(
                    self._ingestion,
                    invocation.context.actor_id,
                    invocation.matter_id,
                    arguments["sourceFileId"],
                )
            )
        canonical["documentReferences"] = [
            {"id": ref.id, "version": ref.version, "generation": ref.generation}
            for ref in evidence
            if ref.kind == "document"
        ]
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        proposal = await self._tasks.create_suggestion(
            invocation.context,
            invocation.matter_id,
            title=title,
            reason=reason,
            group=arguments["group"],
            evidence=tuple(evidence),
            dedup_key=f"agent-task:{digest}",
            provenance={
                "jobId": invocation.job_id,
                "toolName": self.name,
                "sessionId": self._session_id or "",
            },
        )
        return ToolResult(
            summary="Suggested operational work for lawyer review. It has not been accepted or completed.",
            payload={"suggestionId": proposal.id},
            resource_refs=(proposal.id,),
        )
