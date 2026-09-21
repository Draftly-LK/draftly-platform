"""In-memory doubles for the matter module's tests. No database.

The repository double keeps the two behaviours of the real one the service
depends on: reads are scoped by ``user_id`` (another tenant's matter is simply
absent), and ``update`` refuses a stale ``expected_version`` and bumps the
version on success. Every value is synthetic.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.modules.auth.domain.models import Role
from src.modules.auth.ports import AuditEventInput
from src.modules.content_governance.contracts import (
    AnswerStatus,
    CompiledChecklist,
    CompilerInput,
    compile_checklist,
)
from src.modules.matter.domain.errors import MatterStaleError
from src.modules.matter.domain.models import IntakeAnswer, Matter
from src.modules.matter.domain.routing import MatterFactSnapshot
from src.platform.request_context import RequestContext

LAWYER_ID = "usr_lawyer"
OTHER_USER_ID = "usr_other"
CORRELATION = "corr_synthetic"


def ctx(actor_id: str = LAWYER_ID, role: Role = Role.APPROVER) -> RequestContext:
    return RequestContext(actor_id=actor_id, account_role=role, correlation_id=CORRELATION)


class InMemoryMatterRepository:
    def __init__(self) -> None:
        self.matters: dict[str, Matter] = {}
        self.classifications: list[dict[str, Any]] = []

    async def get(self, user_id: str, matter_id: str) -> Matter | None:
        matter = self.matters.get(matter_id)
        if matter is None or matter.user_id != user_id:
            return None
        return replace(matter)

    async def list_for_user(
        self, user_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Matter], str | None]:
        owned = [m for m in self.matters.values() if m.user_id == user_id]
        return owned[:limit], None

    async def create(self, matter: Matter) -> Matter:
        self.matters[matter.id] = replace(matter)
        return replace(matter)

    async def update(self, matter: Matter, expected_version: int) -> Matter:
        stored = self.matters[matter.id]
        if stored.version != expected_version:
            raise MatterStaleError()
        saved = replace(matter, version=stored.version + 1)
        self.matters[matter.id] = saved
        return replace(saved)

    async def append_classification(
        self,
        matter: Matter,
        *,
        version: int,
        rule_pack_version: str,
        changed_by: str,
        reason: str | None,
    ) -> None:
        self.classifications.append(
            {
                "matter_id": matter.id,
                "version": version,
                "subtype_id": matter.subtype_id,
                "rule_pack_version": rule_pack_version,
                "changed_by": changed_by,
                "reason": reason,
            }
        )

    async def next_classification_version(self, matter_id: str) -> int:
        return 1 + sum(1 for c in self.classifications if c["matter_id"] == matter_id)


class InMemoryAnswerRepository:
    def __init__(self) -> None:
        self.answers: list[IntakeAnswer] = []

    async def list_live(self, user_id: str, matter_id: str) -> list[IntakeAnswer]:
        return [a for a in await self.list_all(user_id, matter_id) if a.is_live]

    async def list_all(self, user_id: str, matter_id: str) -> list[IntakeAnswer]:
        return [a for a in self.answers if a.user_id == user_id and a.matter_id == matter_id]

    async def supersede(self, user_id: str, matter_id: str, question_id: str) -> str | None:
        for answer in await self.list_live(user_id, matter_id):
            if answer.question_definition_id == question_id:
                answer.status = AnswerStatus.SUPERSEDED
                return answer.id
        return None

    async def create(self, answer: IntakeAnswer) -> IntakeAnswer:
        self.answers.append(answer)
        return answer


class FakeFactPort:
    def __init__(self, snapshot: MatterFactSnapshot | None = None) -> None:
        self.current = snapshot or MatterFactSnapshot()
        self.calls: list[tuple[str, str]] = []

    async def snapshot(self, user_id: str, matter_id: str) -> MatterFactSnapshot:
        self.calls.append((user_id, matter_id))
        return self.current


class FakeChecklistPort:
    """Compiles with the real rule-pack compiler; persists nothing."""

    def __init__(self) -> None:
        self.inputs: list[CompilerInput] = []

    async def compile_snapshot(
        self,
        *,
        user_id: str,
        matter_id: str,
        compiler_input: CompilerInput,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[str, CompiledChecklist]:
        self.inputs.append(compiler_input)
        return f"snp_{len(self.inputs)}", compile_checklist(compiler_input)


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)

    def actions(self) -> list[str]:
        return [event.action for event in self.events]
