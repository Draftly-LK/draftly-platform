"""The approval declaration register.

§9.6 requires the approval to carry "a declaration that the lawyer reviewed the
evidence-linked draft and accepts responsibility for the legal instrument". That
sentence is **human-owned legal wording** (CLAUDE.md) and is deliberately not
authored here. What this module owns is the *record* of which declaration was
accepted: a version, a translation key, and a hash.

Until the team registers the approved wording, ``text_sha256`` is ``None`` and
`declaration_text_hash` returns a ``pending-sha256:`` digest over the record's
identity instead of over its text. The scheme prefix is part of the stored value
so no reader can mistake one for the other, and the day the wording lands the
hash changes — which is exactly what an auditor needs to see, because an
approval given under different words is a different approval.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

#: Bumped when the wording changes. An approval stores the version it was given
#: under, so a later edit can never be read back onto an earlier signature.
DECLARATION_V1 = "1"


@dataclass(frozen=True)
class DeclarationRecord:
    """One version of the approval declaration."""

    version: str
    #: The translation key the interface renders. The text lives in the i18n
    #: bundle, is written by the team, and is never generated.
    text_key: str
    #: sha256 of the exact approved wording, once a lawyer has approved it.
    text_sha256: str | None = None


DECLARATIONS: dict[str, DeclarationRecord] = {
    DECLARATION_V1: DeclarationRecord(
        version=DECLARATION_V1,
        text_key="rta.approval.declaration.v1",
    ),
}

CURRENT_DECLARATION_VERSION = DECLARATION_V1


def get_declaration(version: str) -> DeclarationRecord | None:
    return DECLARATIONS.get(version)


def declaration_text_hash(record: DeclarationRecord) -> str:
    """The hash stored on the approval.

    Over the wording when it exists; over ``text_key@version`` when it does not,
    under a distinct scheme so the record never claims to have hashed words that
    were never written.
    """
    if record.text_sha256 is not None:
        return f"sha256:{record.text_sha256}"
    identity = f"{record.text_key}@{record.version}".encode()
    return f"pending-sha256:{hashlib.sha256(identity).hexdigest()}"


__all__ = [
    "CURRENT_DECLARATION_VERSION",
    "DECLARATIONS",
    "DECLARATION_V1",
    "DeclarationRecord",
    "declaration_text_hash",
    "get_declaration",
]
