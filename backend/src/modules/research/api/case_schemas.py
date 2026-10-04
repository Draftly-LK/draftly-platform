from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from src.modules.library.api.case_schemas import CaseCoverageRead, CaseRecordRead, CaseWire
from src.modules.research.domain.cases import CaseSearchResult, SimilarCase


class CaseSearchRequest(CaseWire):
    query: str = Field(min_length=1, max_length=8000)
    limit: int = Field(default=8, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A fact pattern is required")
        return value


class SimilarCaseRead(CaseWire):
    case: CaseRecordRead | None
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1)
    citation: str
    source_url: str
    score: float = Field(ge=0, allow_inf_nan=False)
    matched_signals: list[Literal["lexical", "graph", "dense"]]
    reader_available: bool
    excerpt: str = Field(max_length=900)

    @field_validator("source_url")
    @classmethod
    def safe_source_url(cls, value: str) -> str:
        return CaseRecordRead.safe_source_url(value)

    @model_validator(mode="after")
    def corroborated(self) -> SimilarCaseRead:
        if not set(self.matched_signals) & {"lexical", "graph"}:
            raise ValueError("Uncorroborated search hit")
        if self.reader_available != (self.case is not None):
            raise ValueError("Reader membership mismatch")
        if self.case is not None and (self.case.id != self.id or self.case.text is not None):
            raise ValueError("Invalid search projection")
        return self

    def domain(self) -> SimilarCase:
        return SimilarCase(
            case=self.case.domain() if self.case else None, **self.model_dump(exclude={"case"})
        )


class CaseSearchRead(CaseWire):
    corpus_version: str = Field(min_length=1)
    coverage: CaseCoverageRead
    items: list[SimilarCaseRead]
    outcome: Literal["similar_cases_found", "no_similar_cases"]
    degraded_channels: list[Literal["dense"]]
    dense_status: Literal["disabled", "unavailable", "enabled-status-unknown"]

    @model_validator(mode="after")
    def truthful_outcome(self) -> CaseSearchRead:
        if bool(self.items) != (self.outcome == "similar_cases_found"):
            raise ValueError("Search outcome mismatch")
        return self

    def domain(self) -> CaseSearchResult:
        return CaseSearchResult(
            self.corpus_version,
            self.coverage.domain(),
            [row.domain() for row in self.items],
            self.outcome,
            self.degraded_channels,
            self.dense_status,
        )
