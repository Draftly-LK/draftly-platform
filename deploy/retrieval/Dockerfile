# syntax=docker/dockerfile:1.7
#
# Draftly retrieval API (statutes + conveyancing case law).
#
# The engine's code and corpus live in the research repository, which is only a
# build-time input here: it is the main build context, and this folder is passed
# as the named context `deploy`. Normally built through ../build.sh; by hand:
#
#   docker build -f deploy/retrieval/Dockerfile \
#     --build-context deploy=deploy/retrieval -t draftly-retrieval ../draftly
#
# The builder stage indexes the corpus; the runtime stage carries only the code,
# the finished indexes and the small CSVs read per request, and runs with
# DRAFTLY_INDEX_FROZEN=1 so it never re-hashes or rebuilds the corpus.
#
# Dense (embedding) channel is opt-in because it spends Gemini credits: add
#   --build-arg WITH_EMBEDDINGS=1 --secret id=gemini_api_key,env=GEMINI_API_KEY

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src
WORKDIR /app
COPY --from=deploy requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
# paths.py derives REPO_ROOT from this layout (/app/src/draftly/...); do not pip-install the package.
COPY src/draftly/__init__.py src/draftly/__init__.py
COPY src/draftly/retrieval src/draftly/retrieval
COPY src/draftly/case_retrieval src/draftly/case_retrieval


FROM base AS builder
ARG WITH_EMBEDDINGS=0
COPY data/processed/documents.csv data/processed/source-registry.csv \
     data/processed/topics.csv data/processed/topic-sources.csv \
     data/processed/cases.jsonl data/processed/
COPY data/processed/docs/statutes data/processed/docs/statutes
COPY data/processed/docs/amendments data/processed/docs/amendments
COPY data/processed/docs/case-law data/processed/docs/case-law
COPY data/processed/legal-case-index/case_topic_links.csv data/processed/legal-case-index/
COPY data/commonlii/parsed/LKCA/judgments.jsonl data/commonlii/parsed/LKCA/
COPY data/commonlii/parsed/LKSC/judgments.jsonl data/commonlii/parsed/LKSC/
COPY scripts/case-law-statute-linking/output/resolved_links.csv \
     scripts/case-law-statute-linking/output/statute_index.csv \
     scripts/case-law-statute-linking/output/
COPY scripts/case-law-information-extraction/output/rules_high_confidence.csv \
     scripts/case-law-information-extraction/output/
RUN --mount=type=secret,id=gemini_api_key,required=false \
    set -eu; \
    flags=""; \
    if [ "$WITH_EMBEDDINGS" = "1" ]; then \
        [ -s /run/secrets/gemini_api_key ] || { echo "WITH_EMBEDDINGS=1 needs --secret id=gemini_api_key" >&2; exit 1; }; \
        export GEMINI_API_KEY="$(cat /run/secrets/gemini_api_key)"; \
        flags="--with-embeddings"; \
    fi; \
    python -m draftly.retrieval build $flags; \
    python -m draftly.case_retrieval build $flags; \
    rm -f data/processed/retrieval-indexes/*/build.lock


FROM base AS runtime
RUN useradd --system --uid 10001 --no-create-home draftly
COPY --from=builder /app/data/processed/retrieval-indexes data/processed/retrieval-indexes
# Read per request by /topics, /sources, /case-statute-links and the case graph.
COPY data/processed/documents.csv data/processed/source-registry.csv \
     data/processed/topics.csv data/processed/topic-sources.csv data/processed/
COPY scripts/case-law-statute-linking/output/resolved_links.csv \
     scripts/case-law-statute-linking/output/statute_index.csv \
     scripts/case-law-statute-linking/output/
ENV DRAFTLY_INDEX_FROZEN=1
USER draftly
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]
CMD ["uvicorn", "draftly.retrieval.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
