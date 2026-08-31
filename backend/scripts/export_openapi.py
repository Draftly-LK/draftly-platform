"""Generate ``contracts/openapi.v1.json`` from the live FastAPI app.

``api-conventions.md`` §9 requires the schema to be regenerated on every build
and committed, so a removed or renamed field is a visible diff rather than a
surprise in the browser. ``tests/contract/test_openapi_contract.py`` fails when
the committed file and the app disagree.

Run: ``uv run python scripts/export_openapi.py``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "openapi.v1.json"


def build_schema() -> dict[str, Any]:
    """The schema the running app would serve."""
    from src.main import create_app

    schema: dict[str, Any] = create_app().openapi()
    return schema


def serialise(schema: dict[str, Any]) -> str:
    """Stable formatting so a diff shows content changes, not key churn."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(serialise(build_schema()), encoding="utf-8")
    print(f"wrote {CONTRACT_PATH.relative_to(CONTRACT_PATH.parent.parent)}")


if __name__ == "__main__":
    main()
