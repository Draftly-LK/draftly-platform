"""Synthetic party fixtures.

Every value here is invented for tests and demos. There is no real person,
NIC, passport, address, or registration number in this file, and none may be
added — see CLAUDE.md, "never commit real client data".
"""

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

SYNTHETIC_PARTY_B = {
    "party_kind": "company",
    "display_name": "Synthetic Holdings (demo)",
    "name_parts": {"full": "Synthetic Holdings (demo)"},
    "former_names": [],
    "date_of_birth": None,
    "registration_number": "BR-SYN-0001",
    "nationality": "LK",
    "residency_status": None,
    "addresses": [{"line1": "1 Demo Road, Kandy (demo)"}],
    "contact_points": [],
    "confidentiality_level": "standard",
}

# Synthetic identifiers — invented digit strings, not issued to anyone.
SYNTHETIC_NIC = "200012345678"
SYNTHETIC_NIC_OLD_FORMAT = "851234567V"
SYNTHETIC_PASSPORT = "N7654321"
SYNTHETIC_DOCUMENT_ID = "doc_synthetic_0001"
SYNTHETIC_DOCUMENT_VERSION_ID = "dver_synthetic_0001"
SYNTHETIC_EVIDENCE_SPAN = {"page": 1, "bbox": [0.1, 0.1, 0.4, 0.15]}
