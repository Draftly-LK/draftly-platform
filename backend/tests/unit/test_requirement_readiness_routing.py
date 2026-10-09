"""Real governed review dimensions must route to the consumer with those commands."""

import pytest

from tests.factories.requirement_readiness import requirement_readiness_packet


@pytest.mark.parametrize(
    ("condition", "action"),
    [
        ("original", "manual"),
        ("review", "manual"),
        ("stale", "requirements"),
        ("missing", "requirements"),
    ],
)
async def test_real_requirement_dimensions_choose_the_action_destination(condition, action):
    packet = (await requirement_readiness_packet())[condition]
    item, readiness = packet["checklist"]["items"][0], packet["readiness"]
    assert readiness["requirementCompleted"] == 0
    assert readiness["state"] == "blocked"
    assert readiness["nextAction"] == action
    assert item["computedResolution"] != "SATISFIED" and item["blocksApproval"]
    if condition in {"original", "review"}:
        assert item["collection"] == "RECEIVED" and item["liveLinkCount"] == 2


async def test_consumer_packet_matches_real_governed_readiness_output():
    import json
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parents[3]
        / "frontend/src/test/fixtures/requirement-readiness.json"
    )
    assert json.loads(fixture.read_text(encoding="utf8")) == await requirement_readiness_packet()
