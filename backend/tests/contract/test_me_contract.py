"""Contract test: GET /me response matches frontend User shape.

This test verifies that UserRead serialises to exactly the camelCase fields
the frontend expects (id, displayName, role, notaryRegistration, jurisdiction).
"""

from __future__ import annotations

import pytest

from src.modules.auth.api.schemas import UserRead


class TestMeContract:
    def test_user_read_serialises_to_camel_case(self):
        """UserRead must produce camelCase keys that match frontend User type."""
        read = UserRead(
            id="usr_123",
            display_name="N. M. Silva",
            role="approver",
            notary_registration="NP-0042",
            jurisdiction="Western Province",
        )
        data = read.model_dump(by_alias=True)

        # These keys must match frontend/src/types/user.ts User interface exactly
        assert data["id"] == "usr_123"
        assert data["displayName"] == "N. M. Silva"
        assert data["role"] == "approver"
        assert data["notaryRegistration"] == "NP-0042"
        assert data["jurisdiction"] == "Western Province"

        # No snake_case keys at the top level
        assert "display_name" not in data
        assert "notary_registration" not in data

    def test_user_read_nullable_fields(self):
        """notaryRegistration and jurisdiction are optional in the frontend type."""
        read = UserRead(
            id="usr_456",
            display_name="Pending User",
            role="reviewer",
            notary_registration=None,
            jurisdiction=None,
        )
        data = read.model_dump(by_alias=True)
        assert data["notaryRegistration"] is None
        assert data["jurisdiction"] is None

    def test_role_values_match_frontend_enum(self):
        """Role values must be the four strings in frontend user.ts."""
        valid_roles = {"reviewer", "approver", "maintainer", "administrator"}
        for role in valid_roles:
            read = UserRead(id="u", display_name="X", role=role)
            assert read.role == role
