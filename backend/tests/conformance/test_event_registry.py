"""Events: named, documented, and each consumed one published once (§4.3).

This replaces the inline script CI used to run, so the same check runs
locally with the rest of the suite.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from src.platform.messaging.envelope import EVENT_NAME_PATTERN, REGISTERED_AGGREGATES
from tests.conformance.registry import BACKEND, REGISTRY

PUBLISHERS: dict[str, list[str]] = defaultdict(list)
CONSUMERS: dict[str, list[str]] = defaultdict(list)
for _service in REGISTRY:
    for _event in _service.get("publishes") or []:
        PUBLISHERS[_event].append(_service["name"])
    for _event in _service.get("consumes") or []:
        CONSUMERS[_event].append(_service["name"])
ALL_EVENTS = sorted(set(PUBLISHERS) | set(CONSUMERS))
EVENTS_DOC = (BACKEND / "docs" / "events.md").read_text(encoding="utf-8")


def test_the_registry_declares_events() -> None:
    assert len(ALL_EVENTS) > 20


@pytest.mark.parametrize("event", sorted(CONSUMERS))
def test_every_consumed_event_has_a_publisher(event: str) -> None:
    assert PUBLISHERS[event], f"{event} consumed by {CONSUMERS[event]} with no publisher"


@pytest.mark.parametrize("event", sorted(PUBLISHERS))
def test_every_event_has_exactly_one_publisher(event: str) -> None:
    assert len(PUBLISHERS[event]) == 1, PUBLISHERS[event]


@pytest.mark.parametrize("event", ALL_EVENTS)
def test_every_event_is_documented(event: str) -> None:
    assert f"`{event}`" in EVENTS_DOC


@pytest.mark.parametrize("event", ALL_EVENTS)
def test_every_event_name_is_well_formed(event: str) -> None:
    assert EVENT_NAME_PATTERN.match(event)
    assert event.split(".", 1)[0] in REGISTERED_AGGREGATES
