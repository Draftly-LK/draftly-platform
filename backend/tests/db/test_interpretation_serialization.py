"""A correction and consumers of its facts serialize through the owning matter."""

import asyncio

import pytest

from scripts.seed_synthetic_matter import seed
from src.bootstrap import build_check_service, build_draft_service
from src.modules.content_governance.contracts import TRANSFER_SALE_SUBTYPE_ID, SubtypeDecisionStatus
from src.modules.matter.infrastructure.scope_repository import SqlMatterScopeRepository


@pytest.mark.parametrize("consumer", ["checks", "draft"])
async def test_consumers_wait_until_the_correction_transaction_finishes(
    db_committing, tmp_path, monkeypatch, consumer
):
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "sources"))
    async with db_committing() as session:
        matter = await seed(session)
        await session.commit()

    async def consume():
        async with db_committing() as session:
            kwargs = {
                "user_id": matter.lawyer_id,
                "matter_id": matter.matter_id,
                "actor_id": matter.lawyer_id,
                "correlation_id": "synthetic-consumer",
            }
            if consumer == "checks":
                await build_check_service(session).run_checks(**kwargs)
            else:
                await build_draft_service(session).generate_form(
                    **kwargs,
                    subtype_id=TRANSFER_SALE_SUBTYPE_ID,
                    subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
                )
            await session.commit()

    async with db_committing() as correction:
        await SqlMatterScopeRepository(correction).lock(matter.lawyer_id, matter.matter_id)
        task = asyncio.create_task(consume())
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
        finally:
            await correction.rollback()
            await task
