"""Ports for the document-processing pipeline (document-processing.md §3).

Application services depend on these protocols, never on concrete adapters.
Infrastructure implements them; wiring happens only in bootstrap.py.

v1 is Gemini-only: ClassifierPort and OcrExtractorPort are both implemented by
the Gemini adapter, and provenance is page-level. The port shapes deliberately
leave room for a box-producing engine (Document AI) to slot in later — that is
a new adapter and a settings value, not an application change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.modules.content_governance.contracts import MatterState

if TYPE_CHECKING:
    from src.modules.document.domain.ingestion import ProcessingRun, SourceFile
    from src.modules.document.domain.v1 import (
        ExtractedCandidate,
        OcrPage,
        PageClassification,
    )


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


class SourceFileStoragePort(Protocol):
    """Immutable object storage for uploaded bytes (§6.2 stage 2).

    ``put`` returns the storage object *version* rather than a boolean: the
    version is recorded on the SourceFile so a later read can prove it fetched
    the same bytes that were hashed. There is deliberately no ``delete`` and no
    ``overwrite`` — original evidence is immutable, and a cleaned copy is a new
    object under a new key.

    ``version`` is an opaque provider token — a GCS generation, a content hash,
    whatever the adapter can honestly guarantee. Nothing outside the adapter
    parses it. It is keyword-only and required on ``get`` so that a caller
    cannot quietly read "whatever is at this key now": an unpinned read is the
    failure this port exists to prevent.

    The port guarantees *identity* — that the bytes came from the object
    recorded at upload. It does not guarantee *integrity*; verifying the
    evidence hash is the caller's job, because the expected hash lives on the
    SourceFile rather than in storage.
    """

    async def put(self, key: str, data: bytes) -> str: ...

    async def get(self, key: str, *, version: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...


class ProcessingJobPort(Protocol):
    """Run the pipeline over one stored source file.

    Synchronous today (the outbox and worker runtime do not exist yet), so the
    returned run is already terminal. The signature is the one a queued
    implementation will keep: the caller hands over the SourceFile it already
    loaded under the tenant filter, so no implementation needs to re-read a row
    without a ``user_id`` predicate.
    """

    async def enqueue(
        self, *, source_file: SourceFile, correlation_id: str = ""
    ) -> ProcessingRun: ...


@dataclass(frozen=True)
class ClassificationPageInput:
    page_no: int
    text: str
    quality_status: str


@dataclass(frozen=True)
class ExtractionFieldSchema:
    key: str
    description: str


@dataclass(frozen=True)
class MatterDocumentTypes:
    allowed_type_ids: tuple[str, ...]
    extraction_schemas: dict[str, tuple[ExtractionFieldSchema, ...]]


class MatterDocumentTypesPort(Protocol):
    """Allowed types and strict schemas derived from the current matter checklist."""

    async def for_matter(self, *, user_id: str, matter_id: str) -> MatterDocumentTypes: ...


class VisionOcrPort(Protocol):
    """Cloud Vision document OCR normalized without losing polygon order."""

    async def document_text_detection(self, page: PageRaster) -> OcrPage: ...


class BatchPageClassifierPort(Protocol):
    """Classify all pages in one structured request where provider limits allow."""

    async def classify_pages(
        self,
        pages: list[ClassificationPageInput],
        *,
        allowed_type_ids: tuple[str, ...],
        text_limit: int | None,
    ) -> list[PageClassification]: ...


class MatterWorkflowCommandPort(Protocol):
    """Advance the §10.1 matter state from a recorded document act.

    Implemented by ``matter``, which owns the state machine and refuses any move
    it does not allow. This module only names the state the act implies.
    """

    async def advance_state(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None: ...


class StructuredDocumentExtractorPort(Protocol):
    """Extract string candidates from one complete logical-document transcript."""

    async def extract_document(
        self,
        *,
        type_id: str,
        text: str,
        page_numbers: tuple[int, ...],
        fields: tuple[ExtractionFieldSchema, ...],
    ) -> tuple[ExtractedCandidate, ...]: ...
