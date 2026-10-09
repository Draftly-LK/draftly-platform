"""Provider-neutral value objects and deterministic V1 document policies.

The functions in this module deliberately know nothing about Google, Gemini,
SQLAlchemy, FastAPI, or object storage.  OCR engines provide ordered polygons;
this module decides page quality, orientation, corrected coordinates, and
logical-document boundaries in a form that can be tested byte-for-byte.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import StrEnum


class PageQualityStatus(StrEnum):
    NORMAL = "normal"
    LIKELY_BLANK = "likely_blank"
    OCR_SPARSE = "ocr_sparse"
    OCR_FAILED = "ocr_failed"


class RotationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    APPLIED = "applied"
    UNCERTAIN = "rotation_uncertain"


class CandidateReviewState(StrEnum):
    UNVERIFIED = "unverified"
    APPROVED = "approved"


@dataclass(frozen=True)
class Point:
    """Normalised point in the inclusive 0..1 page coordinate space."""

    x: float
    y: float


@dataclass(frozen=True)
class DetectedLanguage:
    code: str
    confidence: float


@dataclass(frozen=True)
class OcrElement:
    """One Vision element with its ordered four-point polygon intact."""

    level: str
    text: str
    confidence: float
    detected_languages: tuple[DetectedLanguage, ...]
    polygon: tuple[Point, Point, Point, Point]
    corrected_polygon: tuple[Point, Point, Point, Point] | None = None
    reading_order: int | None = None


@dataclass(frozen=True)
class OcrPage:
    text: str
    detected_languages: tuple[DetectedLanguage, ...]
    elements: tuple[OcrElement, ...]

    @property
    def words(self) -> tuple[OcrElement, ...]:
        return tuple(element for element in self.elements if element.level == "word")


@dataclass(frozen=True)
class RotationDecision:
    detected_orientation: int | None
    correction_applied: int
    vote_share: float
    usable_word_count: int
    status: RotationStatus


@dataclass(frozen=True)
class PageClassification:
    page_no: int
    type_id: str
    suggested_name: str | None
    starts_new_document: bool
    model_reported_confidence: float


@dataclass(frozen=True)
class LogicalDocument:
    index: int
    type_id: str
    suggested_name: str | None
    page_numbers: tuple[int, ...]
    text: str


@dataclass(frozen=True)
class ExtractedCandidate:
    key: str
    value: str
    page_no: int
    model_reported_confidence: float


@dataclass
class ProcessedPage:
    page_no: int
    original_width: int
    original_height: int
    corrected_width: int
    corrected_height: int
    quality_status: PageQualityStatus
    rotation: RotationDecision
    ocr: OcrPage
    corrected_webp: bytes
    ocr_json: bytes
    plain_text: bytes
    classification: PageClassification | None = None
    derivative_refs: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class ProcessedLogicalDocument:
    logical_document: LogicalDocument
    candidates: tuple[ExtractedCandidate, ...]
    extraction_state: str = "unavailable"


@dataclass
class V1PipelineReport:
    pages: tuple[ProcessedPage, ...]
    logical_documents: tuple[ProcessedLogicalDocument, ...]
    classification_calls: int
    extraction_calls: int


@dataclass(frozen=True)
class ReviewPage:
    id: str
    page_no: int
    corrected_width: int
    corrected_height: int
    quality_status: str
    rotation_status: str
    classification_type_id: str
    classification_confidence: float
    corrected_webp_ref: tuple[str, str]
    corrected_ocr_ref: tuple[str, str]
    source_file_id: str | None = None


@dataclass(frozen=True)
class ReviewCandidate:
    id: str
    key: str
    candidate_value: str
    edited_value: str | None
    page_no: int
    model_reported_confidence: float
    review_state: str
    version: int


@dataclass(frozen=True)
class DocumentReview:
    id: str
    matter_id: str
    detected_document_id: str
    type_id: str
    suggested_name: str | None
    pages: tuple[ReviewPage, ...]
    candidates: tuple[ReviewCandidate, ...]
    interpretation_generation: int = 1
    current: bool = False


def quality_status(
    *,
    ocr: OcrPage | None,
    ink_ratio: float,
    ocr_failed: bool = False,
    sparse_word_threshold: int = 5,
    sparse_character_threshold: int = 40,
    blank_ink_ratio: float = 0.002,
) -> PageQualityStatus:
    """Assign exactly one status while retaining the page in every case."""

    if ocr_failed:
        return PageQualityStatus.OCR_FAILED
    if ocr is None:
        return PageQualityStatus.OCR_FAILED
    if ink_ratio < blank_ink_ratio and not ocr.text.strip():
        return PageQualityStatus.LIKELY_BLANK
    if len(ocr.words) < sparse_word_threshold or len(ocr.text.strip()) < sparse_character_threshold:
        return PageQualityStatus.OCR_SPARSE
    return PageQualityStatus.NORMAL


def _snap_orientation(angle: float) -> int:
    return int(round(angle / 90.0) * 90) % 360


def detect_rotation(
    ocr: OcrPage,
    *,
    minimum_words: int = 10,
    minimum_vote_share: float = 0.70,
    minimum_word_confidence: float = 0.60,
) -> RotationDecision:
    """Vote from ordered word top edges and abstain below either threshold."""

    votes = {0: 0.0, 90: 0.0, 180: 0.0, 270: 0.0}
    usable = 0
    for word in ocr.words:
        if word.confidence < minimum_word_confidence:
            continue
        start, end = word.polygon[0], word.polygon[1]
        dx, dy = end.x - start.x, end.y - start.y
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        orientation = _snap_orientation(math.degrees(math.atan2(dy, dx)))
        votes[orientation] += word.confidence * length
        usable += 1

    total = sum(votes.values())
    if usable < minimum_words or total <= 0:
        return RotationDecision(None, 0, 0.0, usable, RotationStatus.UNCERTAIN)

    detected = max(votes, key=votes.__getitem__)
    share = votes[detected] / total
    if share < minimum_vote_share:
        return RotationDecision(None, 0, share, usable, RotationStatus.UNCERTAIN)

    correction = (360 - detected) % 360
    return RotationDecision(
        detected,
        correction,
        share,
        usable,
        RotationStatus.NOT_REQUIRED if correction == 0 else RotationStatus.APPLIED,
    )


def transform_point(point: Point, clockwise: int) -> Point:
    """Rotate a normalised point as the page rotates clockwise."""

    rotation = clockwise % 360
    if rotation == 0:
        return point
    if rotation == 90:
        return Point(1.0 - point.y, point.x)
    if rotation == 180:
        return Point(1.0 - point.x, 1.0 - point.y)
    if rotation == 270:
        return Point(point.y, 1.0 - point.x)
    raise ValueError("Only cardinal rotations are supported.")


def corrected_dimensions(width: int, height: int, clockwise: int) -> tuple[int, int]:
    return (height, width) if clockwise % 180 else (width, height)


def _reading_order_key(element: OcrElement, band: float = 0.02) -> tuple[int, float]:
    polygon = element.corrected_polygon or element.polygon
    return (round(min(point.y for point in polygon) / band), min(point.x for point in polygon))


def transform_ocr(ocr: OcrPage, clockwise: int) -> OcrPage:
    """Retain original polygons and add polygons in the corrected coordinate space."""

    transformed = [
        replace(
            element,
            corrected_polygon=tuple(  # type: ignore[arg-type]
                transform_point(point, clockwise) for point in element.polygon
            ),
        )
        for element in ocr.elements
    ]
    ordered_words = sorted(
        (element for element in transformed if element.level == "word"),
        key=_reading_order_key,
    )
    order_by_identity = {id(element): index for index, element in enumerate(ordered_words)}
    elements = tuple(
        replace(element, reading_order=order_by_identity.get(id(element)))
        for element in transformed
    )
    return replace(ocr, elements=elements)


def normalize_classifications(
    classifications: list[PageClassification],
    *,
    page_count: int,
    allowed_type_ids: set[str],
) -> list[PageClassification]:
    """Make model output total, ordered, and unable to expand the type catalogue."""

    by_page = {item.page_no: item for item in classifications if 1 <= item.page_no <= page_count}
    normalized: list[PageClassification] = []
    for page_no in range(1, page_count + 1):
        item = by_page.get(page_no)
        if item is None:
            item = PageClassification(page_no, "other", None, page_no == 1, 0.0)
        type_id = item.type_id if item.type_id in allowed_type_ids else "other"
        normalized.append(
            PageClassification(
                page_no=page_no,
                type_id=type_id,
                suggested_name=(item.suggested_name.strip() or None)
                if type_id == "other" and item.suggested_name
                else None,
                starts_new_document=True if page_no == 1 else item.starts_new_document,
                model_reported_confidence=max(0.0, min(1.0, item.model_reported_confidence)),
            )
        )
    return normalized


def group_logical_documents(
    classifications: list[PageClassification], page_text: dict[int, str]
) -> list[LogicalDocument]:
    """Start a group on either an explicit boundary or a type change."""

    groups: list[list[PageClassification]] = []
    for item in sorted(classifications, key=lambda value: value.page_no):
        if not groups:
            groups.append([item])
            continue
        previous = groups[-1][-1]
        if item.starts_new_document or item.type_id != previous.type_id:
            groups.append([item])
        else:
            groups[-1].append(item)

    logical: list[LogicalDocument] = []
    for index, group in enumerate(groups, start=1):
        page_numbers = tuple(item.page_no for item in group)
        logical.append(
            LogicalDocument(
                index=index,
                type_id=group[0].type_id,
                suggested_name=group[0].suggested_name,
                page_numbers=page_numbers,
                text="\n\n".join(page_text.get(page, "") for page in page_numbers),
            )
        )
    return logical
