"""How the worker turns each handler's outcome into an outbox result (§6.4).

``build_dispatcher`` owns the mapping. Every outcome a handler can report is
listed here, and each table must cover its enum exactly, so a new outcome
cannot fall silently into a default. The handlers themselves are replaced:
these test the wiring, not delivery or the agent.
"""

from __future__ import annotations

from typing import Any

import pytest

import src.modules.matter_agent.jobs as agent_jobs
import src.modules.notification.jobs as notification_jobs
from src.bootstrap import build_dispatcher
from src.modules.matter_agent.jobs import RUN_TURN_JOB_TYPE
from src.modules.notification.application.notification_service import (
    DELIVER_JOB_TYPE,
    ConsumeOutcome,
    DeliveryOutcome,
)
from src.modules.notification.domain.policies import EVENT_TEMPLATE_ROUTES
from src.modules.notification.domain.templates import get_template
from src.platform.messaging.dispatcher import MessageDispatcher, MessageResult
from src.platform.messaging.outbox import KIND_EVENT, KIND_JOB, ClaimedMessage

DELIVERY: dict[DeliveryOutcome, MessageResult] = {
    DeliveryOutcome.DELIVERED: MessageResult.DONE,
    DeliveryOutcome.SUPPRESSED: MessageResult.DONE,
    DeliveryOutcome.PERMANENT_FAILURE: MessageResult.DONE,
    DeliveryOutcome.UNKNOWN_DELIVERY: MessageResult.DONE,
    DeliveryOutcome.RETRY: MessageResult.RETRY,
    DeliveryOutcome.DEAD_LETTER: MessageResult.DEAD_LETTER,
}

CONSUME: dict[ConsumeOutcome, MessageResult] = {
    ConsumeOutcome.PROCESSED: MessageResult.DONE,
    ConsumeOutcome.DUPLICATE: MessageResult.DONE,
    ConsumeOutcome.SUPPRESSED: MessageResult.DONE,
    ConsumeOutcome.DEAD_LETTER: MessageResult.DEAD_LETTER,
}

#: run_turn_job's documented outcomes, plus "retry" which the mapping handles.
AGENT_TURN: dict[str, MessageResult] = {
    "completed": MessageResult.DONE,
    "unknown-job": MessageResult.DONE,
    "failed": MessageResult.DONE,
    "retry": MessageResult.RETRY,
}


def _message(kind: str, name: str) -> ClaimedMessage:
    return ClaimedMessage(
        id=1,
        organisation_id="usr_synthetic",
        kind=kind,
        name=name,
        payload={},
        idempotency_key="k1",
        attempts=1,
    )


def _dispatcher_reporting(
    monkeypatch: pytest.MonkeyPatch, module: Any, function: str, outcome: str
) -> MessageDispatcher:
    async def reports(session: Any, payload: Any) -> str:
        return outcome

    monkeypatch.setattr(module, function, reports)
    return build_dispatcher()


def test_the_delivery_table_covers_every_delivery_outcome() -> None:
    assert set(DELIVERY) == set(DeliveryOutcome)


def test_the_consume_table_covers_every_consume_outcome() -> None:
    assert set(CONSUME) == set(ConsumeOutcome)


@pytest.mark.parametrize(("outcome", "expected"), DELIVERY.items(), ids=lambda v: str(v))
async def test_a_delivery_outcome_maps_to_its_outbox_result(
    monkeypatch: pytest.MonkeyPatch, outcome: DeliveryOutcome, expected: MessageResult
) -> None:
    dispatcher = _dispatcher_reporting(
        monkeypatch, notification_jobs, "run_delivery_job", outcome.value
    )

    result = await dispatcher.dispatch(None, _message(KIND_JOB, DELIVER_JOB_TYPE))  # type: ignore[arg-type]

    assert result is expected


@pytest.mark.parametrize(("outcome", "expected"), CONSUME.items(), ids=lambda v: str(v))
async def test_a_consume_outcome_maps_to_its_outbox_result(
    monkeypatch: pytest.MonkeyPatch, outcome: ConsumeOutcome, expected: MessageResult
) -> None:
    dispatcher = _dispatcher_reporting(
        monkeypatch, notification_jobs, "consume_registered_event", outcome.value
    )

    result = await dispatcher.dispatch(None, _message(KIND_EVENT, "obligation.escalated"))  # type: ignore[arg-type]

    assert result is expected


@pytest.mark.parametrize(("outcome", "expected"), AGENT_TURN.items())
async def test_an_agent_turn_outcome_maps_to_its_outbox_result(
    monkeypatch: pytest.MonkeyPatch, outcome: str, expected: MessageResult
) -> None:
    """Anything but ``retry`` finishes the job — ``failed`` included, on purpose.

    A failed turn is recorded on the agent job. Redelivering it would run the
    turn again and answer the user twice; do not "fix" this to RETRY.
    """
    dispatcher = _dispatcher_reporting(monkeypatch, agent_jobs, "run_turn_job", outcome)

    result = await dispatcher.dispatch(None, _message(KIND_JOB, RUN_TURN_JOB_TYPE))  # type: ignore[arg-type]

    assert result is expected


@pytest.mark.parametrize(
    ("module", "function", "kind", "name", "expected"),
    [
        (notification_jobs, "run_delivery_job", KIND_JOB, DELIVER_JOB_TYPE, MessageResult.FAILED),
        (
            notification_jobs,
            "consume_registered_event",
            KIND_EVENT,
            "obligation.escalated",
            MessageResult.FAILED,
        ),
        (agent_jobs, "run_turn_job", KIND_JOB, RUN_TURN_JOB_TYPE, MessageResult.DONE),
    ],
    ids=["delivery", "consume", "agent-turn"],
)
async def test_an_unrecognised_outcome_does_not_retry_forever(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    function: str,
    kind: str,
    name: str,
    expected: MessageResult,
) -> None:
    dispatcher = _dispatcher_reporting(monkeypatch, module, function, "synthetic-new-outcome")

    assert await dispatcher.dispatch(None, _message(kind, name)) is expected  # type: ignore[arg-type]


def test_every_routed_event_has_a_consumer() -> None:
    registered = {name for kind, name in build_dispatcher().registered() if kind == KIND_EVENT}

    assert set(EVENT_TEMPLATE_ROUTES) <= registered


@pytest.mark.parametrize(("event_name", "template_key"), sorted(EVENT_TEMPLATE_ROUTES.items()))
def test_every_routed_event_names_a_template_that_exists(
    event_name: str, template_key: str
) -> None:
    """A renamed template would otherwise fail only when the event fires."""
    assert get_template(template_key) is not None, f"{event_name} → {template_key}"
