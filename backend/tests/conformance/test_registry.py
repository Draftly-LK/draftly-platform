"""The service registry is well formed and agrees with the README it generates.

docs/services/README.md §2 says contracts/services.yaml is its machine-readable
form and that a check fails the build if the two drift. This is that check.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from tests.conformance.registry import BACKEND, REGISTRY, SERVICE_NAMES

REQUIRED_KEYS = ("name", "doc", "level", "phase")


def _readme_rows() -> dict[str, tuple[str, str]]:
    """``{service name: (phase, level)}`` from the README §2 table."""
    text = (BACKEND / "docs" / "services" / "README.md").read_text(encoding="utf-8")
    rows: dict[str, tuple[str, str]] = {}
    for match in re.finditer(
        r"^\| \[([a-z-]+)\]\([^)]*\) \|[^|]*\| ([^|]+) \| (L\d) \|$", text, re.M
    ):
        rows[match.group(1).replace("-", "_")] = (match.group(2).strip(), match.group(3))
    return rows


@pytest.mark.parametrize("service", REGISTRY, ids=SERVICE_NAMES)
def test_every_service_declares_its_required_keys(service: dict[str, Any]) -> None:
    assert [key for key in REQUIRED_KEYS if key not in service] == []


@pytest.mark.parametrize("service", REGISTRY, ids=SERVICE_NAMES)
def test_every_service_doc_exists(service: dict[str, Any]) -> None:
    assert (BACKEND / service["doc"]).is_file()


def test_service_names_are_unique() -> None:
    assert len(SERVICE_NAMES) == len(set(SERVICE_NAMES))


def test_the_readme_lists_every_registered_service() -> None:
    assert set(SERVICE_NAMES) <= set(_readme_rows())


@pytest.mark.parametrize("service", REGISTRY, ids=SERVICE_NAMES)
def test_the_readme_matches_the_registry(service: dict[str, Any]) -> None:
    phase, level = _readme_rows()[service["name"]]

    assert (str(service["phase"]), service["level"]) == (phase, level)
