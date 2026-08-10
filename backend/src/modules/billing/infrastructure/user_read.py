"""UserReadPort adapter.

Billing does not own accounts, so it reads them through auth's repository rather
than joining to auth tables itself.
"""

from __future__ import annotations

from src.modules.auth.domain.models import AccountStatus
from src.modules.auth.ports import UserRepository
from src.modules.billing.ports import BillingUser


class AuthUserReadAdapter:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    async def get_billing_user(self, user_id: str) -> BillingUser | None:
        user = await self._users.get(user_id)
        if user is None:
            return None
        return BillingUser(
            user_id=user.id,
            is_active=user.account_status == AccountStatus.ACTIVE,
        )
