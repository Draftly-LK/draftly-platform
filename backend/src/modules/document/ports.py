"""Ports for the document-processing pipeline (document-processing.md §3).

Application services depend on these protocols, never on concrete adapters.
Infrastructure implements them; wiring happens only in bootstrap.py.

v1 is Gemini-only: ClassifierPort and OcrExtractorPort are both implemented by
the Gemini adapter, and provenance is page-level. The port shapes deliberately
leave room for a box-producing engine (Document AI) to slot in later — that is
a new adapter and a settings value, not an application change.
"""

from __future__ import annotations

from typing import Protocol


class PageRaster:
    """One rendered page. DPI is recorded so coordinate mapping stays exact
    if a box-producing engine is added later (document-processing.md §4, §6)."""

    def __init__(
        self,
        *,
        page_no: int,
        png_bytes: bytes,
        width_px: int,
        height_px: int,
        dpi: int,
    ) -> None:
        self.page_no = page_no  # 1-based, always
        self.png_bytes = png_bytes
        self.width_px = width_px
        self.height_px = height_px
        self.dpi = dpi


class ClassificationResult:
    """Which document type a page shows.

    ``model_reported_confidence`` is the provider's own estimate. It routes to
    manual review; it never verifies anything (§8 honesty rules).
    """

    def __init__(
        self,
        *,
        kind: str,
        model_reported_confidence: float,
        raw_model_text: str | None = None,
    ) -> None:
        self.kind = kind
        self.model_reported_confidence = model_reported_confidence
        self.raw_model_text = raw_model_text


class CandidateField:
    """One extracted particular — always a candidate, never a verified value.

    ``region`` is intentionally absent: a Gemini-only pipeline cannot produce
    trustworthy bounding boxes, and a fabricated box is worse than none.
    Provenance is the page number until a box-producing engine exists.
    """

    def __init__(
        self,
        *,
        key: str,
        value: str | None,
        page_no: int,
        source: str,
        model_reported_confidence: float,
        format_valid: bool | None = None,
    ) -> None:
        self.key = key
        self.value = value
        self.page_no = page_no
        self.source = source  # e.g. "gemini" | "stub"
        self.model_reported_confidence = model_reported_confidence
        # None = no deterministic validator exists for this field.
        self.format_valid = format_valid


class ExtractionResult:
    """Per-page extraction output from a provider."""

    def __init__(
        self,
        *,
        fields: dict[str, str | None],
        transcript: str,
        model_reported_confidence: float,
    ) -> None:
        self.fields = fields
        self.transcript = transcript
        self.model_reported_confidence = model_reported_confidence


class RasterizerPort(Protocol):
    """PDF/image bytes → deterministic per-page rasters.

    Raises UnsupportedDocumentError for mime types the pipeline cannot read.
    """

    def rasterize(self, data: bytes, mime_type: str) -> list[PageRaster]: ...


class ClassifierPort(Protocol):
    """Which registered document kind is this? (document-processing.md §3)

    Raises ExtractionProviderError on provider failure.
    """

    async def classify(self, page: PageRaster) -> ClassificationResult: ...


class OcrExtractorPort(Protocol):
    """Text + structured fields from one page for a known document kind.

    v1: GeminiExtractionAdapter (whole-page, page-level provenance).
    Later: DocumentAiAdapter at Level 0 with box provenance (§5 ladder).
    Raises ExtractionProviderError on provider failure.
    """

    async def extract(self, page: PageRaster, kind: str) -> ExtractionResult: ...
