"""Legacy document review has no separate confirmation policy or write path."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.auth.domain.models import Role
from src.modules.verification.application.candidate_approval import (
    VerificationCandidateApprovalAdapter,
)
from src.modules.verification.contracts import CandidateApprovalInput
from src.platform.errors import CapabilityDeniedError


def candidate():
    return CandidateApprovalInput(
        "candidate",
        "user",
        "matter",
        "source",
        "document",
        "run",
        "a" * 64,
        "parcelNo",
        "0020",
        1,
        1,
        "unverified",
        version=7,
        correlation_id="synthetic",
    )


async def test_document_approval_delegates_to_canonical_policy_and_version():
    service = SimpleNamespace(
        decide_candidate=AsyncMock(return_value=SimpleNamespace(id="successor"))
    )
    repository = SimpleNamespace(by_candidate=AsyncMock())
    adapter = VerificationCandidateApprovalAdapter(service, repository)
    assert (
        await adapter.approve(candidate(), reviewer_id="user", reviewer_role=Role.APPROVER.value)
        == "successor"
    )
    args, kwargs = service.decide_candidate.call_args
    assert args[0].actor_id == "user"
    assert args[1:] == ("matter", "candidate")
    assert kwargs == {"action": "accept", "expected_version": 7}
    repository.by_candidate.assert_not_called()


@pytest.mark.parametrize("actor,role", [("foreign", "APPROVER"), ("user", "LAWYER")])
async def test_adapter_does_not_invent_an_authorized_role(actor, role):
    service = SimpleNamespace(decide_candidate=AsyncMock())
    adapter = VerificationCandidateApprovalAdapter(service, SimpleNamespace())
    with pytest.raises(CapabilityDeniedError):
        await adapter.approve(candidate(), reviewer_id=actor, reviewer_role=role)
    service.decide_candidate.assert_not_called()
