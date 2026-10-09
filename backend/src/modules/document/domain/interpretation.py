"""Pinned cached OCR input for a corrected document, independent of its upload run."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InterpretationPage:
    source_file_id: str
    page_number: int
    page_id: str
    quality_status: str
    image_ref: tuple[str, str]
    text_ref: tuple[str, str]
