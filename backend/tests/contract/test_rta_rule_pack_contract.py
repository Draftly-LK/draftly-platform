"""The committed RTA rule-pack contracts match the Python source of truth.

scripts/export_rta_contracts.py writes the full rule pack for the API and a
taxonomy slice for the frontend, whose New Matter screen renders families
and instruments from it. Its docstring promises a test that fails if either
committed file drifts; this is that test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.export_rta_contracts import FRONTEND_TAXONOMY_PATH, RULE_PACK_PATH, targets

REGENERATE = "regenerate it with: uv run python scripts/export_rta_contracts.py"


@pytest.mark.parametrize(
    "path",
    [RULE_PACK_PATH, FRONTEND_TAXONOMY_PATH],
    ids=["rta-rule-pack.v1.json", "taxonomy.generated.json"],
)
def test_the_committed_contract_matches_the_rule_pack(path: Path) -> None:
    expected = targets()[path]

    assert path.exists(), f"{path.name} is missing; {REGENERATE}"
    assert path.read_text(encoding="utf-8") == expected, f"{path.name} is stale; {REGENERATE}"
