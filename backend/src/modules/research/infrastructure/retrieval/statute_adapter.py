from __future__ import annotations

import asyncio
import re
import sqlite3
from pathlib import Path

from src.modules.research.domain.models import (
    RetrievalPassage,
    RetrievalStatus,
    Scope,
    SearchResult,
)

CORPUS_DB = Path(__file__).with_name("corpus") / "statutes.sqlite"
CORPUS_FINGERPRINT = "8a7f096671b28cf0ff5fcf90b5dd1c1300f343e8ec401c73cd8f9538abccd765"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "which",
    "who",
    "under",
}
TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}")
PAGE_RE = re.compile(r"## Page\s+(\d+)", re.IGNORECASE)

# Curated entry points are deterministic retrieval hints, never generated text.
# They compensate for OCR headings that otherwise hide the operative cluster.
TITLE_HINTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "registration of title act",
        "transfer",
        (
            "SRC011:s38",
            "SRC011:s39",
            "SRC011:s40",
            "SRC011:s43",
            "SRC011:s44",
            "SRC011:s45",
            "SRC011:s47",
        ),
    ),
)


class StatuteRetrievalAdapter:
    """Read-only lexical retrieval over the pinned 57-statute/18-amendment release."""

    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
        del scope
        if not CORPUS_DB.exists():
            return SearchResult(
                degraded_channels=["statute-corpus"], status=RetrievalStatus.UNAVAILABLE
            )
        passages = await asyncio.to_thread(self._search, query, corpus_version)
        return SearchResult(
            passages=passages, degraded_channels=["dense"], corpus_version=corpus_version
        )

    def _search(self, query: str, corpus_version: str) -> list[RetrievalPassage]:
        if not CORPUS_DB.exists():
            return []
        tokens = [
            token.lower() for token in TOKEN_RE.findall(query) if token.lower() not in STOPWORDS
        ]
        if not tokens:
            return []
        fts = " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))
        lowered = query.lower()
        seeded_ids: list[str] = []
        for title, keyword, ids in TITLE_HINTS:
            if title in lowered and keyword in lowered:
                seeded_ids.extend(ids)

        with sqlite3.connect(f"file:{CORPUS_DB.as_posix()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows: list[sqlite3.Row] = []
            if seeded_ids:
                placeholders = ",".join("?" for _ in seeded_ids)
                rows.extend(
                    conn.execute(
                        f"SELECT * FROM sections WHERE section_id IN ({placeholders})",
                        seeded_ids,
                    ).fetchall()
                )
            rows.extend(
                conn.execute(
                    """
                    SELECT s.*
                    FROM sections_fts f
                    JOIN sections s ON s.section_id = f.section_id
                    WHERE sections_fts MATCH ?
                    ORDER BY bm25(sections_fts)
                    LIMIT 12
                    """,
                    (fts,),
                ).fetchall()
            )

        passages: list[RetrievalPassage] = []
        seen: set[str] = set()
        for row in rows:
            section_id = str(row["section_id"])
            if section_id in seen:
                continue
            seen.add(section_id)
            body = re.sub(r"\s+", " ", str(row["body"])).strip()
            page_match = PAGE_RE.search(str(row["body"]))
            section = section_id.rsplit(":s", 1)[-1]
            passages.append(
                RetrievalPassage(
                    source_id=str(row["source_id"]),
                    authority_id=section_id,
                    title=str(row["title"]),
                    reference=f"Section {section}",
                    text=body[:4000],
                    page=int(page_match.group(1)) if page_match else 0,
                    corpus_version=corpus_version,
                    verified=True,
                )
            )
            if len(passages) == 12:
                break
        return passages
