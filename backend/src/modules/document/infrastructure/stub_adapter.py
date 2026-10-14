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

#: Deterministic sample values per kind — obviously synthetic. None of them may
#: echo a real matter's identifiers (map, parcel, certificate, plan, amount, NIC),
#: because these values are shown on screen in recorded demos.
_SAMPLE_FIELDS: dict[str, dict[str, str | None]] = {
    "identity-card": {
        "transfereeNic": "900010002V",
        "holderNameEn": "Synthetic Person",
        "holderDateOfBirth": "1990-01-01",
    },
    "title-certificate": {
        "titleCertificateNo": "00099900001",
        "cadastralMapNo": "900001",
        "parcelNo": "0099",
        "extent": "0.0250 hectares",
    },
    "form8-instrument": {
        "district": "Colombo",
        "dsDivision": "Synthetic DS Division",
        "cadastralMapNo": "900001",
        "parcelNo": "0099",
        "extent": "0.0250 hectares",
        "transfereeNic": "900010002V",
        "consideration": "Rs. 1,000,000",
    },
    "survey-plan": {
        "surveyPlanNo": "9001",
        "lotNo": "7",
        "extent": "0.0250 hectares",
    },
}


#: Shared with the V1 stand-in (:mod:`vision_stub_adapter`) so both stubs read the same marker and values.
KIND_MARKER = _KIND_MARKER
SAMPLE_FIELDS = _SAMPLE_FIELDS


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
