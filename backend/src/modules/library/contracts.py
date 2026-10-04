"""Public case catalogue DTOs and read port; no storage access crosses this boundary."""

from typing import Protocol

from src.modules.library.domain.cases import (
    CaseCorpusUnavailableError,
    CaseCoverage,
    CaseDetail,
    CaseFilters,
    CaseList,
    CaseRecord,
)

__all__ = [
    "CaseCataloguePort",
    "CaseCorpusUnavailableError",
    "CaseCoverage",
    "CaseDetail",
    "CaseFilters",
    "CaseList",
    "CaseRecord",
]


class CaseCataloguePort(Protocol):
    async def list_cases(
        self,
        filters: CaseFilters,
        *,
        limit: int,
        after_id: str | None = None,
        after_year: int | None = None,
    ) -> CaseList: ...
    async def get_case(self, case_id: str, *, actor_id: str) -> CaseDetail | None: ...
