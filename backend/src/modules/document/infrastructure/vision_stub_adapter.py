"""Deterministic stand-ins for the V1 (Vision OCR + Gemini) pipeline, local/test only.

``EXTRACTION_PROVIDER=vision-stub`` runs the real V1 pipeline (rasterise, OCR,
page classification, logical documents, structured extraction) with these
adapters in place of Cloud Vision and Gemini. Nothing leaves the machine, and
bootstrap refuses this provider outside the stub environments, exactly as it
refuses ``stub``.

Like :mod:`stub_adapter`, it is steered by a marker in the page bytes
(``STUB-KIND:form8-instrument``). An image upload keeps its bytes, so a PNG
carrying the marker in a text chunk is recognised; a rendered PDF page is not,
and lands as ``other`` for the lawyer to classify. Values are one invented,
internally consistent transaction (``V1_SAMPLE_FIELDS``) built on the legacy
stub's samples, complete enough that the generated form can be approved.
"""

from __future__ import annotations

from src.modules.document.domain.registry import OTHER_KIND, get_template
from src.modules.document.domain.v1 import (
    DetectedLanguage,
    ExtractedCandidate,
    OcrElement,
    OcrPage,
    PageClassification,
    Point,
)
from src.modules.document.infrastructure.matter_document_types import template_kind_for_class
from src.modules.document.infrastructure.stub_adapter import KIND_MARKER, SAMPLE_FIELDS
from src.modules.document.ports import (
    ClassificationPageInput,
    ExtractionFieldSchema,
    PageRaster,
)

_ENGLISH = (DetectedLanguage(code="en", confidence=0.99),)

#: One synthetic transaction, consistent across all four documents, so a local
#: matter can run from upload to an approvable form. Every value is invented and
#: labelled as such; the legacy stub's samples are kept as the base.
_PARCEL = {
    "district": "Colombo",
    "dsDivision": "Synthetic DS Division",
    "gnDivision": "Synthetic GN Division 000",
    "village": "Synthetic Village",
    "assessmentNumber": "SYN-ASSESS-0001",
    "cadastralMapNo": "900001",
    "blockNo": "09",
    "sheetNo": "01",
    "parcelNo": "0099",
    "extent": "0.0250 hectares",
    "extentSubjectToTransfer": "0.0250 hectares",
    "placeOfRegistration": "Synthetic Land Registry",
    "titleCertificateNo": "00099900001",
    "classOfTitle": "FIRST_CLASS",
}
V1_SAMPLE_FIELDS: dict[str, dict[str, str]] = {
    "identity-card": {
        **{k: v for k, v in SAMPLE_FIELDS["identity-card"].items() if v},
        "holderNameEn": "Synthetic Transferee Two",
        "holderAddress": "1 Synthetic Lane, Synthetic Town",
    },
    "title-certificate": {**_PARCEL, "ownerName": "Synthetic Transferor One"},
    "form8-instrument": {
        **_PARCEL,
        "transferorName": "Synthetic Transferor One",
        "transferorNic": "800000001V",
        "transferorAddress": "2 Synthetic Road, Synthetic City",
        "transfereeName": "Synthetic Transferee Two",
        "transfereeNic": "900010002V",
        "transfereeAddress": "1 Synthetic Lane, Synthetic Town",
        "consideration": "Rs. 1,000,000",
        "considerationWords": "Rupees one million",
        "notaryName": "Synthetic Notary Public",
        "notaryCode": "SYN-NP-0001",
    },
    "survey-plan": {
        **{k: v for k, v in SAMPLE_FIELDS["survey-plan"].items() if v},
        "surveyorName": "Synthetic Licensed Surveyor",
        "landName": "Synthetic Land",
        "boundaryNorth": "Synthetic road",
        "boundaryEast": "Synthetic lot 8",
        "boundarySouth": "Synthetic stream",
        "boundaryWest": "Synthetic lot 6",
    },
}
_RECOGNISED_CONFIDENCE = 0.97
_UNRECOGNISED_CONFIDENCE = 0.1


def _marker_kind(data: bytes) -> str | None:
    at = data.find(KIND_MARKER)
    if at == -1:
        return None
    rest = data[at + len(KIND_MARKER) :]
    kind = rest.split(b"\n", 1)[0].split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
    return kind if get_template(kind) is not None else None


def _text_kind(text: str) -> str | None:
    return _marker_kind(text.encode("ascii", "ignore"))


def _words(tokens: list[str]) -> tuple[OcrElement, ...]:
    """Horizontal, confident words in reading order, so quality and rotation read as normal."""
    elements: list[OcrElement] = []
    x = 40.0
    for order, token in enumerate(tokens):
        width = 12.0 * max(len(token), 1)
        elements.append(
            OcrElement(
                level="word",
                text=token,
                confidence=0.95,
                detected_languages=_ENGLISH,
                polygon=(Point(x, 40), Point(x + width, 40), Point(x + width, 60), Point(x, 60)),
                reading_order=order,
            )
        )
        x += width + 8
    return tuple(elements)


class VisionStubAdapter:
    """Implements VisionOcrPort, BatchPageClassifierPort and StructuredDocumentExtractorPort."""

    async def document_text_detection(self, page: PageRaster) -> OcrPage:
        kind = _marker_kind(page.png_bytes)
        tokens = ["SYNTHETIC", "local", "test", "page", str(page.page_no)]
        if kind:
            template = get_template(kind)
            label = template.label if template else kind
            tokens += label.split()[:8] + ["not", "a", "real", "record", f"STUB-KIND:{kind}"]
        else:
            tokens += ["no", "test", "marker", "found", "classify", "this", "page", "by", "hand"]
        text = " ".join(tokens)
        return OcrPage(text=text, detected_languages=_ENGLISH, elements=_words(tokens))

    async def classify_pages(
        self,
        pages: list[ClassificationPageInput],
        *,
        allowed_type_ids: tuple[str, ...],
        text_limit: int | None,
    ) -> list[PageClassification]:
        del text_limit  # Nothing is sent anywhere; the whole text is already local.
        results: list[PageClassification] = []
        previous: str | None = None
        for page in pages:
            kind = _text_kind(page.text)
            type_id = next(
                (
                    class_id
                    for class_id in allowed_type_ids
                    if kind and template_kind_for_class(class_id) == kind
                ),
                OTHER_KIND,
            )
            template = get_template(kind) if kind else None
            results.append(
                PageClassification(
                    page_no=page.page_no,
                    type_id=type_id,
                    suggested_name=template.label if template and type_id != OTHER_KIND else None,
                    starts_new_document=type_id != previous,
                    model_reported_confidence=(
                        _RECOGNISED_CONFIDENCE
                        if type_id != OTHER_KIND
                        else _UNRECOGNISED_CONFIDENCE
                    ),
                )
            )
            previous = type_id
        return results

    async def extract_document(
        self,
        *,
        type_id: str,
        text: str,
        page_numbers: tuple[int, ...],
        fields: tuple[ExtractionFieldSchema, ...],
    ) -> tuple[ExtractedCandidate, ...]:
        del text
        samples = V1_SAMPLE_FIELDS.get(template_kind_for_class(type_id) or "", {})
        return tuple(
            ExtractedCandidate(
                key=field.key,
                value=value,
                page_no=page_numbers[0],
                model_reported_confidence=0.9,
            )
            for field in fields
            if (value := samples.get(field.key))
        )
