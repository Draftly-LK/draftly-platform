"""Google Cloud Vision OCR adapter for Sinhala, Tamil, and English pages."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision

from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.domain.v1 import DetectedLanguage, OcrElement, OcrPage, Point
from src.modules.document.ports import PageRaster

LANGUAGE_HINTS = ("si", "ta", "en")


def _languages(prop: Any) -> tuple[DetectedLanguage, ...]:
    detected = getattr(prop, "detected_languages", ()) if prop is not None else ()
    return tuple(
        DetectedLanguage(
            code=language.language_code,
            confidence=float(getattr(language, "confidence", 0.0)),
        )
        for language in detected
        if getattr(language, "language_code", "")
    )


def _polygon(bound: Any, width: int, height: int) -> tuple[Point, Point, Point, Point]:
    vertices = list(getattr(bound, "vertices", ()))
    if len(vertices) != 4:
        raise ExtractionProviderError("OCR returned a polygon without four ordered vertices.")
    return tuple(  # type: ignore[return-value]
        Point(
            float(getattr(vertex, "x", 0)) / max(width, 1),
            float(getattr(vertex, "y", 0)) / max(height, 1),
        )
        for vertex in vertices
    )


def _symbols_text(symbols: Iterable[Any]) -> str:
    return "".join(getattr(symbol, "text", "") for symbol in symbols)


def _words_text(words: Iterable[Any]) -> str:
    return " ".join(_symbols_text(getattr(word, "symbols", ())) for word in words)


class GoogleVisionOcrAdapter:
    """Calls ``document_text_detection`` once per rendered page."""

    def __init__(self, *, client: vision.ImageAnnotatorClient) -> None:
        self._client = client

    async def document_text_detection(self, page: PageRaster) -> OcrPage:
        image = vision.Image(content=page.png_bytes)
        context = vision.ImageContext(language_hints=list(LANGUAGE_HINTS))
        try:
            response = await asyncio.to_thread(
                self._client.document_text_detection,
                image=image,
                image_context=context,
            )
        except GoogleAPIError as exc:
            raise ExtractionProviderError("Vision OCR request failed.") from exc

        if response.error.message:
            raise ExtractionProviderError("Vision OCR returned an error.")

        annotation = response.full_text_annotation
        elements: list[OcrElement] = []
        page_languages: list[DetectedLanguage] = []
        for provider_page in annotation.pages:
            width = int(provider_page.width or page.width_px)
            height = int(provider_page.height or page.height_px)
            for language in _languages(getattr(provider_page, "property", None)):
                if language.code not in {item.code for item in page_languages}:
                    page_languages.append(language)
            for block in provider_page.blocks:
                block_words = [word for paragraph in block.paragraphs for word in paragraph.words]
                elements.append(
                    OcrElement(
                        level="block",
                        text=_words_text(block_words),
                        confidence=float(block.confidence),
                        detected_languages=_languages(getattr(block, "property", None)),
                        polygon=_polygon(block.bounding_box, width, height),
                    )
                )
                for paragraph in block.paragraphs:
                    elements.append(
                        OcrElement(
                            level="paragraph",
                            text=_words_text(paragraph.words),
                            confidence=float(paragraph.confidence),
                            detected_languages=_languages(getattr(paragraph, "property", None)),
                            polygon=_polygon(paragraph.bounding_box, width, height),
                        )
                    )
                    for word in paragraph.words:
                        word_text = _symbols_text(word.symbols)
                        elements.append(
                            OcrElement(
                                level="word",
                                text=word_text,
                                confidence=float(word.confidence),
                                detected_languages=_languages(getattr(word, "property", None)),
                                polygon=_polygon(word.bounding_box, width, height),
                            )
                        )
                        for symbol in word.symbols:
                            elements.append(
                                OcrElement(
                                    level="symbol",
                                    text=symbol.text,
                                    confidence=float(symbol.confidence),
                                    detected_languages=_languages(
                                        getattr(symbol, "property", None)
                                    ),
                                    polygon=_polygon(symbol.bounding_box, width, height),
                                )
                            )

        return OcrPage(
            text=annotation.text or "",
            detected_languages=tuple(page_languages),
            elements=tuple(elements),
        )
