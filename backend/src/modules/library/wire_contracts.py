from __future__ import annotations

import hashlib
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from src.modules.library.domain.cases import CaseCoverage, CaseRecord


class CaseWire(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )


class CaseRecordRead(CaseWire):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1)
    citation: str
    collection: Literal["LKCA", "LKSC"]
    deciding_court: str | None
    year: int = Field(ge=1700, le=2200)
    decision_date: str | None
    report_series: str | None
    source_url: str
    provenance: Literal["commonlii-parsed"]
    verification_state: Literal["parsed-unverified"]
    quality_warnings: list[
        Literal["encoding-errors", "missing-pages", "malformed-tags", "deciding-court-unparsed"]
    ]
    display_policy: Literal["metadata-only", "full-text"]
    text_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    text: str | None
    display_approval_reference: str | None

    @field_validator("source_url")
    @classmethod
    def safe_source_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Invalid source link")
        return value

    @model_validator(mode="after")
    def require_display_approval(self) -> CaseRecordRead:
        if self.display_policy == "metadata-only" and self.text is not None:
            raise ValueError("Metadata policy forbids text")
        if self.display_policy == "full-text" and (
            self.text is None or not self.display_approval_reference
        ):
            raise ValueError("Display approval is required")
        if (
            self.text is not None
            and hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256
        ):
            raise ValueError("Display checksum mismatch")
        return self

    def domain(self) -> CaseRecord:
        return CaseRecord(**self.model_dump())


class CaseCoverageRead(CaseWire):
    catalogue_records: int = Field(ge=0)
    retrieval_records: int = Field(ge=0)
    reader_overlap_records: int = Field(ge=0)
    collections: dict[str, int]
    min_year: int | None = Field(ge=1700, le=2200)
    max_year: int | None = Field(ge=1700, le=2200)
    retrieval_scope: Literal["conveyancing-only"]

    def domain(self) -> CaseCoverage:
        return CaseCoverage(**self.model_dump())
