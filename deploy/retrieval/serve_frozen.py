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

This stands in for the research repo's `DRAFTLY_INDEX_FROZEN` mode until that
mode is on its main branch; it patches nothing else.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import draftly.case_retrieval.index as case_index
import draftly.retrieval.index as statute_index

FINGERPRINTS = Path(statute_index.INDEX_DIR).parent / "frozen-fingerprints.json"

_recorded = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
_statutes: str = _recorded["statutes"]
_cases: str = _recorded["cases"]

statute_index.corpus_fingerprint = lambda documents: _statutes
case_index.corpus_fingerprint = lambda rows: _cases
statute_index.index_build_lock = contextlib.nullcontext
case_index.index_build_lock = contextlib.nullcontext

# Imported last on purpose: the app must load after the patches above.
from draftly.retrieval.api import app  # noqa: E402

__all__ = ["app"]
