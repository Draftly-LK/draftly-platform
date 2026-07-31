"""Document template registry — Strategy pattern for extensible extractors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


KNOWN_KINDS = ("identity", "other")


@dataclass(frozen=True)
class FieldDef:
    key: str
    label_en: str


class DocumentTemplate(Protocol):
    kind: str
    label: str
    fields: list[FieldDef]

    def classification_hint(self) -> str: ...

    def extract_prompt(self) -> str: ...

    def empty_fields(self) -> dict[str, str | None]: ...

    def normalize_fields(self, raw: dict[str, Any]) -> dict[str, str | None]: ...


@dataclass
class IdentityCardTemplate:
    kind: str = "identity"
    label: str = "Sri Lankan National Identity Card"
    fields: list[FieldDef] = field(
        default_factory=lambda: [
            FieldDef("nicNumber", "NIC number"),
            FieldDef("nameSi", "Name (Sinhala)"),
            FieldDef("nameEn", "Name (English)"),
            FieldDef("sex", "Sex"),
            FieldDef("dateOfBirth", "Date of birth"),
            FieldDef("addressEn", "Address (English)"),
            FieldDef("serialNumber", "Serial / document number"),
            FieldDef("dateOfIssue", "Date of issue"),
            FieldDef("placeOfBirthEn", "Place of birth (English)"),
        ]
    )

    def classification_hint(self) -> str:
        return (
            "Sri Lankan National Identity Card (NIC / identity card). "
            "Front usually shows photo, NIC number, name, sex, date of birth. "
            "Back usually shows place of birth, date of issue, address, barcode/chip."
        )

    def empty_fields(self) -> dict[str, str | None]:
        return {f.key: None for f in self.fields}

    def normalize_fields(self, raw: dict[str, Any]) -> dict[str, str | None]:
        out = self.empty_fields()
        for key in out:
            value = raw.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.lower() in {
                "null",
                "none",
                "n/a",
                "unknown",
                "undetected",
            }:
                out[key] = None
            else:
                out[key] = text
        return out

    def extract_prompt(self) -> str:
        keys = ", ".join(f.key for f in self.fields)
        return f"""You are a document extraction assistant for Sri Lankan notarial work.

The image has already been classified as a Sri Lankan National Identity Card.

Task:
1. Decide whether the visible side is "front" or "back" (or "unknown").
   - Front usually shows photo, NIC number, name, sex, date of birth.
   - Back usually shows place of birth, date of issue, address, barcode/chip.
2. Transcribe all clearly readable text directly from the image, preserving line breaks.
3. Extract only these fields when clearly present: {keys}.
4. Never invent values. If a field is not clearly readable, return null.

Respond with JSON only, no markdown:
{{
  "side": "front" | "back" | "unknown",
  "confidence": number between 0 and 1,
  "extracted_text": string,
  "fields": {{
    "nicNumber": string | null,
    "nameSi": string | null,
    "nameEn": string | null,
    "sex": string | null,
    "dateOfBirth": string | null,
    "addressEn": string | null,
    "serialNumber": string | null,
    "dateOfIssue": string | null,
    "placeOfBirthEn": string | null
  }}
}}
"""


_TEMPLATES: dict[str, DocumentTemplate] = {
    "identity": IdentityCardTemplate(),
}


def registered_kinds() -> list[str]:
    return list(_TEMPLATES.keys())


def get_template(kind: str) -> DocumentTemplate | None:
    return _TEMPLATES.get(kind)


def identity_template() -> IdentityCardTemplate:
    return IdentityCardTemplate()


def classification_prompt() -> str:
    """Build the classifier prompt from registered templates only."""
    lines: list[str] = []
    for kind in registered_kinds():
        template = _TEMPLATES[kind]
        lines.append(f'- "{kind}": {template.classification_hint()}')
    kinds_list = ", ".join(f'"{k}"' for k in [*registered_kinds(), "other"])
    return f"""You are a document classifier for Sri Lankan notarial work.

Decide which predefined document type best matches this image.

Registered types:
{chr(10).join(lines)}

If the image does not clearly match a registered type, return "other".

Also decide the identity card side when kind is "identity":
- "front", "back", or "unknown"
For non-identity kinds, side must be "unknown".

Respond with JSON only, no markdown:
{{
  "kind": {kinds_list},
  "side": "front" | "back" | "unknown",
  "confidence": number between 0 and 1
}}
"""


def side_from_filename(filename: str | None) -> str:
    """Prefer explicit front/back filename hints (e.g. nic1f / nic2b)."""
    import re

    if not filename:
        return "unknown"
    base = filename.lower().rsplit(".", 1)[0]
    if re.search(r"nic\d*f(?:ront)?$", base) or re.search(r"\bfront\b", base):
        return "front"
    if re.search(r"nic\d*b(?:ack)?$", base) or re.search(r"\bback\b", base):
        return "back"
    return "unknown"
