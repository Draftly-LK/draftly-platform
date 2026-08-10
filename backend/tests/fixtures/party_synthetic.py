"""Synthetic party fixtures — demo content only, not real client data."""

from __future__ import annotations

from datetime import date

SYNTHETIC_PARTY_A = {
    "party_kind": "natural-person",
    "display_name": "N. M. Silva (synthetic)",
    "name_parts": {"full": "N. M. Silva (synthetic)"},
    "former_names": [],
    "date_of_birth": date(1985, 3, 12),
    "registration_number": None,
    "nationality": "LK",
    "residency_status": "resident",
    "addresses": [{"line1": "12 Synthetic Lane, Colombo (demo)"}],
    "contact_points": [{"kind": "phone", "value": "0700000001"}],
    "confidentiality_level": "standard",
}

SYNTHETIC_NIC = "200012345678"  # synthetic NIC — not a real person
