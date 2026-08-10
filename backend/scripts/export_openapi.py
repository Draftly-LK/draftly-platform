"""Export the OpenAPI contract to backend/contracts/openapi.v1.json.

Run from `backend/`:  uv run python scripts/export_openapi.py
The frontend contract is generated, never hand-edited.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from src.main import create_app  # noqa: E402

OUTPUT = BACKEND_ROOT / "contracts" / "openapi.v1.json"


def main() -> None:
    spec = create_app().openapi()
    OUTPUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
