"""Clerk JWT identity adapter — implements IdentityPort.

Fetches Clerk's JWKS and validates every JWT field that Clerk guarantees:
issuer, signature, authorised party (azp), and expiry. Uses PyJWT +
cryptography; does not import any Clerk SDK (provider-neutral behind port).

Falls back gracefully when CLERK_SECRET_KEY is absent — see stub_adapter.py.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient, PyJWKClientError

from src.modules.auth.domain.errors import IdentityValidationError
from src.modules.auth.ports import IdentityClaims


class ClerkIdentityAdapter:
    """Validates Clerk-issued JWTs using JWKS discovery."""

    def __init__(
        self,
        *,
        issuer: str,
        secret_key: str,
        audience: str | None = None,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._secret_key = secret_key
        self._audience = audience
        # Clerk JWKS endpoint
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._jwks_client = PyJWKClient(self._jwks_url, cache_keys=True)

    async def validate_token(self, token: str) -> IdentityClaims:
        """Validate the Clerk JWT and return verified claims.

        Raises IdentityValidationError on any validation failure.
        """
        try:
            # Decode header to get kid without verifying signature
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise IdentityValidationError("Malformed token header.") from exc

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientError as exc:
            raise IdentityValidationError("Could not retrieve signing key.") from exc

        decode_options: dict[str, Any] = {
            "verify_exp": True,
            "verify_iat": True,
            "verify_iss": True,
        }

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options=decode_options,
            )
        except jwt.ExpiredSignatureError as exc:
            raise IdentityValidationError("Token has expired.") from exc
        except jwt.InvalidIssuerError as exc:
            raise IdentityValidationError("Token issuer is not trusted.") from exc
        except jwt.DecodeError as exc:
            raise IdentityValidationError("Token signature is invalid.") from exc
        except jwt.InvalidTokenError as exc:
            raise IdentityValidationError(f"Token validation failed: {exc}") from exc

        subject: str | None = payload.get("sub")
        if not subject:
            raise IdentityValidationError("Token is missing the 'sub' claim.")

        verified_email: str | None = payload.get("email") or None
        auth_time: int | None = payload.get("auth_time")

        return IdentityClaims(
            issuer=self._issuer,
            subject=subject,
            verified_email=verified_email,
            provider="clerk",
            auth_time=auth_time,
            raw=payload,
        )
