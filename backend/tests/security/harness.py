"""Shared HTTP harness for the security suites.

The production app, dependency chain and ``ClerkIdentityAdapter``, with two
substitutions only: the adapter's signing keys come from a key minted for the
run instead of Clerk's JWKS endpoint, and users live in memory. A database
stand-in fails the test on any real query.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_auth_service
from src.main import create_app
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.domain.models import UserIdentity
from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter
from src.platform.db.session import get_db
from tests.factories.audit import FakeAudit
from tests.factories.auth import InMemoryUserIdentityRepo, InMemoryUserRepo, active_user
from tests.factories.constants import NOW
from tests.factories.tokens import AUTHORIZED_PARTY, ISSUER, TokenMinter

LEEWAY_SECONDS = 30


@dataclass
class Harness:
    app: FastAPI
    client: AsyncClient
    minter: TokenMinter
    identities: InMemoryUserIdentityRepo
    users: InMemoryUserRepo

    async def link(self, subject: str, user_id: str, **user: Any) -> None:
        """Provision ``user_id`` and link ``subject`` to it, as first login would."""
        record = active_user(user_id)
        for field, value in user.items():
            setattr(record, field, value)
        await self.users.create(record)
        await self.identities.create(
            UserIdentity(
                user_id=user_id,
                provider="clerk",
                issuer=ISSUER,
                subject=subject,
                verified_email=f"{subject}@synthetic.draftly.test",
                linked_at=NOW,
            )
        )

    def bearer(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def signed_in(self, subject: str, **claims: Any) -> dict[str, str]:
        """Headers for a fresh session: a valid token that also passes step-up."""
        claims.setdefault("auth_time", int(time.time()))
        return self.bearer(self.minter.mint(subject, **claims))


class _NoDatabase:
    """Lets a unit of work open and close; fails loudly on any real query.

    Rejected requests must never reach the database, and the admitted ones
    here only touch the in-memory user stores.
    """

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"unexpected database use: session.{name}")


async def _no_database() -> AsyncIterator[_NoDatabase]:
    yield _NoDatabase()


@pytest.fixture
async def harness() -> AsyncIterator[Harness]:
    minter = TokenMinter()
    identities, users = InMemoryUserIdentityRepo(), InMemoryUserRepo()
    adapter = ClerkIdentityAdapter(
        issuer=ISSUER,
        secret_key="sk_synthetic_unused",
        authorized_parties=frozenset({AUTHORIZED_PARTY}),
        leeway_seconds=LEEWAY_SECONDS,
    )
    # The one seam: signing keys come from this run's key, not Clerk's JWKS.
    adapter._jwks_client = minter.jwks  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_db] = _no_database
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        identity_port=adapter,
        user_identity_repo=identities,
        user_repo=users,
        audit_port=FakeAudit(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield Harness(app, client, minter, identities, users)
