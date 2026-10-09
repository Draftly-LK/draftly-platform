"""Document template registry — Strategy pattern for extensible extraction.

Each template declares what one document kind looks like and which particulars
it yields. The classifier prompt is generated from the registry, so adding a
template automatically extends the classifier's allowed kinds.

Field keys are the SAME keys as the frontend form contract
(``FormTemplate.fields[].factBinding`` — district, dsDivision, cadastralMapNo,
parcelNo, extent, titleCertificateNo, transferorName, …). The prescribed form
is the single contract for what gets extracted, what gates drafting, and what
renders; this registry must not invent a parallel vocabulary.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

_NULL_TOKENS = {"", "null", "none", "n/a", "unknown", "undetected"}


def normalize_field_value(value: object) -> str | None:
    """Collapse the model's many spellings of 'not readable' into None."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NULL_TOKENS:
        return None
    return text


# ── Deterministic validators ─────────────────────────────────────────────────
# These are the only confidence signal the pipeline trusts (model-reported
# confidence routes to review but never validates). None = no validator.

_NIC_RE = re.compile(r"^(?:\d{9}[VXvx]|\d{12})$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HECTARES_RE = re.compile(r"^\d+(?:\.\d+)?\s*(?:hectares?|ha)$", re.IGNORECASE)
_DIGITS_RE = re.compile(r"^\d+$")


def is_valid_nic(value: str) -> bool:
    return bool(_NIC_RE.match(value.replace(" ", "")))


def is_valid_iso_date(value: str) -> bool:
    return bool(_ISO_DATE_RE.match(value.strip()))


def is_valid_extent(value: str) -> bool:
    return bool(_HECTARES_RE.match(value.strip()))


def is_digits(value: str) -> bool:
    return bool(_DIGITS_RE.match(value.strip()))


Validator = Callable[[str], bool]


@dataclass(frozen=True)
class FieldDef:
    """One extractable particular: form-contract key + reading instruction."""

    key: str
    label: str
    validator: Validator | None = None


@dataclass(frozen=True)
class DocumentTemplate:
    """What one document kind looks like and which particulars it yields."""

    kind: str
    label: str
    classification_hint: str
    fields: tuple[FieldDef, ...] = field(default=())

    def field_keys(self) -> list[str]:
        return [f.key for f in self.fields]

    def empty_fields(self) -> dict[str, str | None]:
        return {f.key: None for f in self.fields}

    def normalize_fields(self, raw: dict[str, object]) -> dict[str, str | None]:
        out = self.empty_fields()
        for key in out:
            out[key] = normalize_field_value(raw.get(key))
        return out

    def validate_field(self, key: str, value: str) -> bool | None:
        """True/False per the field's validator; None when no validator exists."""
        for f in self.fields:
            if f.key == key:
                return f.validator(value) if f.validator else None
        return None

    def extraction_prompt(self) -> str:
        lines = "\n".join(f"- {f.key}: {f.label}" for f in self.fields)
        return (
            "You are a document extraction assistant for Sri Lankan notarial "
            "work. This page has been classified as: "
            f"{self.label}.\n\n"
            "Tasks:\n"
            "1. Transcribe all clearly readable text on the page, preserving "
            "line breaks. Sinhala text stays in Sinhala script.\n"
            "2. Extract only the fields listed below when they are clearly "
            "present ON THIS PAGE.\n\n"
            f"Fields:\n{lines}\n\n"
            "Rules:\n"
            "- Never invent values. If a field is not clearly readable on "
            "this page, return null for it.\n"
            "- Dates in ISO format YYYY-MM-DD when the printed date is "
            "unambiguous; otherwise transcribe as printed.\n"
            "- confidence is your own estimate between 0 and 1 that the "
            "extracted values are faithful to the page."
        )


# ── The v1 templates ─────────────────────────────────────────────────────────
# Keys mirror frontend/src/lib/mocks fact keys / FormTemplate factBinding.

IDENTITY_CARD = DocumentTemplate(
    kind="identity-card",
    label="Sri Lankan National Identity Card",
    classification_hint=(
        "Sri Lankan National Identity Card (NIC). Front shows photo, NIC "
        "number, name, date of birth; back shows address, date of issue, "
        "barcode or chip."
    ),
    fields=(
        FieldDef("holderNic", "NIC number", is_valid_nic),
        FieldDef("holderNameEn", "Holder full name (English)"),
        FieldDef("holderNameSi", "Holder full name (Sinhala)"),
        FieldDef("holderDateOfBirth", "Date of birth", is_valid_iso_date),
        FieldDef("holderAddress", "Residential address"),
    ),
)

TITLE_CERTIFICATE = DocumentTemplate(
    kind="title-certificate",
    label="Bim Saviya title certificate (හිමිකම් සහතිකය, RTA s.37)",
    classification_hint=(
        "Registration of Title Act certificate with the national emblem, "
        "'හිමිකම් සහතිකය' heading, cadastral map / block / parcel numbers, "
        "extent in hectares, owner schedule, and a parcel diagram."
    ),
    fields=(
        FieldDef("titleCertificateNo", "Title certificate number (හිමිකම් අංකය)"),
        FieldDef("cadastralMapNo", "Cadastral map number", is_digits),
        FieldDef("blockNo", "Block / zone number (කලාප අංකය)"),
        FieldDef("sheetNo", "Sheet number (පත්‍ර අංකය)"),
        FieldDef("parcelNo", "Parcel number (ඉඩම් කැබලි අංකය)"),
        FieldDef("extent", "Extent in hectares", is_valid_extent),
        FieldDef("district", "District"),
        FieldDef("dsDivision", "Divisional Secretary's division"),
        FieldDef("gnDivision", "Grama Niladhari division"),
        FieldDef("classOfTitle", "Class of title (first/second)"),
        FieldDef("ownerName", "Registered owner full name"),
        FieldDef("placeOfRegistration", "Title registry office"),
    ),
)

FORM8_INSTRUMENT = DocumentTemplate(
    kind="form8-instrument",
    label="RTA Form 8 — Instrument of Transfer (s.43)",
    classification_hint=(
        "Prescribed 'Form 8' / 'Instrument of Transfer' under the "
        "Registration of Title Act No. 21 of 1998, with an office-use "
        "registration box, numbered land-parcel particulars, transferor and "
        "transferee sections, consideration, and notary attestation."
    ),
    fields=(
        FieldDef("district", "1(a) District"),
        FieldDef("dsDivision", "1(b) Divisional Secretary's division"),
        FieldDef("gnDivision", "1(c) Grama Niladhari division"),
        FieldDef("village", "1(d) Village or town"),
        FieldDef("assessmentNumber", "1(f) Assessment number"),
        FieldDef("cadastralMapNo", "1(g) Cadastral map number", is_digits),
        FieldDef("blockNo", "1(h) Block number"),
        FieldDef("sheetNo", "1(i) Sheet number"),
        FieldDef("parcelNo", "1(j) Parcel number"),
        FieldDef("extent", "1(l) Extent in hectares", is_valid_extent),
        FieldDef("extentSubjectToTransfer", "1(m) Extent subject to the transfer"),
        FieldDef("placeOfRegistration", "2(a) Place of registration"),
        FieldDef("titleCertificateNo", "2(b) Title certificate number"),
        FieldDef("classOfTitle", "2(c) Class of title"),
        FieldDef("transferorName", "3(a) Transferor full name"),
        FieldDef("transferorNic", "3(b) Transferor NIC number", is_valid_nic),
        FieldDef("transferorAddress", "3(c) Transferor address"),
        FieldDef("transfereeName", "4(a) Transferee full name"),
        FieldDef("transfereeNic", "4(b) Transferee NIC number", is_valid_nic),
        FieldDef("transfereeAddress", "4(c) Transferee address"),
        FieldDef("consideration", "5(a) Consideration in figures"),
        FieldDef("considerationWords", "5(b) Consideration in words"),
        FieldDef("notaryName", "Attesting notary full name"),
        FieldDef("notaryCode", "Notary's code"),
    ),
)

SURVEY_PLAN = DocumentTemplate(
    kind="survey-plan",
    label="Licensed surveyor's plan / lot extract",
    classification_hint=(
        "Survey plan by a Registered Licensed Surveyor: plan number, land "
        "name, lot numbers with extents, scale (e.g. 1:1000), boundary "
        "table (North/East/South/West by), surveyor signature."
    ),
    fields=(
        FieldDef("surveyPlanNo", "Plan number"),
        FieldDef("surveyorName", "Licensed surveyor's name"),
        FieldDef("surveyorRegistration", "Surveyor registration number"),
        FieldDef("landName", "Name of the land"),
        FieldDef("lotNo", "Lot number shown in this extract"),
        FieldDef("extent", "Lot extent in hectares", is_valid_extent),
        FieldDef("boundaryNorth", "Boundary — north by"),
        FieldDef("boundaryEast", "Boundary — east by"),
        FieldDef("boundarySouth", "Boundary — south by"),
        FieldDef("boundaryWest", "Boundary — west by"),
    ),
)

_TEMPLATES: dict[str, DocumentTemplate] = {
    template.kind: template
    for template in (IDENTITY_CARD, TITLE_CERTIFICATE, FORM8_INSTRUMENT, SURVEY_PLAN)
}

#: Classification result for anything the registry does not know.
OTHER_KIND = "other"

#: Transcription-only template for the EXTRACTION_SEND_ALL override.
#:
#: Deliberately NOT in ``_TEMPLATES``: it must not appear in the classifier's
#: allowed kinds, and ``get_template`` must keep returning None for an
#: unregistered kind so the default pipeline still routes to manual_review.
#: It declares no fields, so the extractor transcribes the page and there is
#: no field vocabulary for the model to fill in — an unknown document can
#: yield readable text but never a candidate particular.
_GENERIC_DOCUMENT = DocumentTemplate(
    kind=OTHER_KIND,
    label="Document of a kind this release does not model",
    classification_hint="not used — this template is never offered to the classifier",
    fields=(),
)


def registered_kinds() -> list[str]:
    return sorted(_TEMPLATES)


def get_template(kind: str) -> DocumentTemplate | None:
    return _TEMPLATES.get(kind)


def generic_template() -> DocumentTemplate:
    """The transcription-only template used by the send-all override."""
    return _GENERIC_DOCUMENT


def resolve_extraction_template(kind: str) -> DocumentTemplate | None:
    """The template an extractor should read a page with.

    Separate from ``get_template``, which answers the policy question "does
    this release model this kind?" and must keep returning None for
    ``OTHER_KIND``. This answers the narrower question an adapter asks once the
    service has already decided to read the page, so ``OTHER_KIND`` resolves to
    the transcription-only fallback. Any other unrecognised kind is still None,
    and the adapter refuses it.
    """
    if kind == OTHER_KIND:
        return _GENERIC_DOCUMENT
    return _TEMPLATES.get(kind)


def observational_field_key(document_type_id: str, field_key: str) -> str:
    """Legacy NIC extraction observed its holder, never a transaction role."""
    return (
        "holderNic"
        if document_type_id == "rta.doc.nic" and field_key == "transfereeNic"
        else field_key
    )


def classification_prompt() -> str:
    """Classifier prompt generated from the registry, so adding a template
    automatically extends the allowed kinds."""
    hints = "\n".join(
        f'- "{template.kind}": {template.classification_hint}' for template in _TEMPLATES.values()
    )
    kinds = ", ".join(f'"{kind}"' for kind in [*registered_kinds(), OTHER_KIND])
    return (
        "You classify one page of a Sri Lankan conveyancing document.\n\n"
        f"Known document kinds:\n{hints}\n"
        f'- "{OTHER_KIND}": anything else, or too unclear to tell.\n\n'
        f"Answer with kind (one of {kinds}) and confidence (your own "
        "estimate between 0 and 1). When unsure, answer "
        f'"{OTHER_KIND}" with low confidence — never guess.'
    )
