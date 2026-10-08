"""The ``vision-stub`` stand-ins drive the real V1 pipeline without a provider.

Every image here is generated in the test and carries only synthetic text and
a test marker; nothing resembles client evidence.
"""

from __future__ import annotations

import io

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from src.modules.document.application.v1_pipeline import V1DocumentPipeline
from src.modules.document.domain.registry import OTHER_KIND
from src.modules.document.domain.v1 import PageQualityStatus, quality_status
from src.modules.document.infrastructure.rasterizer_pypdfium import PypdfiumRasterizer
from src.modules.document.infrastructure.vision_stub_adapter import (
    V1_SAMPLE_FIELDS,
    VisionStubAdapter,
)
from src.modules.document.ports import (
    ClassificationPageInput,
    ExtractionFieldSchema,
    PageRaster,
)

NIC = "rta.doc.nic"
FORM8 = "rta.doc.form8_instrument"
ALLOWED = (NIC, FORM8, "rta.doc.title_certificate", "rta.doc.survey_plan")


def marker_png(kind: str | None) -> bytes:
    image = Image.new("RGB", (400, 200), "white")
    meta = PngInfo()
    if kind:
        meta.add_text("Comment", f"STUB-KIND:{kind}\n")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=meta)
    return buffer.getvalue()


def raster(data: bytes) -> PageRaster:
    return PageRaster(page_no=1, png_bytes=data, width_px=400, height_px=200, dpi=200)


async def test_marked_pages_read_as_normal_quality_text_naming_the_kind() -> None:
    ocr = await VisionStubAdapter().document_text_detection(raster(marker_png("identity-card")))

    assert "STUB-KIND:identity-card" in ocr.text
    assert quality_status(ocr=ocr, ink_ratio=0.5) is PageQualityStatus.NORMAL


async def test_a_page_is_classified_only_into_a_type_the_matter_allows() -> None:
    stub = VisionStubAdapter()
    text = (await stub.document_text_detection(raster(marker_png("identity-card")))).text

    allowed = await stub.classify_pages(
        [ClassificationPageInput(1, text, "normal")], allowed_type_ids=ALLOWED, text_limit=None
    )
    refused = await stub.classify_pages(
        [ClassificationPageInput(1, text, "normal")], allowed_type_ids=(FORM8,), text_limit=None
    )

    assert allowed[0].type_id == NIC
    assert allowed[0].model_reported_confidence > 0.9
    assert refused[0].type_id == OTHER_KIND


async def test_an_unmarked_page_is_left_for_the_lawyer() -> None:
    stub = VisionStubAdapter()
    text = (await stub.document_text_detection(raster(marker_png(None)))).text

    pages = await stub.classify_pages(
        [ClassificationPageInput(1, text, "normal")], allowed_type_ids=ALLOWED, text_limit=None
    )

    assert pages[0].type_id == OTHER_KIND
    assert pages[0].model_reported_confidence < 0.5


async def test_extraction_returns_only_the_requested_fields_with_synthetic_values() -> None:
    fields = (
        ExtractionFieldSchema("transferorName", "Transferor name"),
        ExtractionFieldSchema("notInTheSamples", "Unknown"),
    )

    candidates = await VisionStubAdapter().extract_document(
        type_id=FORM8, text="", page_numbers=(1,), fields=fields
    )

    assert [(c.key, c.value) for c in candidates] == [
        ("transferorName", V1_SAMPLE_FIELDS["form8-instrument"]["transferorName"])
    ]
    assert "Synthetic" in candidates[0].value


async def test_the_real_v1_pipeline_runs_end_to_end_on_the_stand_ins() -> None:
    stub = VisionStubAdapter()
    pipeline = V1DocumentPipeline(
        rasterizer=PypdfiumRasterizer(dpi=200), ocr=stub, classifier=stub, extractor=stub
    )

    report = await pipeline.process(
        marker_png("identity-card"),
        "image/png",
        allowed_type_ids=ALLOWED,
        extraction_schemas={NIC: (ExtractionFieldSchema("transfereeNic", "NIC number"),)},
    )

    assert [document.logical_document.type_id for document in report.logical_documents] == [NIC]
    assert [c.key for c in report.logical_documents[0].candidates] == ["transfereeNic"]
