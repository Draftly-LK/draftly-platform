"""Clerk JWT identity adapter — implements IdentityPort.

Fetches Clerk's JWKS and validates every JWT field that Clerk guarantees:
issuer, signature, authorised party (azp), and expiry. Uses PyJWT +
cryptography; does not import any Clerk SDK (provider-neutral behind port).

Falls back gracefully when CLERK_SECRET_KEY is absent — see stub_adapter.py.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, cast

import jwt
from jwt import PyJWKClient, PyJWKClientError

from src.modules.auth.domain.errors import IdentityValidationError
from src.modules.auth.ports import IdentityClaims


def _is_affirmatively_verified(claim: object) -> bool:
    """Whether Clerk asserted this email is verified.

    Accepts the boolean and the string form. Clerk's session-token editor
    interpolates shortcodes into a JSON template, so a claim written as
    ``"email_verified": "{{user.email_verified}}"`` arrives as the *string*
    ``"true"`` rather than a boolean.

    Deliberately narrow: only an explicit affirmative counts. A missing claim,
    ``null``, ``"false"``, or the mere presence of an email address does not —
    an unverified address is exactly the case this gate exists to reject.
    """
    if claim is True:
        return True
    return isinstance(claim, str) and claim.strip().lower() == "true"


def _email_from_payload(payload: dict[str, Any]) -> str | None:
    """Return email only when Clerk marks it verified."""
    if not _is_affirmatively_verified(payload.get("email_verified")):
        return None
    email = payload.get("email")
    if isinstance(email, str) and email:
        return email
    return None


def _assert_authorized_party(payload: dict[str, Any], expected: frozenset[str]) -> None:
    """Reject tokens whose azp is missing or not in the trusted set."""
    azp = payload.get("azp")
    if not isinstance(azp, str) or not azp or azp not in expected:
        raise IdentityValidationError("Token authorised party (azp) is missing or not trusted.")


class ClerkIdentityAdapter:
    """Validates Clerk-issued JWTs using JWKS discovery."""

    def __init__(
        self,
        *,
        issuer: str,
        secret_key: str,
        authorized_parties: frozenset[str],
        audience: str | None = None,
        leeway_seconds: int = 30,
    ) -> None:
        if not authorized_parties:
            raise ValueError("authorized_parties is required for ClerkIdentityAdapter.")
        if leeway_seconds < 0:
            raise ValueError("leeway_seconds cannot be negative.")
        self._issuer = issuer.rstrip("/")
        self._secret_key = secret_key
        self._authorized_parties = authorized_parties
        self._audience = audience
        self._leeway = timedelta(seconds=leeway_seconds)
        # Clerk JWKS endpoint
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._jwks_client = PyJWKClient(self._jwks_url, cache_keys=True)

    async def validate_token(self, token: str) -> IdentityClaims:
        """Validate the Clerk JWT and return verified claims.

        Raises IdentityValidationError on any validation failure.
        """
        try:
            # Validate header structure before fetching signing key
            jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise IdentityValidationError("Malformed token header.") from exc

        try:
            signing_key = await asyncio.to_thread(
                self._jwks_client.get_signing_key_from_jwt,
                token,
            )
        except PyJWKClientError as exc:
            raise IdentityValidationError("Could not retrieve signing key.") from exc

        decode_options = cast(
            Any,
            {
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
            },
        )

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options=decode_options,
                # Absorbs clock drift between this host and Clerk. Without it a
                # host a couple of seconds slow rejects every freshly issued
                # token as "not yet valid (iat)".
                leeway=self._leeway,
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

        _assert_authorized_party(payload, self._authorized_parties)

        verified_email = _email_from_payload(payload)
        auth_time: int | None = payload.get("auth_time")

        return IdentityClaims(
            issuer=self._issuer,
            subject=subject,
            verified_email=verified_email,
            provider="clerk",
            auth_time=auth_time,
            raw=payload,
        )
