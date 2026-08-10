"""Deliberately narrow stub for `MatterAccessPort` — `matter_service` does not exist.

This is **not** a matter access control implementation and must not grow into
one. `matter_service` owns matter membership and `MatterPartyReference`
(party-service.md §1); when it lands, this file is deleted and the real adapter
replaces it. Nothing here should be read as an approved access rule.

Fail-closed behaviour while it stands in:

- No matter is accessible unless a test has explicitly linked it.
- Every refusal is 404, so a non-member gets no existence signal (§5).
- It refuses to be wired outside local and test environments.
"""

from __future__ import annotations

from src.platform.errors import NotFoundError

_NON_PRODUCTION_ENVIRONMENTS = frozenset({"local", "test", "ci"})


class MatterServiceUnavailableError(RuntimeError):
    """Wiring the stub outside local/test is a deployment error, not a fallback."""


class StubMatterAccessAdapter:
    """In-memory matter membership. Empty by default, so it denies everything."""

    def __init__(self) -> None:
        # matter_id -> (owning actor_id, party ids)
        self._matters: dict[str, tuple[str, list[str]]] = {}

    def link_parties(self, matter_id: str, actor_id: str, party_ids: list[str]) -> None:
        """Test helper — the only way this stub ever grants access."""
        self._matters[matter_id] = (actor_id, list(party_ids))

    async def assert_matter_access(self, actor_id: str, matter_id: str) -> None:
        entry = self._matters.get(matter_id)
        if entry is None or entry[0] != actor_id:
            raise NotFoundError("The requested resource was not found.")

    async def list_party_ids_for_matter(self, actor_id: str, matter_id: str) -> list[str]:
        await self.assert_matter_access(actor_id, matter_id)
        return list(self._matters[matter_id][1])


def build_matter_access_adapter(environment: str) -> StubMatterAccessAdapter:
    if environment not in _NON_PRODUCTION_ENVIRONMENTS:
        raise MatterServiceUnavailableError(
            "matter_service is not implemented; the party module cannot serve "
            "matter-scoped party lists outside local and test environments."
        )
    return StubMatterAccessAdapter()
