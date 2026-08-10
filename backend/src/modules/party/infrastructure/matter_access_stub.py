"""Matter access stub for V0 — no matter_service yet."""

from __future__ import annotations

from src.platform.errors import NotFoundError


class StubMatterAccessAdapter:
    """Allows access when matter_id starts with matter- and embeds the actor id."""

    def __init__(self) -> None:
        self._matter_party_ids: dict[str, list[str]] = {}

    def link_parties(self, matter_id: str, party_ids: list[str]) -> None:
        """Test helper — register party ids for a matter."""
        self._matter_party_ids[matter_id] = list(party_ids)

    async def assert_matter_access(self, actor_id: str, matter_id: str) -> None:
        if not matter_id.startswith("matter-"):
            raise NotFoundError("The requested resource was not found.")
        token = f"matter-{actor_id}"
        if not (matter_id == token or matter_id.startswith(f"{token}-")):
            raise NotFoundError("The requested resource was not found.")

    async def list_party_ids_for_matter(self, actor_id: str, matter_id: str) -> list[str]:
        await self.assert_matter_access(actor_id, matter_id)
        return list(self._matter_party_ids.get(matter_id, []))
