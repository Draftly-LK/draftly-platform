"""Pending canonical and observational fact work, without exposing values."""

from src.modules.task.contracts import ReadinessDependency, ReadinessReference
from src.modules.verification.application.review_service import FactReviewService
from src.platform.request_context import RequestContext


class FactReadinessReader:
    def __init__(self, review: FactReviewService) -> None:
        self._review = review

    async def readiness_dependencies(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[ReadinessDependency, ...]:
        dependencies = []
        after = None
        seen = False
        cursors = set()
        for _ in range(4):
            rows, more = await self._review.list_facts(ctx, matter_id, limit=25, after=after)
            for row in rows:
                fact = row.fact
                if not fact.is_live or fact.status.value == "REJECTED":
                    continue
                seen = True
                if (
                    not fact.is_confirmed
                    or fact.evidence_stale
                    or fact.scope_status == "unassigned"
                    or row.conflict_fact_ids
                ):
                    dependencies.append(
                        ReadinessDependency(
                            "facts",
                            "pending",
                            (
                                ReadinessReference(
                                    "fact",
                                    fact.id,
                                    fact.version,
                                    transaction_id=fact.transaction_id,
                                    subject_id=fact.subject_id,
                                ),
                            ),
                        )
                    )
            if not more:
                break
            if not rows or rows[-1].fact.id in cursors:
                return (*dependencies, ReadinessDependency("facts", "unknown"))
            after = rows[-1].fact.id
            cursors.add(after)
        else:
            dependencies.append(ReadinessDependency("facts", "unknown"))
        if not seen:
            dependencies.append(ReadinessDependency("facts", "pending"))
        return tuple(dependencies)
