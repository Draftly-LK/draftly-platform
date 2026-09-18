"""In-memory user and identity stores, keyed the way the SQL ones are.

Enough of the real repositories' behaviour to drive ``AuthService`` over HTTP:
identities resolve by ``(issuer, subject)``, never by email alone.
"""

from __future__ import annotations

from dataclasses import replace

from src.modules.auth.domain.models import AccountStatus, Role, User, UserIdentity
from tests.factories.constants import NOW


def active_user(user_id: str, role: Role = Role.APPROVER) -> User:
    return User(
        id=user_id,
        display_name=f"{user_id} (synthetic)",
        account_status=AccountStatus.ACTIVE,
        role=role,
        notary_registration=None,
        jurisdiction=None,
        created_at=NOW,
        updated_at=NOW,
    )


class InMemoryUserIdentityRepo:
    def __init__(self) -> None:
        self._by_subject: dict[tuple[str, str], UserIdentity] = {}

    async def find_by_subject(self, issuer: str, subject: str) -> UserIdentity | None:
        return self._by_subject.get((issuer, subject))

    async def find_by_verified_email(self, email: str) -> UserIdentity | None:
        return next(
            (i for i in self._by_subject.values() if i.verified_email == email),
            None,
        )

    async def create(self, identity: UserIdentity) -> UserIdentity:
        self._by_subject[(identity.issuer, identity.subject)] = identity
        return identity


class InMemoryUserRepo:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def get(self, user_id: str) -> User | None:
        user = self._users.get(user_id)
        return replace(user) if user else None

    async def get_by_email(self, email: str) -> User | None:
        return None

    async def create(self, user: User) -> User:
        self._users[user.id] = replace(user)
        return replace(user)

    async def update(self, user: User) -> User:
        self._users[user.id] = replace(user)
        return replace(user)
