# Draftly backend — document intake pipeline

FastAPI service for Gemini two-stage classify → extract (E5 / DRA-44).

Package layout follows `backend-implementation-plan-v0.md` (`src/draftly_api`).

## Pipeline

1. **Classify** the uploaded image against registered document types
   (currently: `identity` only; everything else → `other`).
2. **Extract** only when classification matches a registered type and
   confidence meets the threshold. Identity extraction returns
   transcription + typed NIC fields (`null` = undetected).

No Document AI / OCR step.

## Setup

1. Copy root `.env.example` → `.env` and fill `GEMINI_API_KEY`.
   Set `GEMINI_CLASSIFY_MODEL` (cheap) and `GEMINI_EXTRACT_MODEL` (accurate).
2. From `backend/`:

```bash
uv sync --group dev
uv run uvicorn draftly_api.main:app --reload --port 8000
```

Health: `GET http://127.0.0.1:8000/health`

Process: `POST http://127.0.0.1:8000/api/documents/process` (multipart `file`).

## Gates

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract tests/conformance
```
