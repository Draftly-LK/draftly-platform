"""Unit tests for Clerk identity adapter helpers."""

from __future__ import annotations

from src.modules.auth.infrastructure.clerk_adapter import _email_from_payload


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
