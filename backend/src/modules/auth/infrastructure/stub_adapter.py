"""Stub identity adapter for CI and local development without Clerk credentials.

Returns a deterministic IdentityClaims that resolves to the synthetic demo user
(DEMO_USER_ID from the frontend fixtures). Used when USE_STUB_IDENTITY=true or
when CLERK_ISSUER / CLERK_SECRET_KEY are absent.

This adapter MUST NOT be used in production — bootstrap.py enforces this by
checking settings.clerk_configured before selecting it.
"""

from __future__ import annotations

from src.modules.auth.ports import IdentityClaims

# Matches frontend/src/lib/mocks/fixtures.ts DEMO_USER_ID
_STUB_SUBJECT = "stub-clerk-user-001"
_STUB_ISSUER = "https://stub.clerk.local"
_STUB_EMAIL = "demo@draftly.local"


class StubIdentityAdapter:
    """Returns hard-coded synthetic claims — never validate a real Clerk JWT."""

    async def validate_token(self, token: str) -> IdentityClaims:  # noqa: ARG002
        return IdentityClaims(
            issuer=_STUB_ISSUER,
            subject=_STUB_SUBJECT,
            verified_email=_STUB_EMAIL,
            provider="stub",
        )
