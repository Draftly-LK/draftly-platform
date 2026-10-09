"""Worker composition for extraction-review suggestions, with live authorization."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.domain.models import AccountStatus
from src.modules.auth.infrastructure.repository import SqlUserRepository
from src.modules.task.contracts import ReadinessReference
from src.platform.errors import DraftlyError
from src.platform.request_context import RequestContext


async def consume_processed_document(session: AsyncSession, payload: dict[str, Any]) -> str:
    from src.bootstrap import build_work_task_service

    actor = payload.get("actorId")
    matter = payload.get("matterId")
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return "suppressed"
    source = data.get("sourceFileId")
    version = data.get("sourceVersion")
    if not isinstance(actor, str) or not isinstance(matter, str):
        return "suppressed"
    if not isinstance(source, str) or not isinstance(version, int) or version < 1:
        return "suppressed"
    evidence = [ReadinessReference("source-file", source, version)]
    documents = data.get("documentReferences", [])
    if not isinstance(documents, list) or not documents:
        return "suppressed"
    for document in documents:
        if not isinstance(document, dict) or not isinstance(document.get("id"), str):
            return "suppressed"
        if not isinstance(document.get("version"), int) or not isinstance(
            document.get("generation"), int
        ):
            return "suppressed"
        evidence.append(
            ReadinessReference(
                "document", document["id"], document["version"], document["generation"]
            )
        )
    user = await SqlUserRepository(session).get(actor)
    if user is None or user.account_status is not AccountStatus.ACTIVE or user.role is None:
        return "suppressed"
    ctx = RequestContext(actor, user.role, payload.get("correlationId", ""))
    try:
        await build_work_task_service(session).create_suggestion(
            ctx,
            matter,
            title="Review new document evidence",
            reason="Review the extracted information against the source pages.",
            title_key="matterChecklist.tasks.documentReview.title",
            reason_key="matterChecklist.tasks.documentReview.reason",
            group="documents",
            evidence=tuple(evidence),
            dedup_key=f"document-review:{source}:{version}",
            provenance={
                "kind": "document-processing",
                "processingRunId": str(data.get("processingRunId", "")),
            },
        )
    except DraftlyError as cause:
        if cause.http_status in {403, 404, 409, 412, 422}:
            # A lost capability or superseded source is not a reason to retry
            # obsolete work. The current checklist remains independently usable.
            return "suppressed"
        raise
    return "processed"
