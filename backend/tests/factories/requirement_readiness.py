"""Synthetic real-service state packets consumed by backend, frontend and browser regressions."""

from dataclasses import asdict, replace
from datetime import UTC, datetime
from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import (
    AutomationScope,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    MatterState,
    SubtypeDecisionStatus,
)
from src.modules.matter.contracts import MatterAccessSummary
from src.modules.task.api.router import _to_checklist_read
from src.modules.task.api.schemas import MatterReadinessRead
from src.modules.task.application.readiness_service import ReadinessService
from src.modules.task.tests.fakes import MATTER_ID, USER_ID
from src.modules.task.tests.test_checklist_service import WHO
from src.modules.task.tests.test_requirement_currentness import received_original_requirement
from src.platform.request_context import RequestContext


class FixedDate(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 9, tzinfo=UTC)


async def requirement_readiness_packet():
    packet = {}
    for condition in ("original", "review", "stale", "missing"):
        sequence = count(1)
        with (
            patch(
                "src.platform.ids.new_id",
                side_effect=lambda prefix, sequence=sequence: (
                    f"{prefix}_synthetic_{next(sequence)}"
                ),
            ),
            patch("src.modules.task.application.checklist_service.datetime", FixedDate),
            patch("src.modules.task.application.readiness_service.datetime", FixedDate),
        ):
            h, item_id = await received_original_requirement()
            await h.service.decide_satisfaction(
                **WHO,
                item_id=item_id,
                expected_version=3,
                digital_review=DigitalReviewStatus.UNREVIEWED
                if condition == "review"
                else DigitalReviewStatus.LAWYER_CONFIRMED,
                currency=CurrencyStatus.CURRENT,
                consistency=ConsistencyStatus.MATCHED,
            )
            if condition != "original":
                await h.service.record_original_inspection(
                    **WHO, item_id=item_id, expected_version=4, method="Synthetic packet inspection"
                )
            if condition == "stale":
                h.service._documents.changed = "version"
            if condition == "missing":
                # Isolate the collection dimension using the existing authorized command.
                from src.modules.content_governance.contracts import CollectionStatus

                await h.service.decide_satisfaction(
                    **WHO, item_id=item_id, expected_version=5, collection=CollectionStatus.MISSING
                )
            view = await h.service.get_checklist(user_id=USER_ID, matter_id=MATTER_ID)
            # Other governed requirements are not asserted complete: this packet isolates one row.
            view = replace(view, items=tuple(row for row in view.items if row.item.id == item_id))
            matter = MatterAccessSummary(
                MATTER_ID,
                USER_ID,
                USER_ID,
                "lk.rta",
                None,
                SubtypeDecisionStatus.PROVISIONAL,
                MatterState.EVIDENCE_COLLECTION,
                AutomationScope.ASSESSING,
                view.snapshot.id,
                1,
            )
            service = ReadinessService(
                SimpleNamespace(get_access_summary=AsyncMock(return_value=matter)),
                SimpleNamespace(lock=AsyncMock()),
                SimpleNamespace(get_checklist=AsyncMock(return_value=view)),
                {},
            )
            readiness = await service.evaluate(
                RequestContext(USER_ID, Role.APPROVER, "synthetic-packet"), MATTER_ID
            )
            packet[condition] = {
                "checklist": _to_checklist_read(view).model_dump(by_alias=True),
                "readiness": MatterReadinessRead.model_validate(
                    {**asdict(readiness), "evaluated_at": readiness.evaluated_at.isoformat()}
                ).model_dump(by_alias=True),
            }
    return packet
