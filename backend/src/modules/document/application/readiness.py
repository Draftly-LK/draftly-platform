"""Document-owned readiness reads use the complete inbox and current interpretation state."""

from src.modules.document.application.ingestion_service import SourceFileIngestionService
from src.modules.task.contracts import ReadinessDependency, ReadinessReference
from src.platform.request_context import RequestContext


class DocumentReadinessReader:
    def __init__(self, ingestion: SourceFileIngestionService) -> None:
        self._ingestion = ingestion

    async def readiness_dependencies(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[ReadinessDependency, ...]:
        dependencies = []
        cursor = None
        seen_documents: set[str] = set()
        sources = 0
        cursors = set()
        for _ in range(10):
            inbox = await self._ingestion.get_document_inbox(
                user_id=ctx.actor_id, matter_id=matter_id, limit=100, cursor=cursor
            )
            for view in inbox.source_files:
                source = view.source_file
                if source.state.value == "SUPERSEDED":
                    continue
                sources += 1
                ref = ReadinessReference("source", source.id, source.version)
                if source.state.value != "PROCESSED":
                    state = (
                        "failed"
                        if source.state.value in {"PROCESSING_FAILED", "REJECTED"}
                        else "pending"
                    )
                    dependencies.append(ReadinessDependency("processing", state, (ref,)))
            for page in inbox.page_accounting:
                if page.manual_review_required:
                    dependencies.append(
                        ReadinessDependency(
                            "grouping",
                            "pending",
                            (ReadinessReference("source", page.source_file_id),),
                        )
                    )
            for document_view in inbox.documents:
                document = document_view.document
                if document.id in seen_documents:
                    continue
                seen_documents.add(document.id)
                ref = ReadinessReference(
                    "document", document.id, document.version, document.interpretation_generation
                )
                if document.boundary_status.value != "CONFIRMED":
                    dependencies.append(ReadinessDependency("grouping", "pending", (ref,)))
                if document.class_status.value != "LAWYER_CONFIRMED":
                    dependencies.append(ReadinessDependency("classification", "pending", (ref,)))
                if document.extraction_state != "current":
                    dependencies.append(
                        ReadinessDependency(
                            "extraction",
                            "failed" if document.extraction_state == "failed" else "pending",
                            (ref,),
                        )
                    )
            cursor = inbox.next_cursor
            if cursor is None:
                break
            if cursor in cursors:
                return (*dependencies, ReadinessDependency("documents", "unknown"))
            cursors.add(cursor)
        else:
            dependencies.append(ReadinessDependency("documents", "unknown"))
        if not sources:
            dependencies.append(ReadinessDependency("upload", "pending"))
        return tuple(dependencies)
