from __future__ import annotations

from datetime import UTC, datetime

from src.modules.content_governance.contracts import SourceFileState
from src.modules.document.domain.ingestion import ProcessingRun
from src.modules.document.domain.v1 import (
    ExtractedCandidate,
    LogicalDocument,
    OcrPage,
    PageClassification,
    PageQualityStatus,
    ProcessedLogicalDocument,
    ProcessedPage,
    RotationDecision,
    RotationStatus,
    V1PipelineReport,
)
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository


class RecordingSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    def add(self, row: object) -> None:
        self.events.append(type(row).__name__)

    async def flush(self) -> None:
        self.events.append("flush")


async def test_processing_run_parent_is_flushed_before_v1_children() -> None:
    session = RecordingSession()
    page = ProcessedPage(
        page_no=1,
        original_width=100,
        original_height=200,
        corrected_width=100,
        corrected_height=200,
        quality_status=PageQualityStatus.NORMAL,
        rotation=RotationDecision(0, 0, 1.0, 12, RotationStatus.NOT_REQUIRED),
        ocr=OcrPage(text="synthetic", detected_languages=(), elements=()),
        corrected_webp=b"webp",
        ocr_json=b"{}",
        plain_text=b"synthetic",
        classification=PageClassification(1, "rta.doc.nic", None, True, 0.9),
        derivative_refs={
            "corrected_webp": ("page.webp", "1"),
            "corrected_ocr_json": ("ocr.json", "2"),
            "plain_ocr_text": ("text.txt", "3"),
        },
    )
    run = ProcessingRun(
        id="run_test",
        user_id="usr_test",
        matter_id="mat_test",
        source_file_id="src_test",
        provider="test",
        outcome=SourceFileState.PROCESSED,
        started_at=datetime.now(tz=UTC),
        correlation_id="corr_test",
        v1_report=V1PipelineReport(
            pages=(page,),
            logical_documents=(
                ProcessedLogicalDocument(
                    logical_document=LogicalDocument(
                        index=1,
                        type_id="rta.doc.nic",
                        suggested_name=None,
                        page_numbers=(1,),
                        text="synthetic",
                    ),
                    candidates=(
                        ExtractedCandidate(
                            key="synthetic_field",
                            value="synthetic_value",
                            page_no=1,
                            model_reported_confidence=0.9,
                        ),
                    ),
                ),
            ),
            classification_calls=1,
            extraction_calls=0,
        ),
    )

    repository = SqlDocumentIngestionRepository(session)  # type: ignore[arg-type]
    await repository.create_run(run)

    assert session.events == [
        "SourceFileProcessingRunRow",
        "flush",
        "DocumentProcessingPageRow",
        "ProcessingLogicalDocumentRow",
        "flush",
        "ProcessingCandidateFieldRow",
        "flush",
    ]
