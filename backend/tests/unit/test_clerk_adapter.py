"""Unit tests for Clerk identity adapter helpers."""

from __future__ import annotations

import pytest

from src.modules.auth.domain.errors import IdentityValidationError
from src.modules.auth.infrastructure.clerk_adapter import (
    _assert_authorized_party,
    _email_from_payload,
)


class TestEmailFromPayload:
    def test_returns_email_when_verified(self):
        assert _email_from_payload({"email": "solo@example.com", "email_verified": True}) == (
            "solo@example.com"
        )

    def test_returns_none_when_email_unverified(self):
        assert _email_from_payload({"email": "solo@example.com", "email_verified": False}) is None

    def test_returns_none_when_verified_flag_missing(self):
        assert _email_from_payload({"email": "solo@example.com"}) is None

    def test_returns_none_when_email_missing(self):
        assert _email_from_payload({"email_verified": True}) is None


class TestAssertAuthorizedParty:
    def test_accepts_matching_azp(self):
        _assert_authorized_party({"azp": "http://localhost:4310"}, "http://localhost:4310")

    def test_rejects_missing_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"sub": "user_1"}, "http://localhost:4310")

    def test_rejects_empty_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"azp": ""}, "http://localhost:4310")

    def test_rejects_mismatched_azp(self):
        with pytest.raises(IdentityValidationError):
            _assert_authorized_party({"azp": "https://other-app.example"}, "http://localhost:4310")
