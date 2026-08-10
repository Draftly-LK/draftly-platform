"""The private-content denylist (service-definition-of-done.md §4.7).

A log line, error body, event payload, audit payload, notification body, or
metric label must never carry a party name, an identifier value, a suspicion
narrative, a document snippet, or a secret. This module is the single shared
definition of "must never carry", so a test and the runtime check agree.
"""

from __future__ import annotations

import re
from typing import Any

# Keys that name private content regardless of what they happen to hold.
DENIED_KEYS: frozenset[str] = frozenset(
    {
        "displayname",
        "display_name",
        "name",
        "nameparts",
        "name_parts",
        "formernames",
        "former_names",
        "fullname",
        "full_name",
        "givenname",
        "surname",
        "identifiervalue",
        "identifier_value",
        "nic",
        "passport",
        "passportnumber",
        "address",
        "addresses",
        "dateofbirth",
        "date_of_birth",
        "snippet",
        "text",
        "value",
        "narrative",
        "matchnarrative",
        "match_narrative",
        "listentry",
        "listentryref",
        "list_entry_ref",
        "providerpayload",
        "provider_payload",
        "dispositionreason",
        "disposition_reason",
        "recipient",
        "email",
        "phone",
        "secret",
        "token",
        "apikey",
        "api_key",
        "password",
    }
)

# Sri Lankan NIC: nine digits plus V/X, or the twelve-digit form.
_NIC_PATTERNS = (
    re.compile(r"\b\d{9}[VvXx]\b"),
    re.compile(r"\b\d{12}\b"),
)
# Common passport shape: one or two letters followed by six to eight digits.
_PASSPORT_PATTERN = re.compile(r"\b[A-Z]{1,2}\d{6,8}\b")


class PrivateContentLeakError(AssertionError):
    """A value that must never leave the protected tier was about to."""


def find_private_content(payload: Any, *, path: str = "") -> list[str]:
    """Return a list of denylist violations, described by path and rule only.

    The offending value is never included in the description — that would make
    the leak checker itself a leak.
    """
    violations: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.lower().replace("-", "_").replace("_", "") in {
                k.replace("_", "") for k in DENIED_KEYS
            }:
                violations.append(f"{child_path}: denied key")
            violations.extend(find_private_content(value, path=child_path))
    elif isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            violations.extend(find_private_content(item, path=f"{path}[{index}]"))
    elif isinstance(payload, str):
        for pattern in _NIC_PATTERNS:
            if pattern.search(payload):
                violations.append(f"{path or '<root>'}: NIC pattern")
                break
        if _PASSPORT_PATTERN.search(payload):
            violations.append(f"{path or '<root>'}: passport pattern")

    return violations


def assert_no_private_content(payload: Any, *, context: str) -> None:
    violations = find_private_content(payload)
    if violations:
        raise PrivateContentLeakError(f"{context}: {'; '.join(sorted(set(violations)))}")
