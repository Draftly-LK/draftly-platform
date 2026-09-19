"""Every job a functional service declares has a worker handler (§4.5).

A service at L3 is functional, so the jobs it lists in the registry must be
registered with the dispatcher, or they are enqueued and never run. Services
below L3 are still designs and are not held to their runtime yet.
"""

from __future__ import annotations

import pytest

from src.bootstrap import build_dispatcher
from src.platform.messaging.outbox import KIND_JOB
from tests.conformance.registry import FUNCTIONAL_LEVELS, REGISTRY

REGISTERED = {name for kind, name in build_dispatcher().registered() if kind == KIND_JOB}
DECLARED = sorted(
    (service["name"], job)
    for service in REGISTRY
    if service["level"] in FUNCTIONAL_LEVELS
    for job in service.get("jobs") or []
)

#: Declared by a functional service, with no handler registered. Each needs its
#: job implemented, or the service's level or job list corrected.
MISSING_HANDLERS = {
    "billing.reconcile-subscriptions",
    "obligation.emit-reminders",
    "register.close-month",
}


def test_functional_services_declare_jobs() -> None:
    assert DECLARED


@pytest.mark.parametrize(("service", "job"), DECLARED)
def test_no_new_declared_job_lacks_a_handler(service: str, job: str) -> None:
    assert job in REGISTERED or job in MISSING_HANDLERS, f"{service} declares {job}"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="billing, obligations and the notarial register declare jobs nothing handles.",
)
def test_every_declared_job_has_a_handler() -> None:
    assert [job for _, job in DECLARED if job not in REGISTERED] == []
