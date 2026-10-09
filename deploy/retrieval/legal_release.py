"""Versioned platform input adapter over the existing frozen statute engine.

No ranking algorithm lives here. The five inspected package modules are checked
before their explicit parser/index builder interfaces accept release-listed bytes.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

from src.modules.corpus_governance.infrastructure.manifest import (
    canonical_manifest_bytes,
    validate_release,
    validate_release_metadata,
)

MODULE_HASHES = {
    "api": "ec3af137da742932e94a9c7c64b2e31e37b3accac56993fb6d8fe95a574c8043",
    "corpus": "596167e4fce6edf5354324592bc0098ca20954a6c709c2258d3d3be9143e7073",
    "index": "701b1427868c0400f31bd610683589747db8bce845ade10303ba350b63bece01",
    "models": "9f13f67bea1d724849a9b3e9f7c3e072d4d3fdee65fcf822f3257f5e6ed03907",
    "section_parser": "0355c1cb4f7ebd06ee2df1e6c2a066024d67bd68d23fe517d080f70ac835c4f4",
}
BOUNDARY = "draftly-retrieval-eb47114a-platform-v1"
TRUST = Path("/app/trust/legal-release.pub")
REQUIRED = Path("/app/trust/legal-release.required")
ACTIVE = Path("/run/draftly/legal-active-release")
GAZETTE = re.compile(r"\bGazette(?:\s+Extraordinary)?\s*(?:No\.?\s*)?(\d{3,5}/\d{1,3})", re.I)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def engine():
    import draftly.retrieval.corpus as corpus
    import draftly.retrieval.index as index

    directory = Path(index.__file__).parent
    for name, expected in MODULE_HASHES.items():
        if digest((directory / f"{name}.py").read_bytes().replace(b"\r\n", b"\n")) != expected:
            raise RuntimeError("Unsupported legal retrieval package boundary")
    return corpus, index


def artifact_file(index):
    return Path(index.INDEX_DIR).parent / "frozen-legal-release.json"


def install_inputs(corpus, index, sources, fingerprint):
    rows = [
        {"source_id": s.metadata.source_id, "kind": s.metadata.kind, "title": s.metadata.title}
        for s in sources
        if s.indexed is not None
    ]
    # index imports aliases directly; changing corpus alone would still walk CSVs.
    corpus.load_statute_documents = index.load_statute_documents = lambda: rows
    corpus.corpus_fingerprint = index.corpus_fingerprint = lambda documents: fingerprint
    corpus.ALLOWED_KINDS = {"statute", "amendment", "gazette"}
    corpus.load_registry = lambda: {}
    corpus.load_topic_maps = lambda: ({}, {})
    return rows


def build(source_root=Path("/release-input"), trust=Path("/run/secrets/legal_release_trust")):
    manifest = source_root / "manifest.json"
    TRUST.parent.mkdir(parents=True, exist_ok=True)
    if not manifest.exists():
        if trust.exists() or any(p.name != "README.md" for p in source_root.iterdir()):
            raise RuntimeError("Incomplete supplied legal release; legacy fallback refused")
        subprocess.run(
            [sys.executable, "-m", "draftly.retrieval", "build", *sys.argv[1:]], check=True
        )
        return
    if sys.argv[1:]:
        raise RuntimeError("Metadata-aware embedding builds are not supported by this boundary")
    raw, signature, key = (
        manifest.read_bytes(),
        (source_root / "manifest.sig").read_bytes(),
        trust.read_bytes(),
    )
    release = validate_release(raw, signature, key, "internal-research", source_root)
    corpus, index = engine()
    fingerprint = digest(raw)
    rows = install_inputs(corpus, index, [e.source for e in release.sources], fingerprint)
    parser = importlib.import_module("draftly.retrieval.section_parser")
    nodes = []
    for entry in release.sources:
        if entry.indexed_content is None:
            continue
        m = entry.source.metadata
        nodes.extend(
            parser.parse_sections(
                source_id=m.source_id,
                doc_id=m.source_id,
                kind=m.kind,
                title=m.title,
                act_number=m.reference,
                year="",
                topics=(),
                public_source_url=m.source_url,
                source_sha256=m.source_sha256,
                text=entry.indexed_content.decode("utf-8"),
            )
        )
    summary = {
        "documents": len(rows),
        "statutes": sum(r["kind"] == "statute" for r in rows),
        "amendments": sum(r["kind"] == "amendment" for r in rows),
        "gazettes": sum(r["kind"] == "gazette" for r in rows),
        "sections": len(nodes),
        "fallbacks": sum(n.extraction_confidence == "document_fallback" for n in nodes),
        "fingerprint": fingerprint,
    }
    # The existing parser, database writer, FTS tables and ranker remain in use.
    index.build_section_nodes = lambda documents: (nodes, summary)
    guard = "CHECK (kind IN ('statute', 'amendment'))"
    if index.SCHEMA.count(guard) != 1:
        raise RuntimeError("Unsupported statutory index schema")
    index.SCHEMA = index.SCHEMA.replace(
        guard, "CHECK (kind IN ('statute', 'amendment', 'gazette'))"
    )
    stats = index.build_index(force=True)
    attestation = {
        "protocol": "legal-index-v2",
        "sourceReleaseVersion": release.release_version,
        "indexSha256": digest(Path(stats.db_path).read_bytes()),
        "engineBoundary": BOUNDARY,
        "engineModules": MODULE_HASHES,
    }
    record = {
        "attestation": attestation,
        "indexFile": Path(stats.db_path).name,
        "fingerprint": fingerprint,
        "manifest": base64.b64encode(raw).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    artifact_file(index).write_bytes(canonical_manifest_bytes(record))
    # Public trust material comes ONLY from the independent build secret, never
    # from the release input. No signing material or active-release grant is created.
    TRUST.write_bytes(key)
    # This immutable image marker records required governance, not permission to
    # publish. The independently mounted ACTIVE grant is still compulsory.
    REQUIRED.write_text("legal-index-v2\n", encoding="utf-8")


def statute_fingerprint():
    import draftly.retrieval.index as index

    record = artifact_file(index)
    if record.exists():
        return json.loads(record.read_bytes())["fingerprint"]
    from draftly.retrieval.corpus import corpus_fingerprint, load_statute_documents

    return corpus_fingerprint(load_statute_documents())


class FrozenRelease:
    def __init__(self, record_path, trust=TRUST, active=ACTIVE):
        self.active = active
        record = json.loads(record_path.read_bytes())
        raw = base64.b64decode(record["manifest"], validate=True)
        signature = base64.b64decode(record["signature"], validate=True)
        self.source_version, sources = validate_release_metadata(
            raw, signature, trust.read_bytes(), "internal-research"
        )
        self.sources = {s.metadata.source_id: s for s in sources}
        self.corpus, self.index = engine()
        self.fingerprint = digest(raw)
        name = record["indexFile"]
        if not isinstance(name, str) or Path(name).name != name:
            raise RuntimeError("Invalid frozen legal artifact")
        self.database = Path(self.index.INDEX_DIR) / name
        expected = {
            "protocol": "legal-index-v2",
            "sourceReleaseVersion": self.source_version,
            "indexSha256": digest(self.database.read_bytes()),
            "engineBoundary": BOUNDARY,
            "engineModules": MODULE_HASHES,
        }
        if record["attestation"] != expected or record["fingerprint"] != self.fingerprint:
            raise RuntimeError("Frozen metadata/index attestation mismatch")
        self.index_sha = expected["indexSha256"]
        self.version = "legal-index-v2:" + digest(canonical_manifest_bytes(expected))
        if self.index.read_active_index(self.fingerprint) != self.database:
            raise RuntimeError("Frozen legal index pointer mismatch")
        install_inputs(self.corpus, self.index, sources, self.fingerprint)

    def check_current(self):
        if self.active.read_text(encoding="utf-8").strip() != self.version:
            raise RuntimeError("Legal release is unavailable or withdrawn")
        if digest(self.database.read_bytes()) != self.index_sha:
            raise RuntimeError("Frozen legal index changed")
        if self.index.read_active_index(self.fingerprint) != self.database:
            raise RuntimeError("Frozen legal index pointer changed")

    def permits(self, source_id):
        source = self.sources.get(source_id)
        return bool(
            source
            and source.indexed is not None
            and source.policy.display in {"full-text", "snippet-only"}
            and source.policy.quotation in {"approved-span", "short-quotation-only"}
            and source.policy.quotation_hashes
            and source.policy.quotation_character_limit is not None
        )

    def selected(self, source_ids, references=()):
        selected = {s for s in source_ids if s in self.sources}
        missing = bool(set(source_ids) - self.sources.keys())
        for reference in references:
            number = GAZETTE.search(reference)
            found = {
                key
                for key, s in self.sources.items()
                if (
                    number
                    and s.metadata.kind == "gazette"
                    and re.search(rf"(?<!\d){re.escape(number[1])}(?!\d)", s.metadata.reference)
                )
                or s.metadata.reference.casefold() == reference.casefold()
            }
            selected.update(found)
            missing |= not found
        related = set(selected)
        for key, source in self.sources.items():
            for edge in source.metadata.relationships:
                if edge.review_state == "reviewed":
                    if key in selected:
                        related.add(edge.target_source_id)
                    if edge.target_source_id in selected:
                        related.add(key)
        return related, missing

    def metadata(self, source_ids, references=()):
        selected, missing = self.selected(source_ids, references)
        records = [
            asdict(replace(s.metadata, release_version=self.version))
            for key, s in self.sources.items()
            if key in selected and s.policy.display != "blocked"
        ]
        gaps = ["requested-authority-missing"] if missing else []
        if selected - self.sources.keys():
            gaps.append("related-authority-missing")
        if any(key in self.sources and not self.permits(key) for key in selected):
            gaps.append("source-passages-withheld")
        if any(
            key in self.sources and not self.sources[key].policy.quotation_hashes
            for key in selected
        ):
            gaps.append("quotation-boundary-unavailable")
        return {
            "corpusVersion": self.version,
            "sourceReleaseVersion": self.source_version,
            "authorities": records,
            "coverageGaps": gaps,
        }

    def search(self, query, limit=12, kinds=None, source_id=None):
        from draftly.retrieval.models import StatuteQuery
        from draftly.retrieval.search import search

        direct = {
            key
            for key, s in self.sources.items()
            if re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", query, re.I)
            or s.metadata.reference.casefold() in query.casefold()
        }
        refs = [m.group(0) for m in GAZETTE.finditer(query)]
        selected, _ = self.selected(direct, refs)
        hits = []
        # Exact IDs go back through the existing engine's direct-section query.
        with self.index.connect() as conn:
            for key in sorted(selected & self.sources.keys()):
                for row in conn.execute(
                    "SELECT section_id FROM sections WHERE source_id = ? ORDER BY section_id LIMIT 2",
                    (key,),
                ):
                    hits.extend(search(StatuteQuery(text=row["section_id"], limit=2)))
        hits.extend(search(StatuteQuery(text=query, limit=limit)))
        result, seen, short_sources, quoted_characters = [], set(), set(), {}
        for hit in hits:
            if hit.section_id in seen or hit.source_id not in self.sources:
                continue
            seen.add(hit.section_id)
            selected.add(hit.source_id)
            if not self.permits(hit.source_id):
                continue
            source = self.sources[hit.source_id]
            if (kinds and source.metadata.kind not in kinds) or (
                source_id and hit.source_id != source_id
            ):
                continue
            if source.policy.quotation == "short-quotation-only":
                if hit.source_id in short_sources:
                    continue
            # Other native hit strings (heading, citation_note, matched_queries)
            # are not covered by this exact excerpt grant and are not projected.
            item = {
                "source_id": hit.source_id,
                "section_id": hit.section_id,
                "title": source.metadata.title,
                "document_type": source.metadata.kind,
                "public_source_url": source.metadata.source_url,
                "extraction_confidence": hit.extraction_confidence,
                "excerpt": hit.excerpt,
            }
            # A transport cap cannot grant rights. Emit only the exact reviewed
            # UTF-8 excerpt, bounded by the independently signed quotation grant.
            if (
                digest(item["excerpt"].encode("utf-8")) not in source.policy.quotation_hashes
                or quoted_characters.get(hit.source_id, 0) + len(item["excerpt"])
                > source.policy.quotation_character_limit
            ):
                continue
            if source.policy.quotation == "short-quotation-only":
                short_sources.add(hit.source_id)
            quoted_characters[hit.source_id] = quoted_characters.get(hit.source_id, 0) + len(
                item["excerpt"]
            )
            result.append(item)
        result = result[:limit]
        represented = {h["source_id"] for h in result}
        for key in sorted(selected - represented):
            source = self.sources.get(key)
            if (
                source
                and source.policy.display != "blocked"
                and (not kinds or source.metadata.kind in kinds)
                and (not source_id or key == source_id)
            ):
                result.append(
                    {
                        "source_id": key,
                        "section_id": key + ":metadata",
                        "excerpt": "",
                        "title": source.metadata.title,
                        "document_type": source.metadata.kind,
                        "passages_withheld": True,
                    }
                )
        return result


if __name__ == "__main__":
    build()
