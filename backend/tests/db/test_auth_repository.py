"""The user and identity repositories against Postgres.

An identity is keyed by (issuer, subject), never by email alone: the same
subject from another issuer is a different identity, and one verified email
belongs to at most one identity.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.domain.models import Role, UserIdentity
from src.modules.auth.infrastructure.repository import (
    SqlUserIdentityRepository,
    SqlUserRepository,
)
from tests.factories.auth import active_user
from tests.factories.constants import NOW, USER_A, USER_B

pytestmark = pytest.mark.integration

ISSUER = "https://clerk.synthetic.draftly.test"


def _identity(user_id: str = USER_A, **overrides: object) -> UserIdentity:
    identity = UserIdentity(
        user_id=user_id,
        provider="clerk",
        issuer=ISSUER,
        subject="user_synthetic_a",
        verified_email="lawyer-a@synthetic.draftly.test",
        linked_at=NOW,
    )
    return replace(identity, **overrides)  # type: ignore[arg-type]


async def _users(session: AsyncSession, *user_ids: str) -> None:
    for user_id in user_ids:
        await SqlUserRepository(session).create(active_user(user_id))


async def test_a_user_reads_back_whole_and_updates(db_session: AsyncSession) -> None:
    users = SqlUserRepository(db_session)
    created = await users.create(active_user(USER_A))

    await users.update(replace(created, role=Role.ADMINISTRATOR))
    stored = await users.get(USER_A)

    assert stored is not None
    assert (stored.id, stored.role) == (USER_A, Role.ADMINISTRATOR)


async def test_an_identity_resolves_only_by_its_issuer_and_subject(
    db_session: AsyncSession,
) -> None:
    await _users(db_session, USER_A)
    identities = SqlUserIdentityRepository(db_session)
    await identities.create(_identity())

    found = await identities.find_by_subject(ISSUER, "user_synthetic_a")

    assert found is not None and found.user_id == USER_A
    assert await identities.find_by_subject("https://clerk.other.test", "user_synthetic_a") is None
    assert await identities.find_by_subject(ISSUER, "user_synthetic_b") is None


async def test_one_issuer_and_subject_link_to_one_identity(db_session: AsyncSession) -> None:
    await _users(db_session, USER_A, USER_B)
    identities = SqlUserIdentityRepository(db_session)
    await identities.create(_identity())

    with pytest.raises(IntegrityError, match="uq_user_identity_issuer_subject"):
        await identities.create(_identity(USER_B, verified_email="other@synthetic.draftly.test"))


async def test_one_verified_email_belongs_to_one_identity(db_session: AsyncSession) -> None:
    await _users(db_session, USER_A, USER_B)
    identities = SqlUserIdentityRepository(db_session)
    await identities.create(_identity())

    with pytest.raises(IntegrityError, match="uq_user_identities_verified_email"):
        await identities.create(_identity(USER_B, subject="user_synthetic_b"))


async def test_many_identities_may_have_no_verified_email(db_session: AsyncSession) -> None:
    await _users(db_session, USER_A, USER_B)
    identities = SqlUserIdentityRepository(db_session)

    await identities.create(_identity(verified_email=None))
    await identities.create(_identity(USER_B, subject="user_synthetic_b", verified_email=None))

    assert await identities.find_by_subject(ISSUER, "user_synthetic_b") is not None
