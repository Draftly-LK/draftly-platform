"""Contract test: GET /me response matches frontend User shape.

This test verifies that UserRead serialises to camelCase fields the frontend
expects (see frontend/src/types/user.ts).
"""

from __future__ import annotations

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
            qualifications="LL.B (Sri Lanka)",
            professional_titles="Attorney-at-Law · Notary Public",
            address_line1="No. 12, Synthetic Avenue",
            address_line2="Colombo",
            phone="0700000000",
        )
        data = read.model_dump(by_alias=True)

        assert data["id"] == "usr_123"
        assert data["displayName"] == "N. M. Silva"
        assert data["role"] == "approver"
        assert data["notaryRegistration"] == "NP-0042"
        assert data["jurisdiction"] == "Western Province"
        assert data["qualifications"] == "LL.B (Sri Lanka)"
        assert data["professionalTitles"] == "Attorney-at-Law · Notary Public"
        assert data["addressLine1"] == "No. 12, Synthetic Avenue"
        assert data["addressLine2"] == "Colombo"
        assert data["phone"] == "0700000000"

        assert "display_name" not in data
        assert "notary_registration" not in data
        assert "professional_titles" not in data

    def test_user_read_nullable_fields(self):
        """Extended profile fields are optional."""
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
        assert data["qualifications"] is None
        assert data["phone"] is None

    def test_role_values_match_frontend_enum(self):
        """Role values must be the four strings in frontend user.ts."""
        valid_roles = {"reviewer", "approver", "maintainer", "administrator"}
        for role in valid_roles:
            read = UserRead(id="u", display_name="X", role=role)
            assert read.role == role
