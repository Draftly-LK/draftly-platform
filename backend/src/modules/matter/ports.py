"""Matter module ports.

The application service depends on these protocols only. `MatterFactPort` and
`ChecklistCommandPort` are how the matter reaches state owned elsewhere —
verification owns facts, task owns the checklist — without importing another
module's domain or touching another owner's tables (plan §5.1).
"""

from __future__ import annotations

from typing import Protocol

from src.modules.content_governance.contracts import CompiledChecklist, CompilerInput
from src.modules.matter.domain.models import IntakeAnswer, Matter
from src.modules.matter.domain.routing import MatterFactSnapshot


class MatterRepository(Protocol):
    async def get(self, user_id: str, matter_id: str) -> Matter | None: ...

    async def list_for_user(
        self, user_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Matter], str | None]: ...

    async def create(self, matter: Matter) -> Matter: ...

    async def update(self, matter: Matter, expected_version: int) -> Matter:
        """Persist and bump ``version``; raise on a stale ``expected_version``."""
        ...

    async def append_classification(
        self,
        matter: Matter,
        *,
        version: int,
        rule_pack_version: str,
        changed_by: str,
        reason: str | None,
    ) -> None: ...

    async def next_classification_version(self, matter_id: str) -> int: ...


class IntakeAnswerRepository(Protocol):
    async def list_live(self, user_id: str, matter_id: str) -> list[IntakeAnswer]: ...

    async def list_all(self, user_id: str, matter_id: str) -> list[IntakeAnswer]: ...

    async def supersede(self, user_id: str, matter_id: str, question_id: str) -> str | None:
        """Mark the current live answer superseded; return its id if there was one."""
        ...

    async def create(self, answer: IntakeAnswer) -> IntakeAnswer: ...


class MatterFactPort(Protocol):
    """Reads lawyer-confirmed facts from `verification` for the routing gates."""

    async def snapshot(self, user_id: str, matter_id: str) -> MatterFactSnapshot: ...


class ChecklistCommandPort(Protocol):
    """Asks `task` to compile a snapshot. Matter never writes checklist tables."""

    async def compile_snapshot(
        self,
        *,
        user_id: str,
        matter_id: str,
        compiler_input: CompilerInput,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[str, CompiledChecklist]: ...
