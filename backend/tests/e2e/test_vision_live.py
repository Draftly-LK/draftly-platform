"""Opt-in Cloud Vision smoke test using only a generated synthetic image."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image, ImageDraw

pytestmark = pytest.mark.skipif(
    not (os.environ.get("RUN_LIVE_TESTS") == "1" and os.environ.get("RUN_VISION_LIVE") == "1"),
    reason="requires RUN_LIVE_TESTS=1 and RUN_VISION_LIVE=1",
)


async def test_live_document_text_detection() -> None:
    from google.cloud import vision

    from src.modules.document.infrastructure.vision_adapter import GoogleVisionOcrAdapter
    from src.modules.document.ports import PageRaster

    image = Image.new("RGB", (700, 180), "white")
    ImageDraw.Draw(image).text((30, 60), "SYNTHETIC DRAFTLY OCR TEST 0020", fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    page = PageRaster(page_no=1, png_bytes=output.getvalue(), width_px=700, height_px=180, dpi=200)

    result = await GoogleVisionOcrAdapter(
        client=vision.ImageAnnotatorClient()
    ).document_text_detection(page)

    assert "SYNTHETIC" in result.text.upper()
    assert result.words
