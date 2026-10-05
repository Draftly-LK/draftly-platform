from __future__ import annotations

from pydantic import Field

from src.modules.library.contracts import CaseCoverageRead, CaseRecordRead, CaseWire
from src.modules.library.domain.cases import CaseDetail, CaseList
from src.platform.api.pagination import PageInfo


class InternalCaseListRead(CaseWire):
    corpus_version: str = Field(min_length=1)
    coverage: CaseCoverageRead
    items: list[CaseRecordRead]
    has_more: bool

    def domain(self) -> CaseList:
        return CaseList(
            self.corpus_version,
            self.coverage.domain(),
            [row.domain() for row in self.items],
            self.has_more,
        )


class CaseListRead(CaseWire):
    corpus_version: str
    coverage: CaseCoverageRead
    items: list[CaseRecordRead]
    page: PageInfo


class CaseDetailRead(CaseWire):
    corpus_version: str = Field(min_length=1)
    coverage: CaseCoverageRead
    item: CaseRecordRead

    def domain(self) -> CaseDetail:
        return CaseDetail(self.corpus_version, self.coverage.domain(), self.item.domain())
