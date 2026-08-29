from __future__ import annotations

import math

import pytest

from src.modules.document.domain.v1 import (
    LogicalDocument,
    OcrElement,
    OcrPage,
    PageClassification,
    Point,
    RotationStatus,
    detect_rotation,
    group_logical_documents,
    normalize_classifications,
    transform_ocr,
    transform_point,
)


def _polygon(cx: float, cy: float, width: float, height: float, orientation: int):
    radians = math.radians(orientation)
    along = (math.cos(radians) * width / 2, math.sin(radians) * width / 2)
    down = (-math.sin(radians) * height / 2, math.cos(radians) * height / 2)
    return (
        Point(cx - along[0] - down[0], cy - along[1] - down[1]),
        Point(cx + along[0] - down[0], cy + along[1] - down[1]),
        Point(cx + along[0] + down[0], cy + along[1] + down[1]),
        Point(cx - along[0] + down[0], cy - along[1] + down[1]),
    )


def _page(orientation: int, count: int = 20, confidence: float = 0.95) -> OcrPage:
    return OcrPage(
        text="synthetic " * count,
        detected_languages=(),
        elements=tuple(
            OcrElement(
                level="word",
                text=f"word-{index}",
                confidence=confidence,
                detected_languages=(),
                polygon=_polygon(
                    0.1 + (index % 5) * 0.15, 0.1 + (index // 5) * 0.1, 0.08, 0.03, orientation
                ),
            )
            for index in range(count)
        ),
    )


@pytest.mark.parametrize(("orientation", "correction"), [(0, 0), (90, 270), (180, 180), (270, 90)])
def test_rotation_matches_benchmark_convention(orientation: int, correction: int) -> None:
    result = detect_rotation(_page(orientation))
    assert result.detected_orientation == orientation
    assert result.correction_applied == correction
    assert result.status is (
        RotationStatus.NOT_REQUIRED if correction == 0 else RotationStatus.APPLIED
    )


def test_rotation_abstains_below_word_threshold() -> None:
    result = detect_rotation(_page(90, count=9))
    assert result.status is RotationStatus.UNCERTAIN
    assert result.detected_orientation is None
    assert result.correction_applied == 0


def test_rotation_abstains_below_vote_share() -> None:
    upright = list(_page(0, count=10).elements)
    sideways = list(_page(90, count=10).elements)
    result = detect_rotation(
        OcrPage(text="synthetic", detected_languages=(), elements=tuple(upright + sideways))
    )
    assert result.status is RotationStatus.UNCERTAIN
    assert result.detected_orientation is None
    assert result.vote_share < 0.70


def test_low_confidence_words_do_not_vote() -> None:
    result = detect_rotation(_page(90, confidence=0.59))
    assert result.usable_word_count == 0
    assert result.status is RotationStatus.UNCERTAIN


def test_normalized_rotation_corners_match_benchmark() -> None:
    assert transform_point(Point(0.0, 0.0), 90) == Point(1.0, 0.0)
    assert transform_point(Point(1.0, 0.0), 90) == Point(1.0, 1.0)
    assert transform_point(Point(1.0, 1.0), 270) == Point(1.0, 0.0)


def test_transform_keeps_original_polygon_and_adds_reading_order() -> None:
    result = transform_ocr(_page(90, count=12), 270)
    assert all(word.corrected_polygon is not None for word in result.words)
    assert sorted(
        word.reading_order for word in result.words if word.reading_order is not None
    ) == list(range(12))
    assert result.words[0].polygon == _page(90, count=12).words[0].polygon


def test_unknown_model_type_is_kept_as_other_hint_only() -> None:
    result = normalize_classifications(
        [PageClassification(1, "invented-type", "Letter", False, 0.9)],
        page_count=1,
        allowed_type_ids={"title-certificate"},
    )
    assert result == [PageClassification(1, "other", "Letter", True, 0.9)]


def test_grouping_uses_type_change_and_explicit_boundary() -> None:
    classifications = [
        PageClassification(1, "form8", None, True, 0.9),
        PageClassification(2, "form8", None, False, 0.9),
        PageClassification(3, "form8", None, True, 0.9),
        PageClassification(4, "receipt", None, False, 0.9),
    ]
    grouped = group_logical_documents(classifications, {page: str(page) for page in range(1, 5)})
    assert [group.page_numbers for group in grouped] == [(1, 2), (3,), (4,)]
    assert all(isinstance(group, LogicalDocument) for group in grouped)
