"""In-memory doubles and synthetic fixtures for the check module's tests.

No database. The repository double keeps the two behaviours the real one has
that the tests depend on: results are append-only, and `update_issue` is
optimistic and hands back a copy rather than the caller's own object.

Every value in `CLEAN_TRANSFER` is invented. No real party, NIC, deed, parcel,
or registry reference appears anywhere in this module.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from src.modules.check.domain.errors import LegalIssueStaleError
from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.check.domain.runners import CheckEvaluation
from src.modules.content_governance.contracts import (
    DispositionScope,
    DisputeStage,
    IssueSeverity,
    IssueState,
)
from src.modules.verification.contracts import FactTierSummary

#: A fully evidenced whole-parcel transfer between two invented natural persons,
#: on which every implemented check either passes or does not apply.
CLEAN_TRANSFER: dict[str, Any] = {
    "rta.regime.coverage_confirmed": True,
    "rta.instrument.disposition_scope": DispositionScope.WHOLE_REGISTERED_PARCEL.value,
    "rta.instrument.attestation_date": "2026-08-14",
    "rta.title.certificate_no": "SYNTHETIC-TC-0001",
    "rta.title.class": "FIRST_CLASS",
    "rta.title.place_of_registration": "Synthetic Land Registry",
    "rta.title.registered_owner_name": "Synthetic Seller One",
    "rta.title.register_search_datetime": "2026-08-15",
    "rta.parcel.district": "Synthetic District",
    "rta.parcel.ds_division": "Synthetic DS Division",
    "rta.parcel.gn_division": "Synthetic GN Division",
    "rta.parcel.village": "Synthetic Village",
    "rta.parcel.cadastral_map_number": "SYN-000000",
    "rta.parcel.block_number": "01",
    "rta.parcel.sheet_number": "02",
    "rta.parcel.parcel_number": "0003",
    "rta.parcel.extent": "0.0500 ha",
    "rta.parcel.extent_subject_to_transaction": "0.0500 ha",
    "rta.party.transferor_name": "Synthetic Seller One",
    "rta.party.transferor_nic": "SYNTHETIC-NIC-A",
    "rta.party.transferor_address": "1 Synthetic Road",
    "rta.party.transferee_name": "Synthetic Buyer Two",
    "rta.party.transferee_nic": "SYNTHETIC-NIC-B",
    "rta.party.transferee_address": "2 Synthetic Road",
    "rta.party.capacity_confirmed": True,
    "rta.party.signing_authority": "Signs in person",
    "rta.party.all_natural_persons": True,
    "rta.party.transferor_is_registered_owner": True,
    "rta.party.coowners_present": False,
    "rta.party.creates_coownership": False,
    "rta.interest.mortgage_status": "NOT_FOUND_IN_CURRENT_SEARCH",
    "rta.interest.lease_status": "NOT_FOUND_IN_CURRENT_SEARCH",
    "rta.interest.occupation_status": "OWNER_OCCUPIED",
    "rta.interest.caveat_or_notice_status": "NOT_FOUND_IN_CURRENT_SEARCH",
    "rta.process.dispute_stage": DisputeStage.NO_INDICIA_FOUND.value,
    "rta.local.assessment_register_name": "Synthetic Seller One",
    "rta.local.local_authority_id": "lk.lg.synthetic",
}


def issue_from(evaluation: CheckEvaluation, *, issue_id: str = "iss_synthetic") -> LegalIssue:
    """The issue a run would open for this evaluation, without the service.

    Mirrors `CheckService._create_issue` so a runner test can assert what the
    §7.3 gates make of a result without standing up the whole service.
    """
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    return LegalIssue(
        id=issue_id,
        user_id="usr_synthetic",
        matter_id="mat_synthetic",
        issue_type_id=evaluation.issue_type_id,
        severity=evaluation.default_severity,
        blocker_kind=evaluation.blocker_kind,
        state=IssueState.OPEN,
        summary_key=f"{evaluation.issue_type_id}.summary",
        created_at=now,
        updated_at=now,
        source_record_ids=evaluation.source_record_ids,
        evidence_reference_ids=evaluation.evidence_reference_ids,
    )


class FakeCheckRepository:
    """Implements ``CheckRepository`` in memory."""

    def __init__(self) -> None:
        self.results: list[CheckResult] = []
        self.issues: dict[str, LegalIssue] = {}

    async def create_results(self, results: list[CheckResult]) -> list[CheckResult]:
        self.results.extend(results)
        return results

    async def stale_input_result_ids(self, user_id: str, matter_id: str) -> tuple[str, ...]:
        return ()

    async def list_results(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[CheckResult], str | None]:
        matching = [
            result
            for result in reversed(self.results)
            if result.user_id == user_id and result.matter_id == matter_id
        ]
        return matching[:limit], None

    async def create_issue(self, issue: LegalIssue) -> LegalIssue:
        self.issues[issue.id] = issue
        return replace(issue)

    async def get_issue(self, user_id: str, issue_id: str) -> LegalIssue | None:
        issue = self.issues.get(issue_id)
        if issue is None or issue.user_id != user_id:
            return None
        return replace(issue)

    async def list_issues(
        self,
        user_id: str,
        matter_id: str,
        *,
        severity: IssueSeverity | None,
        state: IssueState | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[LegalIssue], str | None]:
        matching = [
            issue
            for issue in await self.list_all_issues(user_id, matter_id)
            if (severity is None or issue.severity is severity)
            and (state is None or issue.state is state)
        ]
        return matching[:limit], None

    async def list_all_issues(self, user_id: str, matter_id: str) -> list[LegalIssue]:
        return [
            replace(issue)
            for issue in self.issues.values()
            if issue.user_id == user_id and issue.matter_id == matter_id
        ]

    async def update_issue(self, issue: LegalIssue, expected_version: int) -> LegalIssue:
        stored = self.issues.get(issue.id)
        if stored is None or stored.version != expected_version:
            raise LegalIssueStaleError(expectedVersion=expected_version)
        saved = replace(issue, version=expected_version + 1, updated_at=datetime.now(tz=UTC))
        self.issues[issue.id] = saved
        return replace(saved)


class FakeFactReader:
    """Implements ``ConfirmedFactReadPort``; the summary is swapped between runs."""

    def __init__(self, summary: FactTierSummary) -> None:
        self.summary = summary

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        return self.summary
