"""Supermemory adapter — optional, non-authoritative semantic memory.

Neon is authoritative. Nothing here ever serves visible chat history, and a
failure is a degradation rather than an error: every method fails soft and the
turn continues without recall (``matter-agent-service.md`` §Failure Modes).

Isolation rests entirely on the container tag, because an external store has no
``WHERE user_id`` to fall back on. The tag is an HMAC of the matter and a
namespace version, so it is non-guessable and reveals no internal id
(``memory-service.md`` §11.1).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog

from src.modules.matter_agent.ports import MemoryHit

log = structlog.get_logger(__name__)

#: Bump to re-key every container, for example after a key rotation.
NAMESPACE_VERSION = "v1"

_TIMEOUT_SECONDS = 5.0


def container_tag(*, hmac_key: str, matter_id: str) -> str:
    """Derive the opaque container tag.

    Keyed on the matter and the namespace version. A matter id is globally
    unique and is owned by exactly one user in V0, so the matter is the tenant
    boundary here; adding the user id would not narrow it further.

    Deterministic, so a rebuild finds the same container. One-way, so the tag
    discloses neither the user nor the matter if it leaks into a provider log.
    """
    message = f"{NAMESPACE_VERSION}:{matter_id}".encode()
    digest = hmac.new(hmac_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"dm{NAMESPACE_VERSION}_{digest[:32]}"


class SupermemoryMemoryAdapter:
    """Semantic recall over an isolated per-matter container.

    Constructed only when the feature switch **and** the data-transfer approval
    are both set; the composition root uses ``NullMemoryPort`` otherwise, so an
    unapproved provider is unreachable rather than merely unused.
    """

    def __init__(self, *, api_key: str, base_url: str, hmac_key: str) -> None:
        if not hmac_key:
            raise ValueError("SUPERMEMORY_CONTAINER_HMAC_KEY is required for tenant isolation")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._hmac_key = hmac_key

    async def retrieve(self, *, matter_id: str, probe: str, limit: int) -> tuple[MemoryHit, ...]:
        """Best-effort recall. Any failure yields no hits, never an exception."""
        try:
            payload = await self._post(
                "/v1/search",
                {"containerTag": self._tag(matter_id), "q": probe, "limit": limit},
            )
        except Exception as exc:  # noqa: BLE001 - recall must never break a turn
            log.info("supermemory.retrieve_degraded", failure_class=type(exc).__name__)
            return ()
        return tuple(
            MemoryHit(
                text=str(item.get("text", "")),
                resource_id=str(item.get("resourceId", "")),
                resource_version=int(item.get("resourceVersion", 0)),
                kind=str(item.get("kind", "")),
            )
            for item in payload.get("results", [])
        )

    async def ingest(self, *, matter_id: str, resource_id: str, resource_version: int) -> None:
        """Ingest is driven by the outbox, so a failure here is a job retry."""
        await self._post(
            "/v1/documents",
            {
                "containerTag": self._tag(matter_id),
                "resourceId": resource_id,
                "resourceVersion": resource_version,
            },
        )

    async def is_ready(self, *, matter_id: str) -> bool:
        try:
            payload = await self._post(
                "/v1/containers/status", {"containerTag": self._tag(matter_id)}
            )
        except Exception as exc:  # noqa: BLE001 - unknown readiness means no recall
            log.info("supermemory.status_degraded", failure_class=type(exc).__name__)
            return False
        return bool(payload.get("state") == "READY")

    async def destroy(self, *, matter_id: str) -> dict[str, Any]:
        """Destroy the container and return the provider receipt.

        Deliberately does **not** fail soft: destruction is incomplete until the
        provider confirms, and a swallowed error here would report an erasure
        that never happened (``retention-service.md``).
        """
        return await self._post("/v1/containers/delete", {"containerTag": self._tag(matter_id)})

    def _tag(self, matter_id: str) -> str:
        # The matter id is never sent as itself; only its HMAC leaves Draftly.
        return container_tag(hmac_key=self._hmac_key, matter_id=matter_id)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self._base_url}{path}",
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            parsed: dict[str, Any] = response.json()
            return parsed
