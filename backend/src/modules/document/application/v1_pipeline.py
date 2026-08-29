"""The complete provider-neutral Draftly V1 document-processing pipeline."""

from __future__ import annotations

import io
import json
from dataclasses import asdict

from PIL import Image

from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.domain.v1 import (
    ExtractedCandidate,
    OcrPage,
    ProcessedLogicalDocument,
    ProcessedPage,
    RotationDecision,
    RotationStatus,
    V1PipelineReport,
    corrected_dimensions,
    detect_rotation,
    group_logical_documents,
    normalize_classifications,
    quality_status,
    transform_ocr,
)
from src.modules.document.ports import (
    BatchPageClassifierPort,
    ClassificationPageInput,
    ExtractionFieldSchema,
    RasterizerPort,
    StructuredDocumentExtractorPort,
    VisionOcrPort,
)


def _ink_ratio(image: Image.Image) -> float:
    gray = image.convert("L")
    histogram = gray.histogram()
    ink = sum(histogram[:245])
    return ink / max(image.width * image.height, 1)


def _rotate_image(image: Image.Image, clockwise: int) -> Image.Image:
    transposes = {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    return image.copy() if clockwise == 0 else image.transpose(transposes[clockwise])


def _webp(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(output, format="WEBP", lossless=True, method=6)
    return output.getvalue()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _ocr_payload(page: ProcessedPage) -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "pageNo": page.page_no,
        "pageWidth": page.corrected_width,
        "pageHeight": page.corrected_height,
        "originalPageWidth": page.original_width,
        "originalPageHeight": page.original_height,
        "qualityStatus": page.quality_status.value,
        "rotation": {
            "detectedOrientationDegrees": page.rotation.detected_orientation,
            "correctionDegrees": page.rotation.correction_applied,
            "status": page.rotation.status.value,
            "voteShare": round(page.rotation.vote_share, 4),
            "usableWordCount": page.rotation.usable_word_count,
            "threshold": {
                "minimumUsableWords": 10,
                "minimumVoteShare": 0.70,
                "minimumWordConfidence": 0.60,
            },
        },
        "fullText": page.ocr.text,
        "detectedLanguages": [asdict(language) for language in page.ocr.detected_languages],
        "elements": [
            {
                "level": element.level,
                "text": element.text,
                "confidence": element.confidence,
                "detectedLanguages": [asdict(language) for language in element.detected_languages],
                "originalPolygon": [asdict(point) for point in element.polygon],
                "correctedPolygon": [
                    asdict(point) for point in (element.corrected_polygon or element.polygon)
                ],
                "readingOrder": element.reading_order,
            }
            for element in page.ocr.elements
        ],
        "classification": (
            {
                "typeId": page.classification.type_id,
                "suggestedName": page.classification.suggested_name,
                "startsNewDocument": page.classification.starts_new_document,
                "modelReportedConfidence": page.classification.model_reported_confidence,
            }
            if page.classification
            else None
        ),
    }


class V1DocumentPipeline:
    """Render, OCR, rotate, classify, group, derive, and extract."""

    def __init__(
        self,
        *,
        rasterizer: RasterizerPort,
        ocr: VisionOcrPort,
        classifier: BatchPageClassifierPort,
        extractor: StructuredDocumentExtractorPort,
        classification_confidence_threshold: float = 0.55,
        classification_text_limit: int = 2_000,
    ) -> None:
        self._rasterizer = rasterizer
        self._ocr = ocr
        self._classifier = classifier
        self._extractor = extractor
        self._classification_confidence_threshold = classification_confidence_threshold
        self._classification_text_limit = classification_text_limit

    async def process(
        self,
        data: bytes,
        mime_type: str,
        *,
        allowed_type_ids: tuple[str, ...],
        extraction_schemas: dict[str, tuple[ExtractionFieldSchema, ...]],
    ) -> V1PipelineReport:
        rasters = self._rasterizer.rasterize(data, mime_type)
        pages: list[ProcessedPage] = []
        for raster in rasters:
            with Image.open(io.BytesIO(raster.png_bytes)) as opened:
                image = opened.convert("RGB")
            width, height = image.size
            try:
                raw_ocr = await self._ocr.document_text_detection(raster)
                failed = False
            except ExtractionProviderError:
                raw_ocr = OcrPage(text="", detected_languages=(), elements=())
                failed = True
            status = quality_status(ocr=raw_ocr, ink_ratio=_ink_ratio(image), ocr_failed=failed)
            rotation = (
                detect_rotation(raw_ocr)
                if not failed
                else RotationDecision(None, 0, 0.0, 0, RotationStatus.UNCERTAIN)
            )
            corrected_ocr = transform_ocr(raw_ocr, rotation.correction_applied)
            corrected_image = _rotate_image(image, rotation.correction_applied)
            corrected_width, corrected_height = corrected_dimensions(
                width, height, rotation.correction_applied
            )
            page = ProcessedPage(
                page_no=raster.page_no,
                original_width=width,
                original_height=height,
                corrected_width=corrected_width,
                corrected_height=corrected_height,
                quality_status=status,
                rotation=rotation,
                ocr=corrected_ocr,
                corrected_webp=_webp(corrected_image),
                ocr_json=b"",
                plain_text=corrected_ocr.text.encode("utf-8"),
            )
            pages.append(page)

        inputs = [
            ClassificationPageInput(page.page_no, page.ocr.text, page.quality_status.value)
            for page in pages
        ]
        classification_calls = 1
        try:
            classifications = await self._classifier.classify_pages(
                inputs,
                allowed_type_ids=allowed_type_ids,
                text_limit=self._classification_text_limit,
            )
        except ExtractionProviderError:
            # Page retention wins over classification availability. Normalising
            # an empty result creates explicit `other` / confidence-zero rows,
            # which the review UI warns about instead of losing the OCR work.
            classifications = []
        classifications = normalize_classifications(
            classifications,
            page_count=len(pages),
            allowed_type_ids=set(allowed_type_ids),
        )
        low_pages = {
            item.page_no
            for item in classifications
            if item.model_reported_confidence < self._classification_confidence_threshold
        }
        if low_pages:
            classification_calls += 1
            try:
                fallback = await self._classifier.classify_pages(
                    [item for item in inputs if item.page_no in low_pages],
                    allowed_type_ids=allowed_type_ids,
                    text_limit=None,
                )
            except ExtractionProviderError:
                fallback = []
            if fallback:
                fallback_by_page = {item.page_no: item for item in fallback}
                classifications = normalize_classifications(
                    [fallback_by_page.get(item.page_no, item) for item in classifications],
                    page_count=len(pages),
                    allowed_type_ids=set(allowed_type_ids),
                )

        by_page = {item.page_no: item for item in classifications}
        for page in pages:
            page.classification = by_page[page.page_no]
            page.ocr_json = _json_bytes(_ocr_payload(page))

        text_by_page = {
            page.page_no: f"<<<PAGE {page.page_no}>>>\n{page.ocr.text}" for page in pages
        }
        logical_documents = group_logical_documents(classifications, text_by_page)
        processed_documents: list[ProcessedLogicalDocument] = []
        extraction_calls = 0
        for logical_document in logical_documents:
            schema = extraction_schemas.get(logical_document.type_id, ())
            candidates: tuple[ExtractedCandidate, ...] = ()
            if schema and logical_document.text.strip():
                extraction_calls += 1
                try:
                    candidates = await self._extractor.extract_document(
                        type_id=logical_document.type_id,
                        text=logical_document.text,
                        page_numbers=logical_document.page_numbers,
                        fields=schema,
                    )
                except ExtractionProviderError:
                    candidates = ()
            processed_documents.append(
                ProcessedLogicalDocument(logical_document=logical_document, candidates=candidates)
            )

        return V1PipelineReport(
            pages=tuple(pages),
            logical_documents=tuple(processed_documents),
            classification_calls=classification_calls,
            extraction_calls=extraction_calls,
        )
