"""PlatformAdminPort adapters.

`platform.administer` is a Draftly-staff capability that no account role
reaches, granted by an audited administrative action and re-read per request
(security-model.md §3.4). That audited grant store belongs to `auth_service`
and is not built yet, so V0 resolves the grant from a deployment allowlist.

The allowlist is empty by default, so plan administration fails closed until an
operator configures it deliberately.
"""

from __future__ import annotations


class SettingsPlatformAdminAdapter:
    """Resolves the grant from `PLATFORM_ADMIN_USER_IDS`."""

    def __init__(self, allowlist: str) -> None:
        self._user_ids = frozenset(entry.strip() for entry in allowlist.split(",") if entry.strip())

    async def is_platform_admin(self, user_id: str) -> bool:
        return user_id in self._user_ids


class DenyAllPlatformAdminAdapter:
    """Fail-closed default and test double."""

    async def is_platform_admin(self, user_id: str) -> bool:
        _ = user_id
        return False
