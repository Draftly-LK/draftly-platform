from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw

from src.modules.document.application.v1_pipeline import V1DocumentPipeline
from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.domain.v1 import (
    ExtractedCandidate,
    OcrElement,
    OcrPage,
    PageClassification,
    PageQualityStatus,
    Point,
)
from src.modules.document.ports import (
    ClassificationPageInput,
    ExtractionFieldSchema,
    PageRaster,
)


def _png(*, ink: bool) -> bytes:
    image = Image.new("RGB", (100, 200), "white")
    if ink:
        ImageDraw.Draw(image).rectangle((10, 10, 90, 190), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _ocr_page(orientation: int, text: str) -> OcrPage:
    polygons = {
        0: (Point(0.1, 0.1), Point(0.2, 0.1), Point(0.2, 0.13), Point(0.1, 0.13)),
        90: (Point(0.9, 0.1), Point(0.9, 0.2), Point(0.87, 0.2), Point(0.87, 0.1)),
    }
    return OcrPage(
        text=text,
        detected_languages=(),
        elements=tuple(
            OcrElement("word", f"w{i}", 0.95, (), polygons[orientation]) for i in range(12)
        ),
    )


class Rasterizer:
    def rasterize(self, data: bytes, mime_type: str) -> list[PageRaster]:
        return [
            PageRaster(page_no=1, png_bytes=_png(ink=True), width_px=100, height_px=200, dpi=200),
            PageRaster(page_no=2, png_bytes=_png(ink=True), width_px=100, height_px=200, dpi=200),
            PageRaster(page_no=3, png_bytes=_png(ink=False), width_px=100, height_px=200, dpi=200),
        ]


class Ocr:
    async def document_text_detection(self, page: PageRaster) -> OcrPage:
        if page.page_no == 3:
            return OcrPage(text="", detected_languages=(), elements=())
        return _ocr_page(90 if page.page_no == 1 else 0, "synthetic text " * 5)


class Classifier:
    def __init__(self) -> None:
        self.calls: list[tuple[list[int], int | None]] = []

    async def classify_pages(
        self,
        pages: list[ClassificationPageInput],
        *,
        allowed_type_ids: tuple[str, ...],
        text_limit: int | None,
    ) -> list[PageClassification]:
        self.calls.append(([page.page_no for page in pages], text_limit))
        return [
            PageClassification(
                page.page_no,
                "form8" if page.page_no < 3 else "other",
                "Blank separator" if page.page_no == 3 else None,
                page.page_no in {1, 2, 3},
                0.9,
            )
            for page in pages
        ]


class Extractor:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def extract_document(
        self,
        *,
        type_id: str,
        text: str,
        page_numbers: tuple[int, ...],
        fields: tuple[ExtractionFieldSchema, ...],
    ) -> tuple[ExtractedCandidate, ...]:
        self.texts.append(text)
        return (ExtractedCandidate(fields[0].key, "0021", page_numbers[0], 0.91),)


async def test_pipeline_retains_pages_rotates_groups_and_extracts_strings() -> None:
    classifier = Classifier()
    extractor = Extractor()
    pipeline = V1DocumentPipeline(
        rasterizer=Rasterizer(), ocr=Ocr(), classifier=classifier, extractor=extractor
    )

    report = await pipeline.process(
        b"synthetic",
        "application/pdf",
        allowed_type_ids=("form8",),
        extraction_schemas={"form8": (ExtractionFieldSchema("parcelNo", "Parcel number"),)},
    )

    assert len(report.pages) == 3
    assert report.pages[0].rotation.correction_applied == 270
    assert (report.pages[0].corrected_width, report.pages[0].corrected_height) == (200, 100)
    assert report.pages[2].quality_status is PageQualityStatus.LIKELY_BLANK
    assert all(page.corrected_webp.startswith(b"RIFF") for page in report.pages)
    assert json.loads(report.pages[0].ocr_json)["rotation"]["correctionDegrees"] == 270
    assert classifier.calls == [([1, 2, 3], 2_000)]
    assert [doc.logical_document.page_numbers for doc in report.logical_documents] == [
        (1,),
        (2,),
        (3,),
    ]
    assert report.logical_documents[0].candidates[0].value == "0021"
    assert [document.extraction_state for document in report.logical_documents] == [
        "current",
        "current",
        "unsupported",
    ]
    assert "<<<PAGE 1>>>" in extractor.texts[0]


async def test_low_confidence_pages_are_reclassified_together_with_full_text() -> None:
    class LowClassifier(Classifier):
        async def classify_pages(
            self,
            pages: list[ClassificationPageInput],
            *,
            allowed_type_ids: tuple[str, ...],
            text_limit: int | None,
        ) -> list[PageClassification]:
            self.calls.append(([page.page_no for page in pages], text_limit))
            confidence = 0.4 if text_limit is not None else 0.8
            return [
                PageClassification(page.page_no, "form8", None, page.page_no == 1, confidence)
                for page in pages
            ]

    classifier = LowClassifier()
    pipeline = V1DocumentPipeline(
        rasterizer=Rasterizer(), ocr=Ocr(), classifier=classifier, extractor=Extractor()
    )
    report = await pipeline.process(
        b"synthetic",
        "application/pdf",
        allowed_type_ids=("form8",),
        extraction_schemas={},
    )
    assert classifier.calls == [([1, 2, 3], 2_000), ([1, 2, 3], None)]
    assert report.classification_calls == 2
    assert all(
        page.classification and page.classification.model_reported_confidence == 0.8
        for page in report.pages
    )


async def test_classification_failure_retains_every_page_for_review() -> None:
    class FailedClassifier(Classifier):
        async def classify_pages(
            self,
            pages: list[ClassificationPageInput],
            *,
            allowed_type_ids: tuple[str, ...],
            text_limit: int | None,
        ) -> list[PageClassification]:
            _ = (pages, allowed_type_ids, text_limit)
            raise ExtractionProviderError()

    report = await V1DocumentPipeline(
        rasterizer=Rasterizer(),
        ocr=Ocr(),
        classifier=FailedClassifier(),
        extractor=Extractor(),
    ).process(
        b"synthetic",
        "application/pdf",
        allowed_type_ids=("form8",),
        extraction_schemas={},
    )

    assert len(report.pages) == 3
    assert all(page.classification is not None for page in report.pages)
    assert all(
        page.classification.type_id == "other" for page in report.pages if page.classification
    )
    assert all(
        page.classification.model_reported_confidence == 0
        for page in report.pages
        if page.classification
    )
