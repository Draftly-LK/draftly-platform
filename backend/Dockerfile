# syntax=docker/dockerfile:1.7
#
# Draftly API (FastAPI). Build context is backend/:
#
#   docker build -t draftly-backend backend
#
# One image, three commands: the API (default CMD), migrations
# (`alembic upgrade head`) and the outbox worker (`python -m src.workers.runner`).

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies only. The project itself is not installed: its importable module
# is the literal `src/` directory, which resolves from the working directory.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --system --uid 10001 --no-create-home draftly
# WORKDIR must be the backend root: alembic.ini, `src` imports and the relative
# SOURCE_FILE_STORAGE_DIR (.data/source-files) all resolve against it.
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY alembic.ini ./
COPY migrations migrations
COPY src src
RUN mkdir -p .data/source-files && chown -R draftly .data
USER draftly
VOLUME ["/app/.data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status == 200 else 1)"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
