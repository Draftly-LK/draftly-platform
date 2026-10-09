"""Task 6 delegates confirmed proposals to the real canonical register on migrated PG."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.bootstrap import build_agent_service, build_fact_review_service
from src.modules.auth.domain.errors import PracticeStatusError
from src.modules.auth.infrastructure.orm import UserRow
from src.modules.matter_agent.domain.errors import PendingActionStaleError
from src.modules.matter_agent.domain.models import PendingActionState
from tests.db.test_scoped_fact_review import matter as matter
from tests.db.test_scoped_fact_review import scoped_input


@pytest.fixture(autouse=True)
def agent_enabled(monkeypatch):
    import src.platform.config as config

    monkeypatch.setenv("MATTER_AGENT_ENABLED", "true")
    config._settings = None
    yield
    config._settings = None


async def proposal(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    user = await db_session.get(UserRow, ctx.actor_id)
    user.jurisdiction = "SYNTHETIC-JURISDICTION"
    await db_session.flush()
    await db_session.refresh(user)
    facts = build_fact_review_service(db_session)
    fact = await facts.add_manual(ctx, matter.matter_id, data, key="agent-synthetic-input")
    view = await facts.get_view(ctx, matter.matter_id, fact.id)
    agent = build_agent_service(db_session)
    session = await agent.get_or_create_session(ctx, matter.matter_id)
    card = await agent.propose_action(
        ctx,
        matter.matter_id,
        session_id=session.id,
        kind="fact-accept",
        arguments={"factId": fact.id, "expectedScopeToken": view.scope_token},
        target_ref=f"fact:{fact.id}",
        target_version=fact.version,
    )
    return ctx, data, facts, fact, agent, card


async def test_confirmed_fact_proposal_uses_owning_command_and_cached_replay_rechecks_practice(
    db_session, matter
):
    ctx, _, facts, fact, agent, card = await proposal(db_session, matter)
    confirmed = await agent.confirm_action(ctx, matter.matter_id, action_id=card.id)
    assert confirmed.state is PendingActionState.EXECUTED
    view = await facts.get_view(ctx, matter.matter_id, confirmed.result["factId"])
    assert view.fact.is_confirmed and view.fact.supersedes_fact_id == fact.id
    assert confirmed.result == {"factId": view.fact.id, "version": view.fact.version}
    assert await agent.confirm_action(ctx, matter.matter_id, action_id=card.id) == confirmed
    history = await facts.history(ctx, matter.matter_id, view.fact.id)
    assert len(history.decisions) == 2
    user = await db_session.get(UserRow, ctx.actor_id)
    user.certificate_valid_until = datetime.now(UTC) - timedelta(days=1)
    await db_session.flush()
    await db_session.refresh(user)
    with pytest.raises(PracticeStatusError):
        await agent.confirm_action(ctx, matter.matter_id, action_id=card.id)


async def test_changed_scope_token_blocks_same_fact_version_and_keeps_candidate(db_session, matter):
    ctx, data, facts, fact, agent, card = await proposal(db_session, matter)
    await facts.add_manual(
        ctx,
        matter.matter_id,
        replace(data, value="SYNTHETIC OTHER VALUE"),
        key="agent-new-conflict",
    )
    with pytest.raises(PendingActionStaleError):
        await agent.confirm_action(ctx, matter.matter_id, action_id=card.id)
    assert (
        await agent.read_action(ctx, matter.matter_id, card.id)
    ).state is PendingActionState.STALE
    assert not (await facts.get_view(ctx, matter.matter_id, fact.id)).fact.is_confirmed
