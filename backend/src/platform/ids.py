"""Opaque prefixed record identifiers.

A cross-cutting technical primitive: every module needs the same id shape, and
duplicating `uuid4().hex` with a different prefix convention per module is how
`mat_` and `matter_` end up in the same database.

The prefix is part of the id, not metadata about it. It makes a mis-routed id
visible in a log or a URL instead of silently resolving against the wrong table
(RTA workflow spec §12.1).
"""

from __future__ import annotations

import uuid
from typing import Final

MATTER: Final = "mat"
INTAKE_ANSWER: Final = "ans"
CHECKLIST_SNAPSHOT: Final = "cls"
CHECKLIST_ITEM: Final = "cli"
SATISFACTION_LINK: Final = "sat"
SOURCE_FILE: Final = "src"
DETECTED_DOCUMENT: Final = "doc"
DOCUMENT_FRAGMENT: Final = "frg"
PROCESSING_RUN: Final = "run"
EVIDENCE_REFERENCE: Final = "ev"
EXTRACTED_FACT: Final = "fact"
REVIEW_DECISION: Final = "dec"
CROSS_DOCUMENT_CHECK: Final = "chk"
LEGAL_ISSUE: Final = "iss"
GENERATED_FORM: Final = "frm"
GENERATED_FORM_FIELD: Final = "fld"
APPROVAL: Final = "apr"
REGISTRATION_EVENT: Final = "reg"
EXPORT: Final = "exp"


def new_id(prefix: str) -> str:
    """Return a fresh opaque id such as ``mat_9f2c…``."""
    return f"{prefix}_{uuid.uuid4().hex}"


def has_prefix(value: str, prefix: str) -> bool:
    return value.startswith(f"{prefix}_")
