"""Serve the retrieval indexes baked into this image, without the source corpus.

The research repository's engine fingerprints its corpus (size and mtime of
every statute and case file, plus the full CommonLII judgment dumps) on startup
and again on every request, and takes a write lock inside the index folder.
In this image the corpus is not shipped, the filesystem is read-only, and
re-hashing ~160 MB of judgments per /similar-cases call would not fit the 1 GB
server anyway.

So the Dockerfile's builder stage records both fingerprints next to the indexes
it built (`frozen-fingerprints.json`), and this module replaces the two
per-request steps with that record before the app is imported:

- `corpus_fingerprint` returns the recorded value, so the active index is
  found exactly as it would be with the corpus present;
- `index_build_lock` is a no-op, since nothing is ever built here.

If the recorded fingerprint does not match the baked index, the engine tries to
rebuild, which fails on the read-only filesystem: it fails closed rather than
serving a stale or mismatched index.

This retains legacy frozen behavior. When a governed artifact is present, the
versioned platform adapter additionally verifies its signed source metadata,
actual index bytes and current release grant, and filters statutory output.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path

import draftly.case_retrieval.index as case_index
import draftly.retrieval.index as statute_index
from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse
from legal_release import FrozenRelease, artifact_file

FINGERPRINTS = Path(statute_index.INDEX_DIR).parent / "frozen-fingerprints.json"

_recorded = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
_statutes: str = _recorded["statutes"]
_cases: str = _recorded["cases"]
_legal_record = artifact_file(statute_index)
_legal = FrozenRelease(_legal_record) if _legal_record.exists() else None

statute_index.corpus_fingerprint = lambda documents: _statutes
case_index.corpus_fingerprint = lambda rows: _cases
statute_index.index_build_lock = contextlib.nullcontext
case_index.index_build_lock = contextlib.nullcontext

# Imported last on purpose: the app must load after the patches above.
from case_api import install_dense_gate, router  # noqa: E402
from draftly.retrieval.api import app  # noqa: E402

install_dense_gate()
app.include_router(router)

# Attest the same frozen artifact used by the engine to select its baked index.
# The hash is an identity, not a claim of legal verification or completeness.
_statute_version = "statutes-index-v1:" + hashlib.sha256(_statutes.encode()).hexdigest()
if _legal is not None:
    if _statutes != _legal.fingerprint:
        raise RuntimeError("Frozen source fingerprint mismatch")
    _statute_version = _legal.version
    # Native /answer does not implement the governed passage policy. The platform
    # composer uses the filtered /search output; this native path remains closed.
    app.router.routes = [
        r
        for r in app.router.routes
        if getattr(r, "path", "") not in {"/search", "/sources", "/topics"}
    ]

    @app.get("/search")
    def governed_search(
        q: str = Query(..., min_length=1),
        limit: int = Query(12, ge=1, le=50),
        kind: list[str] | None = Query(None),
        source_id: str | None = None,
        topic_slug: str | None = None,
    ):
        if kind and set(kind) - {"statute", "amendment", "gazette"}:
            raise HTTPException(422, "Unsupported authority kind")
        if topic_slug is not None:
            raise HTTPException(422, "Governed topic metadata is unavailable")
        return _legal.search(q, limit, kind, source_id)

    @app.get("/sources")
    def governed_sources():
        return [
            {
                "source_id": key,
                "title": s.metadata.title,
                "kind": s.metadata.kind,
                "year": "",
                "act_number": s.metadata.reference,
            }
            for key, s in _legal.sources.items()
            if s.policy.display != "blocked"
        ]

    @app.get("/topics")
    def governed_topics():
        return []


@app.get("/v1/legal-authorities")
def legal_authorities(
    release_version: str,
    source_id: list[str] = Query(default=[]),
    reference: list[str] = Query(default=[]),
):
    if release_version != _statute_version:
        raise HTTPException(409, "Legal release mismatch")
    if _legal is None:
        return {
            "corpusVersion": _statute_version,
            "sourceReleaseVersion": None,
            "authorities": [],
            "coverageGaps": ["authority-metadata-unsupported"],
        }
    return _legal.metadata(source_id, reference)


@app.get("/v1/legal-authorities/availability")
def legal_availability(release_version: str, source_id: list[str] = Query(default=[])):
    available = bool(
        _legal
        and source_id
        and release_version == _statute_version
        and all(_legal.permits(key) for key in source_id)
    )
    return {"available": available, "corpusVersion": _statute_version}


@app.middleware("http")
async def attest_statute_version(request, call_next):
    governed = request.url.path in {
        "/search",
        "/answer",
        "/sources",
        "/topics",
        "/health",
    } or request.url.path.startswith("/v1/legal-authorities")
    if _legal is not None and governed:
        try:
            _legal.check_current()
        except (OSError, ValueError, RuntimeError):
            return JSONResponse({"detail": "Legal release unavailable"}, status_code=503)
        if request.url.path == "/answer":
            return JSONResponse({"detail": "Use governed platform composition"}, status_code=503)
    response = await call_next(request)
    if (
        request.method == "GET"
        and (request.url.path == "/search" or request.url.path.startswith("/v1/legal-authorities"))
        and response.status_code == 200
    ):
        response.headers["X-Draftly-Corpus-Version"] = _statute_version
    return response


__all__ = ["app"]
