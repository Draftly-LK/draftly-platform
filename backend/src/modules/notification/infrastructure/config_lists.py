"""Parse comma-separated configuration lists."""

from __future__ import annotations


def parse_allowlist(raw: str) -> frozenset[str]:
    if not raw.strip():
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())
