"""Deterministic extraction stub for CI and local development.

Mirrors auth's StubIdentityAdapter: no network, byte-stable results, refused
outside local/test/ci at bootstrap. The stub classifies from magic markers in
the document bytes so tests can steer it without patching internals.
"""

from __future__ import annotations

from src.modules.document.domain.registry import OTHER_KIND, get_template
from src.modules.document.ports import (
    ClassificationResult,
    ExtractionResult,
    PageRaster,
)

#: Marker prefix tests can embed in fixture bytes: b"STUB-KIND:form8-instrument"
_KIND_MARKER = b"STUB-KIND:"

#: Deterministic sample values per kind — obviously synthetic.
_SAMPLE_FIELDS: dict[str, dict[str, str | None]] = {
    "identity-card": {
        "transfereeNic": "945873370V",
        "holderNameEn": "Synthetic Person",
        "holderDateOfBirth": "1994-01-01",
    },
    "title-certificate": {
        "titleCertificateNo": "00030085090",
        "cadastralMapNo": "520005",
        "parcelNo": "0020",
        "extent": "0.0153 hectares",
    },
    "form8-instrument": {
        "district": "Colombo",
        "dsDivision": "Homagama",
        "cadastralMapNo": "520005",
        "parcelNo": "0020",
        "extent": "0.0153 hectares",
        "transfereeNic": "945873370V",
        "consideration": "Rs. 4,590,000",
    },
    "survey-plan": {
        "surveyPlanNo": "2338",
        "lotNo": "17",
        "extent": "0.0153 hectares",
    },
}


class StubExtractionAdapter:
    """Implements ClassifierPort and OcrExtractorPort deterministically."""

    async def classify(self, page: PageRaster) -> ClassificationResult:
        marker_at = page.png_bytes.find(_KIND_MARKER)
        if marker_at == -1:
            return ClassificationResult(kind=OTHER_KIND, model_reported_confidence=0.1)
        rest = page.png_bytes[marker_at + len(_KIND_MARKER) :]
        kind = rest.split(b"\n", 1)[0].split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
        if get_template(kind) is None:
            return ClassificationResult(kind=OTHER_KIND, model_reported_confidence=0.1)
        return ClassificationResult(kind=kind, model_reported_confidence=0.99)

    async def extract(self, page: PageRaster, kind: str) -> ExtractionResult:
        template = get_template(kind)
        fields: dict[str, str | None] = dict.fromkeys(
            template.field_keys() if template else [], None
        )
        # Only page 1 yields values, so multi-page merging stays observable.
        if page.page_no == 1:
            fields.update(_SAMPLE_FIELDS.get(kind, {}))
        return ExtractionResult(
            fields=fields,
            transcript=f"Stub transcript for page {page.page_no} ({kind}).",
            model_reported_confidence=0.9,
        )
