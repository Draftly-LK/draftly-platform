from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.pipeline.gemini import classify_document, extract_document
from app.pipeline.registry import get_template, side_from_filename
from app.settings import get_settings

logger = logging.getLogger("draftly.backend")
logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="Draftly document intake", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessResponse(BaseModel):
    kind: str
    relation: str
    identity_side: str | None = None
    extracted_text: str
    extracted_fields: dict[str, str | None] = Field(default_factory=dict)
    extraction_confidence: float
    undetected_fields: list[str] = Field(default_factory=list)
    display_name: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def normalize_mime(mime: str, filename: str | None = None) -> str:
    lowered = (mime or "").lower().strip()
    if lowered in {"image/jpg", "image/pjpeg"}:
        return "image/jpeg"
    if lowered in {"image/x-png"}:
        return "image/png"
    if lowered in {"application/octet-stream", ""} and filename:
        suffix = filename.rsplit(".", 1)[-1].lower()
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "tif": "image/tiff",
            "tiff": "image/tiff",
            "pdf": "application/pdf",
        }.get(suffix, "image/jpeg")
    return lowered or "image/jpeg"


def unclassified_response() -> ProcessResponse:
    return ProcessResponse(
        kind="other",
        relation="unclassified",
        identity_side=None,
        extracted_text="",
        extracted_fields={},
        extraction_confidence=0.0,
        undetected_fields=[],
        display_name=None,
    )


@app.post("/api/documents/process", response_model=ProcessResponse)
async def process_document(file: UploadFile = File(...)) -> ProcessResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    mime = normalize_mime(file.content_type or "", file.filename)
    if not (mime.startswith("image/") or mime == "application/pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported mime type: {mime}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    # Stage 1 — classify against registered document types.
    try:
        classification = classify_document(
            image_bytes=content,
            mime_type=mime,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini classification failed")
        raise HTTPException(status_code=502, detail=f"Gemini classify failed: {exc}") from exc

    threshold = settings.confidence_threshold
    if (
        classification.kind == "other"
        or classification.confidence < threshold
        or get_template(classification.kind) is None
    ):
        return unclassified_response()

    template = get_template(classification.kind)
    assert template is not None

    # Stage 2 — type-specific extraction only for registered kinds.
    try:
        extraction = extract_document(
            image_bytes=content,
            mime_type=mime,
            template=template,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini extraction failed")
        raise HTTPException(status_code=502, detail=f"Gemini extract failed: {exc}") from exc

    file_side = side_from_filename(file.filename)
    side = file_side if file_side != "unknown" else extraction.side
    if side == "unknown":
        side = classification.side if classification.side != "unknown" else "unknown"

    fields = extraction.fields
    undetected = [key for key, value in fields.items() if value is None]
    name_en = fields.get("nameEn") if classification.kind == "identity" else None
    display_name: str | None = None
    relation = "unclassified"
    identity_side: str | None = None

    if classification.kind == "identity":
        relation = "authorized"
        identity_side = side
        display_name = (
            f"{name_en}'s identity card" if name_en else "Identity card (unidentified)"
        )

    payload: dict[str, Any] = {
        "kind": classification.kind,
        "relation": relation,
        "identity_side": identity_side,
        "extracted_text": extraction.extracted_text,
        "extracted_fields": fields,
        "extraction_confidence": extraction.confidence,
        "undetected_fields": undetected,
        "display_name": display_name,
    }
    return ProcessResponse(**payload)
