from dataclasses import dataclass
from typing import Literal

from src.modules.library.contracts import CaseCoverage, CaseRecord


@dataclass(frozen=True)
class SimilarCase:
    case: CaseRecord | None
    id: str
    title: str
    citation: str
    source_url: str
    score: float
    matched_signals: list[Literal["lexical", "graph", "dense"]]
    reader_available: bool
    excerpt: str


@dataclass(frozen=True)
class CaseSearchResult:
    corpus_version: str
    coverage: CaseCoverage
    items: list[SimilarCase]
    outcome: Literal["similar_cases_found", "no_similar_cases"]
    degraded_channels: list[Literal["dense"]]
    dense_status: Literal["disabled", "unavailable", "enabled-status-unknown"]
