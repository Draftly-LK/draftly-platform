"""Gemini two-stage classify then extract client."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.pipeline.registry import DocumentTemplate, classification_prompt, registered_kinds
from app.settings import Settings

logger = logging.getLogger("draftly.backend.gemini")


@dataclass
class ClassificationResult:
    kind: str
    side: str
    confidence: float
    raw_text: str | None = None


@dataclass
class ExtractionResult:
    side: str
    confidence: float
    extracted_text: str
    fields: dict[str, str | None]
    raw_text: str | None = None


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _generate_with_retry(
    client: genai.Client,
    *,
    model: str,
    contents: types.Content,
    config: types.GenerateContentConfig,
    attempts: int = 3,
) -> Any:
    delay = 5.0
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except ClientError as exc:
            last_error = exc
            message = str(exc)
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            if status != 429 and "RESOURCE_EXHAUSTED" not in message:
                raise
            if "PerDay" in message or ("quotaValue" in message and attempt >= 1):
                match = re.search(r"retry in ([0-9.]+)s", message, re.I)
                wait = float(match.group(1)) if match else 15.0
                if wait > 30:
                    logger.warning("Gemini daily/long quota hit; failing fast")
                    raise
            if attempt >= attempts:
                break
            wait = delay
            match = re.search(r"retry in ([0-9.]+)s", message, re.I)
            if match:
                wait = min(max(delay, float(match.group(1)) + 1.0), 25.0)
            logger.warning(
                "Gemini rate-limited (attempt %s/%s); sleeping %.1fs",
                attempt,
                attempts,
                wait,
            )
            time.sleep(wait)
            delay = min(delay * 2, 25.0)
    assert last_error is not None
    raise last_error


def _call_gemini(
    *,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    model: str,
    settings: Settings,
) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    parts: list[types.Part] = [
        types.Part.from_text(text=prompt),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
    ]
    logger.info("Gemini call model=%s", model)
    response = _generate_with_retry(
        client,
        model=model,
        contents=types.Content(role="user", parts=parts),
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return response.text or "{}"


def _normalize_side(value: Any) -> str:
    side = str(value or "unknown").lower()
    if side not in {"front", "back", "unknown"}:
        return "unknown"
    return side


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_kind(value: Any) -> str:
    kind = str(value or "other").lower().strip()
    allowed = set(registered_kinds()) | {"other"}
    if kind not in allowed:
        return "other"
    return kind


def classify_document(
    *,
    image_bytes: bytes,
    mime_type: str,
    settings: Settings,
) -> ClassificationResult:
    raw = _call_gemini(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=classification_prompt(),
        model=settings.gemini_classify_model,
        settings=settings,
    )
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        return ClassificationResult(
            kind="other",
            side="unknown",
            confidence=0.0,
            raw_text=raw,
        )

    kind = _normalize_kind(data.get("kind"))
    side = _normalize_side(data.get("side"))
    if kind != "identity":
        side = "unknown"
    return ClassificationResult(
        kind=kind,
        side=side,
        confidence=_normalize_confidence(data.get("confidence")),
        raw_text=raw,
    )


def extract_document(
    *,
    image_bytes: bytes,
    mime_type: str,
    template: DocumentTemplate,
    settings: Settings,
) -> ExtractionResult:
    raw = _call_gemini(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=template.extract_prompt(),
        model=settings.gemini_extract_model,
        settings=settings,
    )
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        return ExtractionResult(
            side="unknown",
            confidence=0.0,
            extracted_text="",
            fields=template.empty_fields(),
            raw_text=raw,
        )

    fields_raw = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    fields = template.normalize_fields(fields_raw)
    extracted_text = data.get("extracted_text")
    if not isinstance(extracted_text, str):
        extracted_text = ""
    return ExtractionResult(
        side=_normalize_side(data.get("side")),
        confidence=_normalize_confidence(data.get("confidence")),
        extracted_text=extracted_text.strip(),
        fields=fields,
        raw_text=raw,
    )


__all__ = [
    "ClassificationResult",
    "ExtractionResult",
    "classify_document",
    "extract_document",
]
