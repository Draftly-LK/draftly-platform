"""Golden-set evaluation of document extraction on the real case-001 bundle.

Manual, local-only — never CI. The bundle at ``inputs/case-001/`` is real,
gitignored client material (consent recorded); the expected values file lives
INSIDE that gitignored folder so nothing sensitive can enter the repository.

Usage (from backend/, with a real key):
    PROVIDER_DATA_APPROVAL=true EXTRACTION_PROVIDER=gemini GEMINI_API_KEY=... \
        uv run python scripts/eval_extraction.py

Expected-values format (inputs/case-001/expected-fields.json):
    { "<filename>.pdf": { "kind": "<registry kind>",
                          "fields": { "<factKey>": "<expected value>", ... } } }

Output: per-document and overall field accuracy plus a mismatch table.
Numbers may be copied into docs/review/; values must not.
"""

from __future__ import annotations

import asyncio
import json
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE = REPO_ROOT / "inputs" / "case-001"
EXPECTED = BUNDLE / "expected-fields.json"


def _norm(value: str) -> str:
    """Comparison-normalise: unicode NFC, collapse whitespace, casefold,
    strip common punctuation noise so 'Rs. 1,000,000/=' matches variants."""
    text = unicodedata.normalize("NFC", value)
    text = " ".join(text.split()).casefold()
    return text.replace(",", "").replace("/=", "").replace("/-", "").strip(" .")


async def main() -> int:
    from src.bootstrap import build_processing_service
    from src.platform.config import get_settings

    settings = get_settings()
    if not settings.provider_data_approval:
        print("Refusing: PROVIDER_DATA_APPROVAL must be true for a real-bundle run.")
        return 2
    if not EXPECTED.exists():
        print(f"Missing {EXPECTED} — author it from the verified fixture values first.")
        return 2

    expectations = json.loads(EXPECTED.read_text(encoding="utf-8"))
    service = build_processing_service()

    total_expected = 0
    total_correct = 0
    mismatches: list[tuple[str, str, str, str | None]] = []

    for filename, spec in sorted(expectations.items()):
        path = BUNDLE / filename
        if not path.exists():
            print(f"SKIP {filename}: file not found")
            continue
        report = await service.process(
            path.read_bytes(),
            "application/pdf",
            synthetic=False,
            correlation_id=f"eval:{filename}",
        )
        got = {f.key: f.value for f in report.fields}
        expected_fields: dict[str, str] = spec.get("fields", {})
        correct = 0
        for key, want in expected_fields.items():
            have = got.get(key)
            if have is not None and _norm(have) == _norm(want):
                correct += 1
            else:
                mismatches.append((filename, key, want, have))
        total_expected += len(expected_fields)
        total_correct += correct
        kind_note = (
            "kind OK"
            if report.kind == spec.get("kind")
            else f"kind MISMATCH got={report.kind} want={spec.get('kind')}"
        )
        print(
            f"{filename}: {correct}/{len(expected_fields)} fields · "
            f"outcome={report.outcome.value} · {kind_note} · "
            f"calls={report.ai_extraction_calls}"
        )

    if total_expected:
        print(
            f"\nOVERALL: {total_correct}/{total_expected} "
            f"({100 * total_correct / total_expected:.1f}%) fields correct"
        )
    if mismatches:
        print("\nMismatches (expected vs extracted):")
        for filename, key, want, have in mismatches:
            print(f"  {filename} · {key}: want {want!r} — got {have!r}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
