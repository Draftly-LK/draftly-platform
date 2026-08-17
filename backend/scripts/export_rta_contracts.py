"""Write the RTA rule-pack contracts consumed by the API and the frontend.

Run from ``backend/``::

    uv run python scripts/export_rta_contracts.py

Writes:
  backend/contracts/rta-rule-pack.v1.json     full pack (contract tests, API)
  frontend/src/lib/rta/taxonomy.generated.json  the slice the UI renders

The frontend copy exists so the New Matter screen can render families and
instruments before any matter exists. A contract test regenerates both and
fails if either file on disk differs, so the copy can never drift from the
Python source of truth.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.modules.content_governance.application.rule_pack_export import (  # noqa: E402
    full_rule_pack_contract,
    taxonomy_contract,
)
from src.modules.content_governance.domain.rta.rulepack import (  # noqa: E402
    validate_rule_pack,
)

REPO_ROOT = _BACKEND_ROOT.parent
RULE_PACK_PATH = _BACKEND_ROOT / "contracts" / "rta-rule-pack.v1.json"
FRONTEND_TAXONOMY_PATH = REPO_ROOT / "frontend" / "src" / "lib" / "rta" / "taxonomy.generated.json"


def render(payload: object) -> str:
    """Stable formatting so a regenerated file diffs only on real changes."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def targets() -> dict[Path, str]:
    validate_rule_pack()
    return {
        RULE_PACK_PATH: render(full_rule_pack_contract()),
        FRONTEND_TAXONOMY_PATH: render(taxonomy_contract()),
    }


def main() -> int:
    written = 0
    for path, content in targets().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        written += 1
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    if written == 0:
        print("contracts already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
