from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.platform.errors import DraftlyError


class CaseCorpusUnavailableError(DraftlyError):
    code = "case_corpus_unavailable"
    http_status = 503
    message = "The case corpus is temporarily unavailable."


@dataclass(frozen=True)
class CaseRecord:
    id: str
    title: str
    citation: str
    collection: Literal["LKCA", "LKSC"]
    deciding_court: str | None
    year: int
    decision_date: str | None
    report_series: str | None
    source_url: str
    provenance: Literal["commonlii-parsed"] = "commonlii-parsed"
    verification_state: Literal["parsed-unverified"] = "parsed-unverified"
    quality_warnings: list[str] = field(default_factory=list)
    display_policy: Literal["metadata-only", "full-text"] = "metadata-only"
    text_sha256: str = ""
    text: str | None = None
    display_approval_reference: str | None = None


@dataclass(frozen=True)
class CaseCoverage:
    catalogue_records: int
    retrieval_records: int
    reader_overlap_records: int
    collections: dict[str, int]
    min_year: int | None
    max_year: int | None
    retrieval_scope: Literal["conveyancing-only"] = "conveyancing-only"


@dataclass(frozen=True)
class CaseList:
    corpus_version: str
    coverage: CaseCoverage
    items: list[CaseRecord]
    has_more: bool


@dataclass(frozen=True)
class CaseDetail:
    corpus_version: str
    coverage: CaseCoverage
    item: CaseRecord


@dataclass(frozen=True)
class CaseFilters:
    query: str | None = None
    collection: Literal["LKCA", "LKSC"] | None = None
    court: str | None = None
    year: int | None = None
