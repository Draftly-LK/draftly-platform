"""Unit tests for Clerk identity adapter helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.modules.auth.domain.errors import IdentityValidationError
from src.modules.auth.infrastructure.clerk_adapter import (
    ClerkIdentityAdapter,
    _assert_authorized_party,
    _email_from_payload,
)

ISSUER = "https://popular-lark-48.clerk.accounts.dev"
AZP = "http://localhost:4310"


class _StaticSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


def _adapter(private_key: Any, *, leeway_seconds: int) -> ClerkIdentityAdapter:
    adapter = ClerkIdentityAdapter(
        issuer=ISSUER,
        secret_key="sk_test_notused",
        authorized_parties=frozenset({AZP}),
        leeway_seconds=leeway_seconds,
    )
    # The JWKS fetch is network I/O and is not what these tests are about.
    adapter._jwks_client.get_signing_key_from_jwt = (  # type: ignore[method-assign]
        lambda _token: _StaticSigningKey(private_key.public_key())
    )
    return adapter


def _token(private_key: Any, *, issued_offset: timedelta, azp: str = AZP) -> str:
    """A well-formed Clerk-shaped token whose `iat` is deliberately skewed."""
    issued_at = datetime.now(tz=UTC) + issued_offset
    return jwt.encode(
        {
            "iss": ISSUER,
            "sub": "user_synthetic_001",
            "azp": azp,
            "email": "solo@example.com",
            "email_verified": True,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": issued_at + timedelta(minutes=1),
        },
        private_key,
        algorithm="RS256",
    )


@pytest.fixture(scope="module")
def rsa_key() -> Any:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class TestClockSkewLeeway:
    """A host running slightly slow must not lock every user out.

    Clerk issues a token stamped with *its* clock. If this host is a few
    seconds behind, that `iat` looks like the future and PyJWT rejects it with
    "The token is not yet valid (iat)" — which presents as a total login
    outage rather than as a clock problem.
    """

    async def test_a_token_issued_slightly_in_the_future_is_accepted(self, rsa_key: Any) -> None:
        adapter = _adapter(rsa_key, leeway_seconds=30)
        claims = await adapter.validate_token(_token(rsa_key, issued_offset=timedelta(seconds=5)))
        assert claims.subject == "user_synthetic_001"
        assert claims.verified_email == "solo@example.com"

    async def test_skew_beyond_the_leeway_is_still_rejected(self, rsa_key: Any) -> None:
        """The tolerance is bounded — it is not "trust any timestamp"."""
        adapter = _adapter(rsa_key, leeway_seconds=30)
        with pytest.raises(IdentityValidationError):
            await adapter.validate_token(_token(rsa_key, issued_offset=timedelta(seconds=120)))

    async def test_zero_leeway_rejects_the_drift_that_broke_sign_in(self, rsa_key: Any) -> None:
        """Pins the original bug: with no leeway, seconds of drift is fatal."""
        adapter = _adapter(rsa_key, leeway_seconds=0)
        with pytest.raises(IdentityValidationError):
            await adapter.validate_token(_token(rsa_key, issued_offset=timedelta(seconds=5)))

    def test_a_negative_leeway_is_refused(self, rsa_key: Any) -> None:
        with pytest.raises(ValueError):
            ClerkIdentityAdapter(
                issuer=ISSUER,
                secret_key="sk_test_notused",
                authorized_parties=frozenset({AZP}),
                leeway_seconds=-1,
            )


class TestEmailFromPayload:
    def test_returns_email_when_verified(self):
        assert _email_from_payload({"email": "solo@example.com", "email_verified": True}) == (
            "solo@example.com"
        )

    @pytest.mark.parametrize("claim", ["true", "True", " TRUE "])
    def test_accepts_the_string_form_clerk_actually_sends(self, claim: str):
        """Clerk interpolates shortcodes into JSON, so the claim is a string.

        A session token customised with
        ``"email_verified": "{{user.email_verified}}"`` carries ``"true"``,
        not ``true``.
        """
        assert _email_from_payload({"email": "solo@example.com", "email_verified": claim}) == (
            "solo@example.com"
        )

    @pytest.mark.parametrize("claim", ["false", "False", "", "1", "yes", None, 1, 0])
    def test_rejects_anything_that_is_not_an_explicit_affirmative(self, claim: object):
        """Only an explicit true counts — not truthiness, not a stray value."""
        assert _email_from_payload({"email": "solo@example.com", "email_verified": claim}) is None

    def test_a_present_email_alone_is_never_enough(self):
        """The whole point of the gate: an address is not a verified address."""
        assert _email_from_payload({"email": "solo@example.com"}) is None

    def test_returns_none_when_email_unverified(self):
        assert _email_from_payload({"email": "solo@example.com", "email_verified": False}) is None

    def test_returns_none_when_verified_flag_missing(self):
        assert _email_from_payload({"email": "solo@example.com"}) is None

    def test_returns_none_when_email_missing(self):
        assert _email_from_payload({"email_verified": True}) is None


class TestAssertAuthorizedParty:
    _LOCAL = frozenset({"http://localhost:3000", "http://localhost:4310"})

    def test_accepts_matching_azp(self):
        _assert_authorized_party({"azp": "http://localhost:4310"}, frozenset({AZP}))

    def test_accepts_either_local_origin_on_the_allowlist(self):
        _assert_authorized_party({"azp": "http://localhost:3000"}, self._LOCAL)
        _assert_authorized_party({"azp": "http://localhost:4310"}, self._LOCAL)

    def test_rejects_missing_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"sub": "user_1"}, frozenset({AZP}))

    def test_rejects_empty_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"azp": ""}, frozenset({AZP}))

    def test_rejects_mismatched_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"azp": "https://other-app.example"}, self._LOCAL)

    def test_empty_allowlist_is_refused_at_construction(self):
        with pytest.raises(ValueError):
            ClerkIdentityAdapter(
                issuer=ISSUER,
                secret_key="sk_test_notused",
                authorized_parties=frozenset(),
            )

    async def test_validate_token_accepts_the_other_local_origin(self, rsa_key: Any) -> None:
        adapter = ClerkIdentityAdapter(
            issuer=ISSUER,
            secret_key="sk_test_notused",
            authorized_parties=self._LOCAL,
            leeway_seconds=30,
        )
        adapter._jwks_client.get_signing_key_from_jwt = (  # type: ignore[method-assign]
            lambda _token: _StaticSigningKey(rsa_key.public_key())
        )
        token = _token(
            rsa_key,
            issued_offset=timedelta(seconds=0),
            azp="http://localhost:3000",
        )
        claims = await adapter.validate_token(token)
        assert claims.subject == "user_synthetic_001"
