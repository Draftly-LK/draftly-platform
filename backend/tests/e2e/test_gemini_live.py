"""Live smoke test against the real Gemini API — never runs in CI.

Run manually:
    RUN_LIVE_TESTS=1 GEMINI_API_KEY=... uv run pytest tests/e2e -q

Purpose: prove the configured model ids actually exist and the adapter's
structured-output path works end to end. If GEMINI_EXTRACT_MODEL names a
model the API does not know, this fails with a clear provider error and the
fix is an env change, not a commit.

The fixture document is generated synthetic content — no real data leaves
the machine, so the §10A gate is satisfied with synthetic=True.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (os.environ.get("RUN_LIVE_TESTS") == "1" and os.environ.get("GEMINI_API_KEY")),
        reason="live Gemini smoke runs only with RUN_LIVE_TESTS=1 and GEMINI_API_KEY set",
    ),
]


def _synthetic_form8_png() -> bytes:
    """Render a tiny synthetic Form 8-ish page with Pillow — committable
    because every value is fictional and machine-generated."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        "Form 8 — INSTRUMENT OF TRANSFER",
        "Registration of Title Act, No. 21 of 1998 - Section 43",
        "1. Particulars of Land Parcel:",
        "a) District : Colombo",
        "b) Divisional Secretary's Division : Synthetic DS Division",
        "g) Cadastral Map No. : 900001",
        "j) Parcel No. : 0099",
        "l) Extent : 0.0250 Hectares",
        "3. Transferor: (a) Full Name: SYNTHETIC SELLER (PVT) LTD",
        "4. Transferee: (a) Full Name: SYNTHETIC BUYER",
        "   (b) National Identity Card No: 900010002V",
        "5. Consideration: Rs. 1,000,000",
    ]
    for row, line in enumerate(lines):
        draw.text((40, 40 + row * 48), line, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_live_classify_and_extract() -> None:
    import src.platform.config as config
    from src.bootstrap import build_processing_service
    from src.modules.document.domain.models import ProcessingOutcome

    os.environ["EXTRACTION_PROVIDER"] = "gemini"
    config._settings = None
    service = build_processing_service()

    report = await service.process(
        _synthetic_form8_png(),
        "image/png",
        synthetic=True,
        correlation_id="live-smoke",
    )

    assert report.outcome == ProcessingOutcome.EXTRACTED, report.reasons
    assert report.kind == "form8-instrument"
    values = {f.key: f.value for f in report.fields}
    assert values.get("district") == "Colombo"
    assert values.get("parcelNo") == "0099"
