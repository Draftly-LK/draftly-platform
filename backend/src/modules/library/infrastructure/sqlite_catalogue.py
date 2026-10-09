from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import cast

from src.modules.corpus_governance.infrastructure.manifest import validate_release
from src.modules.library.domain.models import AuthorityType, LegalSourceSummary

CORPUS_DIRECTORY = (
    Path(__file__).parents[2] / "research" / "infrastructure" / "retrieval" / "corpus"
)
CORPUS_DB = CORPUS_DIRECTORY / "statutes.sqlite"
RELEASE_MANIFEST = CORPUS_DIRECTORY / "release.json"
PUBLIC_RELEASE = Path("/run/draftly/public-catalogue")
PUBLIC_TRUST = Path("/run/draftly/trust/public-catalogue.pub")
PUBLIC_ACTIVE = Path("/run/draftly/current-public-release")


class SqliteLegalCatalogue:
    """Policy-limited catalogue view over the pinned public statute release."""

    def __init__(
        self, database_path: Path = CORPUS_DB, manifest_path: Path = RELEASE_MANIFEST
    ) -> None:
        self.database_path = database_path
        self.manifest_path = manifest_path

    async def list_authorities(
        self, authority_type: AuthorityType | None = None, query: str | None = None
    ) -> list[LegalSourceSummary]:
        return await asyncio.to_thread(self._read, None, authority_type, query)

    async def get_authority(self, authority_id: str) -> LegalSourceSummary | None:
        rows = await asyncio.to_thread(self._read, authority_id, None, None)
        return rows[0] if rows else None

    def _read(
        self,
        authority_id: str | None,
        authority_type: AuthorityType | None,
        query: str | None,
    ) -> list[LegalSourceSummary]:
        if PUBLIC_RELEASE.exists() or PUBLIC_TRUST.exists() or PUBLIC_ACTIVE.exists():
            release = validate_release(
                (PUBLIC_RELEASE / "manifest.json").read_bytes(),
                (PUBLIC_RELEASE / "manifest.sig").read_bytes(),
                PUBLIC_TRUST.read_bytes(),
                "public-catalogue",
                PUBLIC_RELEASE,
            )
            if PUBLIC_ACTIVE.read_text(encoding="utf-8").strip() != release.release_version:
                raise RuntimeError("Public catalogue release is withdrawn or unavailable")
            return [
                LegalSourceSummary(
                    id=m.source_id,
                    title=m.title,
                    reference=m.reference,
                    type=m.kind,
                    weight="unverified-candidate",
                    verified=m.review_state == "approved",
                    section_count=0,
                    source_url=m.source_url,
                    extraction_confidence="reviewed-source-metadata",
                    corpus_version=release.release_version,
                    metadata=m,
                )
                for entry in release.sources
                for m in (entry.source.metadata,)
                if (authority_id is None or m.source_id == authority_id)
                and (authority_type is None or m.kind == authority_type)
                and (not query or query.casefold() in (m.title + " " + m.reference).casefold())
            ]
        if not self.database_path.exists() or not self.manifest_path.exists():
            raise RuntimeError("The pinned legal catalogue release is unavailable.")

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        checksum = hashlib.sha256(self.database_path.read_bytes()).hexdigest()
        if manifest.get("sqliteSha256") != checksum:
            raise RuntimeError("The pinned legal catalogue checksum differs from its release")
        verified = False  # Legacy metadata is unsigned; folder/title never establish review.
        corpus_version = "statutes-bundled-v1:" + checksum
        clauses: list[str] = []
        parameters: list[str] = []
        if authority_id:
            clauses.append("source_id = ?")
            parameters.append(authority_id)
        if authority_type:
            clauses.append("kind = ?")
            parameters.append(authority_type)
        if query and query.strip():
            clauses.append("(lower(title) LIKE ? OR act_number LIKE ? OR year LIKE ?)")
            pattern = f"%{query.strip().lower()}%"
            parameters.extend([pattern, pattern, pattern])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT source_id, kind, MAX(title) AS title,
                   MAX(act_number) AS act_number, MAX(year) AS year,
                   MAX(public_source_url) AS public_source_url,
                   MAX(extraction_confidence) AS extraction_confidence,
                   COUNT(*) AS section_count
            FROM sections
            {where}
            GROUP BY source_id, kind
            ORDER BY lower(MAX(title)), CAST(MAX(year) AS INTEGER), source_id
        """
        with sqlite3.connect(
            f"file:{self.database_path.as_posix()}?mode=ro", uri=True
        ) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql, parameters).fetchall()

        return [
            LegalSourceSummary(
                id=str(row["source_id"]),
                title=str(row["title"]),
                reference=f"No. {row['act_number']} of {row['year']}",
                type=cast(AuthorityType, str(row["kind"])),
                weight="binding" if verified else "unverified-candidate",
                verified=verified,
                section_count=int(row["section_count"]),
                source_url=str(row["public_source_url"]),
                extraction_confidence=str(row["extraction_confidence"]),
                corpus_version=corpus_version,
            )
            for row in rows
        ]
