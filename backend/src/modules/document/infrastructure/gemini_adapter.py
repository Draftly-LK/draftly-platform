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
from google.genai.errors import ClientError
from pydantic import BaseModel, Field

from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.domain.registry import (
    OTHER_KIND,
    classification_prompt,
    registered_kinds,
    resolve_extraction_template,
)
from src.modules.document.ports import (
    ClassificationResult,
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


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


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

        raise ExtractionProviderError() from last_error
