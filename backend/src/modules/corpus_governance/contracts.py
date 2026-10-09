"""Read-only authority metadata; no source bytes or permission-changing commands."""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol


@dataclass(frozen=True)
class AuthorityRelationship:
    relation: Literal["amends", "supersedes", "made-under", "commences"]
    target_source_id: str
    target_reference: str | None
    supporting_page: int | None
    review_state: Literal["unreviewed", "reviewed"]


@dataclass(frozen=True)
class AuthorityMetadata:
    source_id: str
    title: str
    reference: str
    kind: Literal["statute", "amendment", "gazette"]
    source_url: str
    source_sha256: str
    publication_date: date | None
    effective_from: date | None
    effective_to: date | None
    commencement_known: bool
    commencement_source_id: str | None
    commencement_page: int | None
    relationships: tuple[AuthorityRelationship, ...]
    release_version: str
    review_state: str
    currency_status: Literal["current", "superseded", "reverify", "unknown"]


class LegalAuthorityReadPort(Protocol):
    async def authorities(
        self, source_ids: tuple[str, ...], *, release_version: str
    ) -> tuple[AuthorityMetadata, ...]: ...

    async def related(
        self, source_ids: tuple[str, ...], *, release_version: str
    ) -> tuple[AuthorityMetadata, ...]: ...


class ReleaseUnavailableError(ValueError):
    """The requested audience/release cannot supply trusted metadata."""


class ReleaseIntegrityError(ReleaseUnavailableError):
    """Signed metadata, source bytes, or contained paths failed validation."""


class PublicationDenied(ReleaseUnavailableError):  # noqa: N818 - name from the governance contract
    """An exact source/use approval is absent or inapplicable."""
