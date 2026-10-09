from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.modules.corpus_governance.contracts import AuthorityMetadata

AuthorityType = Literal["statute", "amendment", "gazette"]
AuthorityWeight = Literal["binding", "unverified-candidate"]


@dataclass(frozen=True)
class LegalSourceSummary:
    id: str
    title: str
    reference: str
    type: AuthorityType
    weight: AuthorityWeight
    verified: bool
    section_count: int
    source_url: str
    extraction_confidence: str
    corpus_version: str
    metadata: AuthorityMetadata | None = None
