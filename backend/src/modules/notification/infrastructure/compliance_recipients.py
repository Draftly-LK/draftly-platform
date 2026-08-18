"""Restricted-compliance recipient allowlist (notification-service.md §8.2).

`auth_service` will own the persisted compliance allowlist
(`security-model.md` §3.4). Until that table exists, the allowlist is explicit
configuration and an empty allowlist fails closed: no restricted alert is
created for anyone.
"""

from __future__ import annotations

from collections.abc import Iterable


class ConfiguredComplianceRecipients:
    def __init__(self, user_ids: Iterable[str]) -> None:
        self._user_ids = frozenset(uid.strip() for uid in user_ids if uid.strip())

    async def is_allowlisted(self, user_id: str) -> bool:
        return user_id in self._user_ids


__all__ = ["ConfiguredComplianceRecipients"]
