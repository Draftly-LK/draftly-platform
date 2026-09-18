"""Every job type the worker runs has the lease jobs-and-workers.md §5 gives it."""

from __future__ import annotations

import pytest

from src.bootstrap import build_dispatcher
from src.platform.messaging.outbox import KIND_JOB
from src.workers.runner import DEFAULT_LEASE_SECONDS, JOB_LEASE_SECONDS

REGISTERED_JOBS = sorted(name for kind, name in build_dispatcher().registered() if kind == KIND_JOB)


def test_the_default_lease_is_the_documented_one() -> None:
    assert DEFAULT_LEASE_SECONDS == 300


@pytest.mark.parametrize("job_type", REGISTERED_JOBS)
def test_every_registered_job_has_an_explicit_lease(job_type: str) -> None:
    """A new job type must be placed in the §5 registry, not inherit silently."""
    assert job_type in JOB_LEASE_SECONDS


def test_an_agent_turn_outlives_its_own_turn_budget() -> None:
    """The lease must cover the 120 s turn timeout, or a slow turn runs twice."""
    from src.platform.config import get_settings

    assert JOB_LEASE_SECONDS["agent.run-turn"] > get_settings().matter_agent_turn_timeout_seconds
