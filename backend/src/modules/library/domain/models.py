from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AuthorityType = Literal["statute", "amendment"]
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
