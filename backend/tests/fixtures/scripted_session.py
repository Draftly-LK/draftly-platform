"""A scripted stand-in for ``AsyncSession``.

The SQL repositories are thin: they build a tenant-scoped statement, then map
rows to domain objects. The fake records every statement (so a test can
assert the tenant scope is in the WHERE clause) and hands back the rows a test
queued, in order. It does not evaluate SQL.
"""

from __future__ import annotations

from typing import Any


class FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._rows)

    def scalar_one_or_none(self) -> Any:
        assert len(self._rows) <= 1, "scalar_one_or_none on a multi-row result"
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.statements: list[Any] = []
        self._results: list[list[Any]] = []
        #: Set to make the next ``flush`` fail, e.g. with an ``IntegrityError``.
        self.flush_error: Exception | None = None

    def queue(self, *rows: Any) -> None:
        """Queue the rows the next ``execute`` call returns."""
        self._results.append(list(rows))

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        self.flushes += 1
        if self.flush_error is not None:
            raise self.flush_error

    async def execute(self, statement: Any) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self._results.pop(0) if self._results else [])

    def where_clause(self, index: int = -1) -> str:
        """The WHERE clause of a recorded statement, with literal parameters."""
        compiled = self.statements[index].compile(compile_kwargs={"literal_binds": True})
        return str(compiled).split("WHERE", 1)[1]
