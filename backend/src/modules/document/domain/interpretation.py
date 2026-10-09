"""Pinned cached OCR input for a corrected document, independent of its upload run."""

from dataclasses import dataclass
from datetime import datetime

from src.modules.document.domain.ingestion import FragmentRange


@dataclass(frozen=True)
class InterpretationSnapshot:
    generation: int
    class_id: str | None
    fragments: tuple[FragmentRange, ...]
    actor_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class InterpretationRun:
    id: str
    generation: int
    outcome: str
    reasons: tuple[str, ...]
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class InterpretationHistory:
    document_id: str
    matter_id: str
    current_generation: int
    snapshots: tuple[InterpretationSnapshot, ...]
    refresh_runs: tuple[InterpretationRun, ...]


@dataclass(frozen=True)
class InterpretationPage:
    source_file_id: str
    page_number: int
    page_id: str
    quality_status: str
    image_ref: tuple[str, str]
    text_ref: tuple[str, str]
