"""Candidate approval creates verification-owned records only after a human command."""

from src.modules.content_governance.contracts import FactStatus
from src.modules.verification.application.candidate_approval import (
    VerificationCandidateApprovalAdapter,
)
from src.modules.verification.contracts import CandidateApprovalInput


class Repository:
    def __init__(self) -> None:
        self.evidence = []
        self.decisions = []
        self.facts = []

    async def create_evidence(self, value: object) -> object:
        self.evidence.append(value)
        return value

    async def create_decision(self, value: object, *, human: bool = True) -> object:
        assert human
        self.decisions.append(value)
        return value

    async def next_version(self, user_id: str, matter_id: str, fact_type_id: str) -> int:
        assert (user_id, matter_id, fact_type_id) == (
            "usr_1",
            "mat_1",
            "rta.parcel.parcel_number",
        )
        return 2

    async def create_fact(self, value: object) -> object:
        self.facts.append(value)
        return value


async def test_explicit_approval_creates_page_evidence_decision_and_confirmed_fact() -> None:
    repository = Repository()
    adapter = VerificationCandidateApprovalAdapter(repository)  # type: ignore[arg-type]

    fact_id = await adapter.approve(
        CandidateApprovalInput(
            candidate_id="cand_1",
            user_id="usr_1",
            matter_id="mat_1",
            source_file_id="src_1",
            detected_document_id="doc_1",
            extraction_run_id="run_1",
            source_sha256="a" * 64,
            field_key="parcelNo",
            value="0020",
            page_no=2,
            model_reported_confidence=0.91,
            review_state="unverified",
        ),
        reviewer_id="usr_1",
        reviewer_role="LAWYER",
    )

    assert fact_id.startswith("fact_")
    assert repository.evidence[0].bounding_box is None
    assert repository.evidence[0].page_number == 2
    assert repository.decisions[0].reviewer_id == "usr_1"
    assert repository.facts[0].status is FactStatus.LAWYER_CONFIRMED
    assert repository.facts[0].value == "0020"
    assert repository.facts[0].version == 2
