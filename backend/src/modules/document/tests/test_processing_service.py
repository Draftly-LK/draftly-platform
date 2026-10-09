"""Unit tests for the document-processing orchestrator — no network, no DB."""

from __future__ import annotations

import pytest

from src.modules.document.application.processing_service import (
    REASON_DATA_APPROVAL,
    REASON_LOW_CONFIDENCE,
    REASON_SEND_ALL_OVERRIDE,
    REASON_UNREGISTERED_KIND,
    DocumentProcessingService,
)
from src.modules.document.domain.models import ProcessingOutcome
from src.modules.document.ports import (
    ClassificationResult,
    ExtractionResult,
    PageRaster,
)


class FakeRasterizer:
    def __init__(self, page_count: int = 2) -> None:
        self.page_count = page_count
        self.calls = 0

    def rasterize(self, data: bytes, mime_type: str) -> list[PageRaster]:
        self.calls += 1
        return [
            PageRaster(page_no=n + 1, png_bytes=data, width_px=100, height_px=140, dpi=200)
            for n in range(self.page_count)
        ]


class FakeClassifier:
    def __init__(self, kind: str = "form8-instrument", confidence: float = 0.9) -> None:
        self.kind = kind
        self.confidence = confidence
        self.calls = 0

    async def classify(self, page: PageRaster) -> ClassificationResult:
        self.calls += 1
        return ClassificationResult(kind=self.kind, model_reported_confidence=self.confidence)


class FakeExtractor:
    """Yields district on page 1 and (conflictingly) also on page 2."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def extract(self, page: PageRaster, kind: str) -> ExtractionResult:
        self.calls.append(page.page_no)
        if page.page_no == 1:
            fields = {"district": "Colombo", "parcelNo": None, "extent": "0.0250 hectares"}
        else:
            fields = {"district": "Kandy", "parcelNo": "0020", "transfereeNic": "bad-nic"}
        return ExtractionResult(
            fields=fields,
            transcript=f"page {page.page_no} text",
            model_reported_confidence=0.8,
        )


def make_service(
    *,
    classifier: FakeClassifier | None = None,
    extractor: FakeExtractor | None = None,
    pages: int = 2,
) -> tuple[DocumentProcessingService, FakeClassifier, FakeExtractor]:
    fake_classifier = classifier or FakeClassifier()
    fake_extractor = extractor or FakeExtractor()
    service = DocumentProcessingService(
        rasterizer=FakeRasterizer(pages),
        classifier=fake_classifier,
        extractor=fake_extractor,
        provider_name="stub",
    )
    return service, fake_classifier, fake_extractor


class TestDataApprovalGate:
    async def test_real_document_refused_before_any_provider_call(self, monkeypatch):
        monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "false")
        service, classifier, extractor = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=False)
        assert report.outcome == ProcessingOutcome.MANUAL_REVIEW
        assert report.reasons == [REASON_DATA_APPROVAL]
        assert classifier.calls == 0
        assert extractor.calls == []
        assert report.ai_extraction_calls == 0

    async def test_synthetic_document_passes_the_gate(self, monkeypatch):
        monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "false")
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.EXTRACTED

    async def test_approval_admits_real_documents(self, monkeypatch):
        monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "true")
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=False)
        assert report.outcome == ProcessingOutcome.EXTRACTED


class TestClassificationRouting:
    async def test_below_threshold_goes_to_manual_review(self, monkeypatch):
        monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.55")
        service, _, extractor = make_service(
            classifier=FakeClassifier(kind="form8-instrument", confidence=0.2)
        )
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.MANUAL_REVIEW
        assert REASON_LOW_CONFIDENCE in report.reasons
        assert extractor.calls == []

    async def test_unregistered_kind_never_extracts(self):
        service, _, extractor = make_service(
            classifier=FakeClassifier(kind="other", confidence=0.95)
        )
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.MANUAL_REVIEW
        assert REASON_UNREGISTERED_KIND in report.reasons
        assert extractor.calls == []


class TestExtraction:
    async def test_fields_carry_true_page_numbers_and_no_region(self):
        service, _, extractor = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.EXTRACTED
        assert extractor.calls == [1, 2]
        by_key = {f.key: f for f in report.fields}
        assert by_key["district"].page_no == 1
        assert by_key["parcelNo"].page_no == 2
        # Provenance honesty: a boxless engine must not fabricate regions.
        assert all(not hasattr(f, "region") for f in report.fields)

    async def test_first_non_null_reading_wins(self):
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        by_key = {f.key: f for f in report.fields}
        assert by_key["district"].value == "Colombo"  # page 1, not page 2's Kandy

    async def test_deterministic_validators_populate_format_valid(self):
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        by_key = {f.key: f for f in report.fields}
        assert by_key["extent"].format_valid is True
        assert by_key["transfereeNic"].format_valid is False  # "bad-nic"
        assert by_key["district"].format_valid is None  # no validator exists

    async def test_meters_count_classify_plus_extract_calls(self):
        service, _, _ = make_service(pages=3)
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.pages_processed == 3
        assert report.ai_extraction_calls == 4  # 1 classify + 3 extracts

    async def test_transcripts_are_kept_per_page(self):
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.transcripts == {1: "page 1 text", 2: "page 2 text"}


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch):
    """Module-colocated tests do not inherit tests/conftest.py, so the
    Settings cache is reset here or env overrides would silently no-op."""
    import src.platform.config as config

    monkeypatch.delenv("PROVIDER_DATA_APPROVAL", raising=False)
    monkeypatch.delenv("CONFIDENCE_THRESHOLD", raising=False)
    config._settings = None
    yield
    config._settings = None


class TestSendAllOverride:
    """EXTRACTION_SEND_ALL reads pages the default pipeline would refuse.

    It relaxes exactly two gates — low classification confidence and an
    unregistered kind — and nothing else. The §10A data-protection gate and the
    "never invent a particular" rule are unaffected.
    """

    async def test_below_threshold_is_extracted_and_still_says_why(self, monkeypatch):
        monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.55")
        monkeypatch.setenv("EXTRACTION_SEND_ALL", "true")
        service, _, extractor = make_service(
            classifier=FakeClassifier(kind="form8-instrument", confidence=0.2)
        )
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.EXTRACTED
        assert extractor.calls == [1, 2]
        assert REASON_LOW_CONFIDENCE in report.reasons
        assert REASON_SEND_ALL_OVERRIDE in report.reasons

    async def test_unregistered_kind_yields_transcript_but_no_fields(self, monkeypatch):
        """The fallback template declares no fields, so nothing can be invented."""
        monkeypatch.setenv("EXTRACTION_SEND_ALL", "true")
        service, _, extractor = make_service(
            classifier=FakeClassifier(kind="other", confidence=0.95)
        )
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.EXTRACTED
        assert extractor.calls == [1, 2]
        assert report.fields == []
        assert report.transcripts == {1: "page 1 text", 2: "page 2 text"}
        assert REASON_UNREGISTERED_KIND in report.reasons
        assert REASON_SEND_ALL_OVERRIDE in report.reasons

    async def test_does_not_bypass_the_data_approval_gate(self, monkeypatch):
        """Sending everything to the provider is a separate decision from
        being allowed to send real client documents at all."""
        monkeypatch.setenv("EXTRACTION_SEND_ALL", "true")
        monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "false")
        service, classifier, extractor = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=False)
        assert report.outcome == ProcessingOutcome.MANUAL_REVIEW
        assert report.reasons == [REASON_DATA_APPROVAL]
        assert classifier.calls == 0
        assert extractor.calls == []

    async def test_clean_classification_reports_no_reasons(self, monkeypatch):
        monkeypatch.setenv("EXTRACTION_SEND_ALL", "true")
        service, _, _ = make_service()
        report = await service.process(b"pdf", "application/pdf", synthetic=True)
        assert report.outcome == ProcessingOutcome.EXTRACTED
        assert report.reasons == []
