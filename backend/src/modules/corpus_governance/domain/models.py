"""Immutable source approvals and audience-specific release records."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.modules.corpus_governance.contracts import AuthorityMetadata

type CorpusAudience = Literal["internal-research", "public-catalogue"]
type ProvenanceStatus = Literal[
    "verified-official", "verified-licensed", "verified-public-domain", "unverified"
]
type RightsStatus = Literal["official-text", "licensed", "public-domain", "restricted", "unknown"]
type SourceUseClass = Literal["public-catalogue", "restricted-internal-research", "quarantined"]
type IndexingPolicy = Literal["full-text", "metadata-only", "blocked"]
type DisplayPolicy = Literal["full-text", "snippet-only", "metadata-only", "link-out", "blocked"]
type QuotationPolicy = Literal["approved-span", "short-quotation-only", "blocked"]
type DownloadPolicy = Literal["source-file", "link-to-official-source", "blocked"]


@dataclass(frozen=True)
class ReviewApproval:
    reference: str
    reviewed_by: str
    reviewed_at: datetime


@dataclass(frozen=True)
class SourceInput:
    path: str
    sha256: str


@dataclass(frozen=True)
class ContentApproval:
    decision: ReviewApproval
    source_sha256: str
    indexed_sha256: str | None


@dataclass(frozen=True)
class AudiencePolicy:
    audience: CorpusAudience
    indexing: IndexingPolicy
    display: DisplayPolicy
    quotation: QuotationPolicy
    download: DownloadPolicy
    approval: ReviewApproval


@dataclass(frozen=True)
class LegalSource:
    metadata: AuthorityMetadata
    original: SourceInput
    indexed: SourceInput | None
    publication_body: str
    source_publisher: str
    language: str
    retrieved_at: datetime
    official_text: bool
    official_translation: bool
    provenance_status: ProvenanceStatus
    rights_status: RightsStatus
    source_use_class: SourceUseClass
    licence_reference: str | None
    rights_approval: ReviewApproval
    content_approval: ContentApproval
    policy: AudiencePolicy


@dataclass(frozen=True)
class ReleasedSource:
    source: LegalSource
    # Builders consume these checked immutable bytes, never reopen a listed path.
    indexed_content: bytes | None


@dataclass(frozen=True)
class ValidatedRelease:
    release_version: str
    audience: CorpusAudience
    sources: tuple[ReleasedSource, ...]
