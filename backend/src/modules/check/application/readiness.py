"""Current check work is scoped and pinned; historical runs never clear it."""

from src.modules.check.application.check_service import CheckService
from src.modules.check.application.currentness import read_current_transaction, subject_is_detached
from src.modules.matter.contracts import MatterScopeReadPort
from src.modules.task.contracts import ReadinessDependency, ReadinessReference
from src.platform.request_context import RequestContext


class CheckReadinessReader:
    def __init__(self, checks: CheckService, scopes: MatterScopeReadPort) -> None:
        self._checks, self._scopes = checks, scopes

    async def readiness_dependencies(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[ReadinessDependency, ...]:
        results = []
        cursor = None
        incomplete = False
        cursors = set()
        for _ in range(10):
            batch, cursor = await self._checks.list_results(
                user_id=ctx.actor_id, matter_id=matter_id, limit=100, cursor=cursor
            )
            results.extend(batch)
            if cursor is None:
                break
            if cursor in cursors:
                incomplete = True
                break
            cursors.add(cursor)
        else:
            incomplete = True
        dependencies = []
        seen = set()
        current = 0
        transactions = {}
        for result in results:
            key = (result.check_definition_id, result.transaction_id, result.subject_id)
            if key in seen:
                continue
            seen.add(key)
            ref = ReadinessReference(
                "check",
                result.id,
                transaction_id=result.transaction_id,
                subject_id=result.subject_id,
                association_version=result.association_version,
            )
            if result.transaction_id is None:
                dependencies.append(ReadinessDependency("checks", "pending", (ref,)))
                continue
            if result.transaction_id not in transactions:
                transactions[result.transaction_id] = await read_current_transaction(
                    self._scopes, ctx.actor_id, matter_id, result.transaction_id
                )
            transaction = transactions[result.transaction_id]
            if subject_is_detached(result, transaction):
                continue
            fresh = transaction is not None and transaction.version == result.association_version
            if not fresh or result.explanation_key == "rta.check.input_changed":
                dependencies.append(ReadinessDependency("checks", "pending", (ref,)))
            elif result.outcome.value in {"INCONCLUSIVE", "FAIL"}:
                dependencies.append(ReadinessDependency("checks", "pending", (ref,)))
            current += bool(fresh)
        if not current:
            dependencies.append(ReadinessDependency("checks", "pending"))
        elif incomplete or not dependencies:
            # No governed per-scope coverage policy exists yet. A fresh subset
            # is reviewable, but cannot prove complete matter-wide coverage.
            dependencies.append(ReadinessDependency("checks", "unknown"))
        gates = await self._checks.gates(ctx.actor_id, matter_id)
        for issue_id in gates.open_blocking_issue_ids:
            dependencies.append(
                ReadinessDependency("issues", "pending", (ReadinessReference("issue", issue_id),))
            )
        return tuple(dependencies)
