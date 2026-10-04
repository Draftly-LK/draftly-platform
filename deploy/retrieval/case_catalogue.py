"""Platform-owned v1 frozen catalogue. Research paths are build inputs only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class CatalogueUnavailableError(Exception):
    pass


def record_coverage(path: Path, index_path: Path) -> None:
    """Freeze engine population and catalogue intersection during image build."""
    with sqlite3.connect(path) as conn:
        conn.execute("ATTACH DATABASE ? AS retrieval", (str(index_path),))
        count = conn.execute("SELECT COUNT(*) FROM retrieval.cases").fetchone()[0]
        overlap = conn.execute(
            "SELECT COUNT(*) FROM retrieval.cases r JOIN cases c ON r.case_id=c.id"
        ).fetchone()[0]
        manifest = json.loads(conn.execute("SELECT data FROM manifest").fetchone()[0])
        manifest.update(retrievalRecords=count, readerOverlapRecords=overlap)
        conn.execute("UPDATE manifest SET data=?", (json.dumps(manifest, sort_keys=True),))
    path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def build_catalogue(inputs: dict[str, Path], output: Path) -> dict[str, Any]:
    checksums = {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()
    }
    version = (
        "commonlii-v1-"
        + hashlib.sha256(json.dumps(checksums, sort_keys=True).encode()).hexdigest()[:16]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output) as conn:
        conn.executescript(
            "DROP TABLE IF EXISTS cases; DROP TABLE IF EXISTS manifest; CREATE TABLE cases (id TEXT PRIMARY KEY, collection TEXT NOT NULL, year INTEGER NOT NULL, title TEXT NOT NULL, citation TEXT NOT NULL, court TEXT, raw_json TEXT NOT NULL); CREATE INDEX case_order ON cases(year DESC,id); CREATE TABLE manifest (data TEXT NOT NULL);"
        )
        counts = {}
        for collection, path in inputs.items():
            counts[collection] = 0
            with path.open(encoding="utf-8") as source:
                for line in source:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    case_id = "commonlii-" + row["case_id"]
                    year = int(row.get("reported_year") or row["case_id"].split("-")[1])
                    conn.execute(
                        "INSERT INTO cases VALUES(?,?,?,?,?,?,?)",
                        (
                            case_id,
                            collection,
                            year,
                            row.get("case_name") or row["case_id"],
                            row.get("neutral_citation") or "",
                            row.get("deciding_court"),
                            json.dumps(row, ensure_ascii=False),
                        ),
                    )
                    counts[collection] += 1
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "corpusVersion": version,
            "inputSha256": checksums,
            "collections": counts,
            "catalogueRecords": sum(counts.values()),
            "verificationState": "parsed-unverified",
            "defaultDisplayPolicy": "metadata-only",
            "audience": "authenticated-library",
            "minYear": conn.execute("SELECT MIN(year) FROM cases").fetchone()[0],
            "maxYear": conn.execute("SELECT MAX(year) FROM cases").fetchone()[0],
        }
        conn.execute("INSERT INTO manifest VALUES(?)", (json.dumps(manifest, sort_keys=True),))
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


class CaseCatalogue:
    def __init__(
        self,
        path: Path,
        *,
        approval: dict[str, Any] | None = None,
        retrieval_records: int | None = None,
        reader_overlap: int | None = None,
    ) -> None:
        self.path = path
        if approval is not None and not isinstance(approval, dict):
            raise CatalogueUnavailableError()
        if approval and (
            approval.get("audience") not in {"authenticated-library", "internal-research"}
            or not isinstance(approval.get("approvalReference"), str)
            or not approval["approvalReference"].strip()
            or not isinstance(approval.get("userIds"), list)
            or not all(isinstance(user_id, str) and user_id for user_id in approval["userIds"])
            or not isinstance(approval.get("records"), dict)
            or not all(
                isinstance(case_id, str)
                and isinstance(checksum, str)
                and re.fullmatch(r"[a-f0-9]{64}", checksum)
                for case_id, checksum in approval["records"].items()
            )
        ):
            raise CatalogueUnavailableError()
        self.approval = approval or {}
        self.retrieval_records = retrieval_records
        self.reader_overlap = reader_overlap

    def connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise CatalogueUnavailableError() from exc

    def envelope(self, conn: sqlite3.Connection) -> dict[str, Any]:
        manifest = json.loads(conn.execute("SELECT data FROM manifest").fetchone()[0])
        return {
            "corpusVersion": manifest["corpusVersion"],
            "coverage": {
                "catalogueRecords": manifest["catalogueRecords"],
                "retrievalRecords": self.retrieval_records
                if self.retrieval_records is not None
                else manifest.get("retrievalRecords", 0),
                "readerOverlapRecords": self.reader_overlap
                if self.reader_overlap is not None
                else manifest.get("readerOverlapRecords", 0),
                "collections": manifest["collections"],
                "retrievalScope": "conveyancing-only",
                "minYear": manifest["minYear"],
                "maxYear": manifest["maxYear"],
            },
        }

    def project(
        self, row: sqlite3.Row, *, actor_id: str | None = None, allow_text: bool = False
    ) -> dict[str, Any]:
        raw = json.loads(row["raw_json"])
        text = raw.get("text") or ""
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        approval = self.approval
        allowed = (
            allow_text
            and bool(actor_id)
            and approval.get("audience") == "authenticated-library"
            and bool(approval.get("approvalReference"))
            and actor_id in approval.get("userIds", [])
            and approval.get("records", {}).get(row["id"]) == checksum
        )
        warnings = [
            label
            for key, label in (
                ("has_encoding_errors", "encoding-errors"),
                ("has_page_missed", "missing-pages"),
                ("has_malformed_tags", "malformed-tags"),
            )
            if raw.get(key)
        ]
        if not raw.get("deciding_court"):
            warnings.append("deciding-court-unparsed")
        file = (
            raw.get("file")
            or row["id"].removeprefix("commonlii-").split("-", 1)[-1].replace("-", "/") + ".html"
        )
        return {
            "id": row["id"],
            "title": row["title"],
            "citation": row["citation"],
            "collection": row["collection"],
            "decidingCourt": row["court"],
            "year": row["year"],
            "decisionDate": raw.get("decision_date"),
            "reportSeries": raw.get("report_series"),
            "sourceUrl": f"https://www.commonlii.org/lk/cases/{row['collection']}/{file}",
            "provenance": "commonlii-parsed",
            "verificationState": "parsed-unverified",
            "qualityWarnings": warnings,
            "displayPolicy": "full-text" if allowed else "metadata-only",
            "textSha256": checksum,
            "text": text if allowed else None,
            "displayApprovalReference": approval["approvalReference"] if allowed else None,
        }

    def list(
        self,
        *,
        query: str | None = None,
        collection: str | None = None,
        court: str | None = None,
        year: int | None = None,
        limit: int = 25,
        after_id: str | None = None,
        after_year: int | None = None,
    ) -> dict[str, Any]:
        clauses, values = [], []
        if query:
            clauses.append(
                "(instr(lower(title),lower(?)) > 0 OR instr(lower(citation),lower(?)) > 0)"
            )
            values.extend([query, query])
        for column, value in (("collection", collection), ("court", court), ("year", year)):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        if after_id is not None:
            clauses.append("(year < ? OR (year = ? AND id > ?))")
            values.extend([after_year, after_year, after_id])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            with self.connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM cases" + where + " ORDER BY year DESC,id LIMIT ?",
                    [*values, min(max(limit, 1), 100) + 1],
                ).fetchall()
                return {
                    **self.envelope(conn),
                    "items": [self.project(row) for row in rows[:limit]],
                    "hasMore": len(rows) > limit,
                }
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise CatalogueUnavailableError() from exc

    def detail(self, case_id: str, *, actor_id: str | None = None) -> dict[str, Any] | None:
        try:
            with self.connect() as conn:
                envelope = self.envelope(conn)
                row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
                return (
                    {**envelope, "item": self.project(row, actor_id=actor_id, allow_text=True)}
                    if row
                    else None
                )
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise CatalogueUnavailableError() from exc

    def project_search(self, hits: list[dict[str, Any]]) -> dict[str, Any]:
        with self.connect() as conn:
            items = []
            for hit in hits:
                signals = hit.get("matched_signals", [])
                if not set(signals) & {"lexical", "graph"}:
                    continue
                row = conn.execute("SELECT * FROM cases WHERE id=?", (hit["case_id"],)).fetchone()
                record = self.project(row) if row else None
                items.append(
                    {
                        "case": record,
                        "id": hit["case_id"],
                        "title": record["title"] if record else hit.get("title", hit["case_id"]),
                        "citation": record["citation"] if record else hit.get("citation", ""),
                        "sourceUrl": record["sourceUrl"] if record else hit.get("url", ""),
                        "score": hit["score"],
                        "matchedSignals": signals,
                        "readerAvailable": row is not None,
                        "excerpt": (hit.get("excerpt") or "")[:900],
                    }
                )
            return {
                **self.envelope(conn),
                "items": items,
                "outcome": "similar_cases_found" if items else "no_similar_cases",
                "degradedChannels": [],
                "denseStatus": "disabled",
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lkca", type=Path, required=True)
    parser.add_argument("--lksc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_catalogue({"LKCA": args.lkca, "LKSC": args.lksc}, args.output)
