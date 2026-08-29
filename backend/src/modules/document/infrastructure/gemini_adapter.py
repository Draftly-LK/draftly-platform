"""Gemini adapter implementing ClassifierPort and OcrExtractorPort.

Improvements over the reverted d0fbd00 pipeline it descends from:
- one injected ``genai.Client`` instead of a new client per call;
- typed structured output via ``response_schema`` (no fence-stripping JSON
  parsing — the SDK enforces the shape);
- provider failures surface as typed domain errors, never raw provider text;
- the retry policy is unit-tested.
"""

from __future__ import annotations

import asyncio
import re
from typing import TypeVar

import structlog
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError
from pydantic import BaseModel, Field

from src.modules.content_governance.contracts import get_document_class
from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.domain.registry import (
    OTHER_KIND,
    classification_prompt,
    registered_kinds,
    resolve_extraction_template,
)
from src.modules.document.domain.v1 import ExtractedCandidate, PageClassification
from src.modules.document.ports import (
    ClassificationPageInput,
    ClassificationResult,
    ExtractionFieldSchema,
    ExtractionResult,
    PageRaster,
)

log = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_S = 5.0
_MAX_DELAY_S = 25.0
_FAIL_FAST_WAIT_S = 30.0
_RETRY_HINT_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


class _ClassifyResponse(BaseModel):
    kind: str
    confidence: float = Field(ge=0.0, le=1.0)


class _ExtractResponse(BaseModel):
    transcript: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    fields: dict[str, str | None] = Field(default_factory=dict)


class _PageClassificationItem(BaseModel):
    page_no: int = Field(ge=1)
    type_id: str
    suggested_name: str | None = None
    starts_new_document: bool
    model_reported_confidence: float = Field(ge=0.0, le=1.0)


class _BatchClassificationResponse(BaseModel):
    pages: list[_PageClassificationItem]


class _CandidateItem(BaseModel):
    key: str
    value: str
    page_no: int = Field(ge=1)
    model_reported_confidence: float = Field(ge=0.0, le=1.0)


class _DocumentExtractionResponse(BaseModel):
    fields: list[_CandidateItem] = Field(default_factory=list)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _classification_catalog(allowed_type_ids: tuple[str, ...]) -> str:
    """Give Gemini meaning, while keeping the governed IDs authoritative."""

    rows: list[str] = []
    for type_id in allowed_type_ids:
        definition = get_document_class(type_id)
        template = (
            resolve_extraction_template(definition.extraction_template_kind)
            if definition and definition.extraction_template_kind
            else None
        )
        human_name = type_id.removeprefix("rta.doc.").replace("_", " ")
        hint = template.classification_hint if template else human_name
        rows.append(f"- {type_id}: {hint}")
    return "\n".join(rows)


class GeminiExtractionAdapter:
    """Whole-page Gemini reading — the doc's Level 2, which is all a
    boxless engine can honestly offer. Page-level provenance only."""

    def __init__(
        self,
        *,
        client: genai.Client,
        classify_model: str,
        extract_model: str,
    ) -> None:
        self._client = client
        self._classify_model = classify_model
        self._extract_model = extract_model

    # ── ClassifierPort ───────────────────────────────────────────────────────

    async def classify(self, page: PageRaster) -> ClassificationResult:
        response = await self._generate(
            model=self._classify_model,
            prompt=classification_prompt(),
            page=page,
            schema=_ClassifyResponse,
        )
        kind = response.kind if response.kind in registered_kinds() else OTHER_KIND
        return ClassificationResult(
            kind=kind,
            model_reported_confidence=_clamp(response.confidence),
        )

    # ── OcrExtractorPort ─────────────────────────────────────────────────────

    async def extract(self, page: PageRaster, kind: str) -> ExtractionResult:
        template = resolve_extraction_template(kind)
        if template is None:
            raise ExtractionProviderError(f"No template registered for kind '{kind}'.")
        response = await self._generate(
            model=self._extract_model,
            prompt=template.extraction_prompt(),
            page=page,
            schema=_ExtractResponse,
        )
        return ExtractionResult(
            fields=dict(response.fields),
            transcript=response.transcript,
            model_reported_confidence=_clamp(response.confidence),
        )

    async def classify_pages(
        self,
        pages: list[ClassificationPageInput],
        *,
        allowed_type_ids: tuple[str, ...],
        text_limit: int | None,
    ) -> list[PageClassification]:
        """Classify one upload in one structured request.

        The application may make one additional batched call with full text for
        low-confidence pages.  This method itself never fans out per page.
        """

        catalog = _classification_catalog(allowed_type_ids)
        page_blocks = []
        for page in pages:
            text = page.text if text_limit is None else page.text[:text_limit]
            page_blocks.append(f"<<<PAGE {page.page_no}; STATUS {page.quality_status}>>>\n{text}")
        prompt = (
            "Classify every page of one Sri Lankan conveyancing upload. Return exactly "
            "one row for each supplied page. The governed type catalog is below; type_id must "
            "be one of those exact IDs or other.\n"
            f"{catalog}\n- other: none of the governed types fits\n\n"
            "Use other when none fits; only then provide a short suggested_name. "
            "starts_new_document is true when this page begins a new logical instrument, "
            "including when it follows another instrument of the same type. Confidence is "
            "your own 0-1 estimate. Never create or rename a permanent type.\n\n"
            + "\n\n".join(page_blocks)
        )
        response = await self._generate_text(
            model=self._classify_model,
            prompt=prompt,
            schema=_BatchClassificationResponse,
        )
        return [
            PageClassification(
                page_no=item.page_no,
                type_id=item.type_id,
                suggested_name=item.suggested_name,
                starts_new_document=item.starts_new_document,
                model_reported_confidence=item.model_reported_confidence,
            )
            for item in response.pages
        ]

    async def extract_document(
        self,
        *,
        type_id: str,
        text: str,
        page_numbers: tuple[int, ...],
        fields: tuple[ExtractionFieldSchema, ...],
    ) -> tuple[ExtractedCandidate, ...]:
        """Extract exact strings from the complete logical-document OCR text."""

        field_list = "\n".join(f"- {field.key}: {field.description}" for field in fields)
        prompt = (
            "You extract structured fields from OCR text of Sri Lankan land-registration "
            "documents. Return only values present in the text. Never infer, translate, "
            "normalise, or complete a value. Copy values exactly, preserving leading zeros, "
            "punctuation, and separators. Omit fields that are absent. Every value must be a "
            "JSON string. page_no must name one of the supplied page markers.\n\n"
            f"Document type: {type_id}\nAllowed pages: {list(page_numbers)}\n"
            f"Strict fields:\n{field_list}\n\n{text}"
        )
        response = await self._generate_text(
            model=self._extract_model,
            prompt=prompt,
            schema=_DocumentExtractionResponse,
        )
        allowed_keys = {field.key for field in fields}
        allowed_pages = set(page_numbers)
        return tuple(
            ExtractedCandidate(
                key=item.key,
                value=item.value,
                page_no=item.page_no,
                model_reported_confidence=item.model_reported_confidence,
            )
            for item in response.fields
            if item.key in allowed_keys and item.page_no in allowed_pages
        )

    # ── provider call with retry ─────────────────────────────────────────────

    async def _generate(
        self,
        *,
        model: str,
        prompt: str,
        page: PageRaster,
        schema: type[_SchemaT],
    ) -> _SchemaT:
        contents = types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=page.png_bytes, mime_type="image/png"),
            ],
        )
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=schema,
        )

        delay = _BASE_DELAY_S
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                )
                parsed = response.parsed
                if isinstance(parsed, schema):
                    return parsed
                # Schema-enforced output should always parse; a miss means the
                # provider returned something unusable.
                raise ExtractionProviderError("Provider returned an unparseable response.")
            except ClientError as exc:
                last_error = exc
                message = str(exc)
                status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                if status != 429 and "RESOURCE_EXHAUSTED" not in message:
                    raise ExtractionProviderError() from exc
                hinted = _RETRY_HINT_RE.search(message)
                hinted_wait = float(hinted.group(1)) if hinted else None
                if "PerDay" in message and (hinted_wait or 0.0) > _FAIL_FAST_WAIT_S:
                    # A daily quota will not recover inside any sane retry
                    # window — waiting only burns the lease.
                    log.warning("gemini.daily_quota_exhausted", model=model)
                    raise ExtractionProviderError() from exc
                if attempt >= _MAX_ATTEMPTS:
                    break
                wait = delay
                if hinted_wait is not None:
                    wait = min(max(delay, hinted_wait + 1.0), _MAX_DELAY_S)
                log.warning(
                    "gemini.rate_limited",
                    model=model,
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)
                delay = min(delay * 2, _MAX_DELAY_S)
            except APIError as exc:
                raise ExtractionProviderError() from exc

        raise ExtractionProviderError() from last_error

    async def _generate_text(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[_SchemaT],
    ) -> _SchemaT:
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
        )
        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=prompt,
                config=config,
            )
        except APIError as exc:
            raise ExtractionProviderError() from exc
        parsed = response.parsed
        if not isinstance(parsed, schema):
            raise ExtractionProviderError("Provider returned an unparseable response.")
        return parsed
