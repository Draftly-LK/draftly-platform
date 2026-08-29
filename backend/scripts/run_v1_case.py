"""Run an explicitly approved local case through the live V1 providers.

The output is deliberately metadata-only: OCR text and candidate values are
written to private GCS objects and are never printed or copied into the report.
This is an operator tool, not an application ingestion path; it does not invent
a tenant or matter association when one was not supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog

from src.bootstrap import build_source_file_storage, build_v1_processing_pipeline
from src.modules.content_governance.contracts import DOCUMENT_CLASSES, fact_type_for_field
from src.modules.document.domain.registry import get_template
from src.modules.document.ports import ExtractionFieldSchema
from src.platform.config import get_settings


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run approved PDFs through Draftly V1")
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def _schemas() -> tuple[tuple[str, ...], dict[str, tuple[ExtractionFieldSchema, ...]]]:
    allowed = tuple(item.id for item in DOCUMENT_CLASSES)
    schemas: dict[str, tuple[ExtractionFieldSchema, ...]] = {}
    for item in DOCUMENT_CLASSES:
        template = get_template(item.extraction_template_kind) if item.extraction_template_kind else None
        if template is None:
            continue
        schemas[item.id] = tuple(
            ExtractionFieldSchema(key=field.key, description=field.label)
            for field in template.fields
            if fact_type_for_field(field.key) is not None
        )
    return allowed, schemas


def _expected(case_dir: Path) -> dict[str, Any]:
    path = case_dir / "expected-fields.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _safe_report_path(path: Path, workspace: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError("The report must stay inside the repository workspace.")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


async def _run(case_dir: Path, report_path: Path) -> dict[str, Any]:
    workspace = Path(__file__).resolve().parents[2]
    case_dir = case_dir.resolve()
    approved_root = (workspace / "inputs").resolve()
    if not case_dir.is_relative_to(approved_root):
        raise ValueError("case_dir must be within the repository inputs directory.")

    pdfs = sorted(case_dir.glob("*.pdf"))
    if not pdfs:
        raise ValueError("No PDF inputs were found.")

    settings = get_settings()
    if settings.source_file_storage != "gcs":
        raise RuntimeError("SOURCE_FILE_STORAGE must be gcs for a live case run.")
    if not settings.storage_real_data_approved or not settings.provider_data_approval:
        raise RuntimeError("Both storage and provider real-data approvals must be enabled.")
    if settings.extraction_provider != "vision-gemini":
        raise RuntimeError("EXTRACTION_PROVIDER must be vision-gemini.")

    storage = build_source_file_storage()
    pipeline = build_v1_processing_pipeline()
    allowed_types, schemas = _schemas()
    expected = _expected(case_dir)
    template_by_class = {
        item.id: item.extraction_template_kind for item in DOCUMENT_CLASSES
    }
    run_id = uuid.uuid4().hex
    prefix = f"document-processing-v1/case-001/{run_id}"
    sources: list[dict[str, Any]] = []

    for source_index, pdf in enumerate(pdfs, start=1):
        data = pdf.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        source_prefix = f"{prefix}/source-{source_index:03d}"
        original_key = f"{source_prefix}/original.pdf"
        original_generation = await storage.put(original_key, data)

        result = await pipeline.process(
            data,
            "application/pdf",
            allowed_type_ids=allowed_types,
            extraction_schemas=schemas,
        )

        status_counts: dict[str, int] = {}
        uncertain_rotation = 0
        low_confidence = 0
        derivative_generations: list[dict[str, Any]] = []
        for page in result.pages:
            status = page.quality_status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            uncertain_rotation += int(page.rotation.status.value == "rotation_uncertain")
            classification = page.classification
            low_confidence += int(
                classification is None
                or classification.model_reported_confidence < settings.confidence_threshold
            )
            page_prefix = f"{source_prefix}/pages/{page.page_no:04d}"
            artifacts = (
                ("corrected_webp", f"{page_prefix}/corrected.webp", page.corrected_webp),
                ("corrected_ocr_json", f"{page_prefix}/ocr.json", page.ocr_json),
                ("plain_ocr_text", f"{page_prefix}/ocr.txt", page.plain_text),
            )
            stored: dict[str, Any] = {"page_no": page.page_no}
            for label, key, artifact in artifacts:
                generation = await storage.put(key, artifact)
                stored[label] = {"key": key, "generation": generation}
            derivative_generations.append(stored)

        candidates = [
            candidate
            for document in result.logical_documents
            for candidate in document.candidates
        ]
        expected_source = expected.get(pdf.name, {})
        expected_kind = expected_source.get("kind") if isinstance(expected_source, dict) else None
        expected_fields = (
            expected_source.get("fields", {}) if isinstance(expected_source, dict) else {}
        )
        candidate_by_key = {candidate.key: candidate.value for candidate in candidates}
        comparable = {
            key: value
            for key, value in expected_fields.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        exact_matches = sum(candidate_by_key.get(key) == value for key, value in comparable.items())
        predicted_types = [
            document.logical_document.type_id for document in result.logical_documents
        ]
        predicted_kinds = [template_by_class.get(type_id) for type_id in predicted_types]

        source_report = {
            "source_index": source_index,
            "input_name": pdf.name,
            "sha256": digest,
            "original": {"key": original_key, "generation": original_generation},
            "page_count": len(result.pages),
            "page_status_counts": status_counts,
            "rotation_uncertain_count": uncertain_rotation,
            "classification_low_confidence_count": low_confidence,
            "classification_calls": result.classification_calls,
            "extraction_calls": result.extraction_calls,
            "logical_document_count": len(result.logical_documents),
            "predicted_type_ids": predicted_types,
            "candidate_count": len(candidates),
            "all_candidates_unverified": True,
            "derivatives": derivative_generations,
            "evaluation": {
                "has_expected_record": bool(expected_source),
                "type_exact": expected_kind in predicted_kinds if expected_kind else None,
                "expected_field_count": len(comparable),
                "exact_field_match_count": exact_matches,
            },
        }
        sources.append(source_report)
        print(
            json.dumps(
                {
                    "source_index": source_index,
                    "page_count": len(result.pages),
                    "status": "stored",
                }
            ),
            flush=True,
        )

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": run_id,
        "gcs_prefix": prefix,
        "provider": "vision-gemini",
        "classification_model": settings.gemini_classify_model,
        "extraction_model": settings.gemini_extract_model,
        "raster_dpi": settings.raster_dpi,
        "tenant_matter_persisted": False,
        "tenant_matter_note": (
            "Operator run only: no verified tenant/matter ID was supplied, so no Neon rows "
            "were created and no existing matter was guessed."
        ),
        "source_count": len(sources),
        "sources": sources,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    args = _arguments()
    logging.disable(logging.CRITICAL)
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    workspace = Path(__file__).resolve().parents[2]
    try:
        report_path = _safe_report_path(args.report, workspace)
        report = asyncio.run(_run(args.case_dir, report_path))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "complete",
                "run_id": report["run_id"],
                "source_count": report["source_count"],
                "report": str(report_path.relative_to(workspace)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
