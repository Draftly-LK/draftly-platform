from __future__ import annotations

import pytest

from src.platform.config import parse_allowed_origins


def test_parse_allowed_origins_normalizes_and_deduplicates() -> None:
    assert parse_allowed_origins(
        "https://app.example.com/, http://localhost:3000,https://app.example.com"
    ) == ("https://app.example.com", "http://localhost:3000")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "*",
        "app.example.com",
        "https://user@example.com",
        "https://app.example.com/path",
        "https://app.example.com?redirect=elsewhere",
    ],
)
def test_parse_allowed_origins_rejects_non_origins(value: str) -> None:
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        parse_allowed_origins(value)
