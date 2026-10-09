"""Page accounting never infers review from an absent document group."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.modules.document.domain.ingestion import DocumentFragment, SourceFile


@dataclass(frozen=True)
class PageDisposition:
    id: str
    user_id: str
    matter_id: str
    source_file_id: str
    page_number: int
    disposition: str
    reason: str
    actor_id: str
    source_version: int
    created_at: datetime


@dataclass(frozen=True)
class PageAccounting:
    source_file_id: str
    page_count: int | None
    unclaimed_page_numbers: tuple[int, ...]
    overlapping_page_numbers: tuple[int, ...]
    blank_page_numbers: tuple[int, ...]
    unsupported_page_numbers: tuple[int, ...]
    out_of_bounds_page_numbers: tuple[int, ...] = ()

    @property
    def complete(self) -> bool:
        return (
            self.page_count is not None
            and self.page_count > 0
            and not (
                self.unclaimed_page_numbers
                or self.overlapping_page_numbers
                or self.out_of_bounds_page_numbers
            )
        )

    @property
    def manual_review_required(self) -> bool:
        return not self.complete or bool(self.unsupported_page_numbers)


def account_pages(
    sources: Sequence[SourceFile],
    fragments: Sequence[DocumentFragment],
    dispositions: Sequence[PageDisposition],
) -> tuple[PageAccounting, ...]:
    result = []
    for source in sources:
        if source.superseded_by_source_file_id:
            continue
        claims: dict[int, int] = {}
        for fragment in fragments:
            if fragment.source_file_id == source.id:
                for page in range(fragment.page_start, fragment.page_end + 1):
                    claims[page] = claims.get(page, 0) + 1
        marked = {
            item.page_number: item.disposition
            for item in dispositions
            if item.source_file_id == source.id and item.disposition != "review_required"
        }
        for page in marked:
            claims[page] = claims.get(page, 0) + 1
        result.append(
            PageAccounting(
                source.id,
                source.page_count,
                tuple(
                    page for page in range(1, (source.page_count or 0) + 1) if page not in claims
                ),
                tuple(sorted(page for page, count in claims.items() if count > 1)),
                tuple(sorted(page for page, kind in marked.items() if kind == "blank")),
                tuple(sorted(page for page, kind in marked.items() if kind == "unsupported")),
                tuple(
                    sorted(
                        page
                        for page in claims
                        if page < 1 or (source.page_count is not None and page > source.page_count)
                    )
                ),
            )
        )
    return tuple(result)
