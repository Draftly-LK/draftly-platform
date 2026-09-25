"""Synthetic Clerk-shaped JWTs, signed with a key minted for the test run.

The real ``ClerkIdentityAdapter`` validates these unchanged; only its key
source is swapped, from Clerk's JWKS endpoint to this key. No real issuer,
subject or email appears here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://clerk.synthetic.draftly.test"
AUTHORIZED_PARTY = "http://localhost:4310"
KEY_ID = "synthetic-key-1"


@dataclass(frozen=True)
class _SigningKey:
    key: Any


class LocalJwks:
    """Stands in for ``PyJWKClient``: hands back the public half of one key."""

    def __init__(self, public_key: rsa.RSAPublicKey) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> _SigningKey:
        if jwt.get_unverified_header(token).get("kid") != KEY_ID:
            raise jwt.PyJWKClientError("Unknown signing key.")
        return _SigningKey(self._public_key)


class TokenMinter:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwks = LocalJwks(self._private_key.public_key())

    def mint(self, subject: str, **overrides: Any) -> str:
        """A valid token for ``subject``; any claim can be overridden or dropped (None)."""
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "sub": subject,
            "azp": AUTHORIZED_PARTY,
            "iat": now,
            "nbf": now,
            "exp": now + 300,
            "email": f"{subject}@synthetic.draftly.test",
            "email_verified": True,
        }
        claims.update(overrides)
        claims = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(claims, self._private_key, algorithm="RS256", headers={"kid": KEY_ID})
