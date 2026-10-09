from __future__ import annotations

import re

import httpx
import structlog
from pydantic import TypeAdapter

from src.modules.corpus_governance.contracts import AuthorityMetadata
from src.modules.research.domain.models import (
    AuthorityKind,
    RetrievalPassage,
    RetrievalStatus,
    Scope,
    SearchResult,
)

log = structlog.get_logger(__name__)
_VERSION = re.compile(r"(?:statutes-index-v1|legal-index-v2):[0-9a-f]{64}")
_GAZETTE = re.compile(r"\bGazette(?:\s+Extraordinary)?\s*(?:No\.?\s*)?\d{3,5}/\d{1,3}", re.I)
_METADATA = TypeAdapter(list[AuthorityMetadata])


class HttpStatuteRetrievalAdapter:
    """Read-only private transport; only the actual frozen producer supplies identity."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url, self._timeout, self._transport = base_url.rstrip("/"), timeout, transport

    async def passages_available(self, source_ids: tuple[str, ...], *, corpus_version: str) -> bool:
        if not source_ids or re.fullmatch(r"legal-index-v2:[0-9a-f]{64}", corpus_version) is None:
            return False
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(
                    f"{self._base_url}/v1/legal-authorities/availability",
                    params=[
                        ("release_version", corpus_version),
                        *[("source_id", key) for key in source_ids],
                    ],
                )
                response.raise_for_status()
                data = response.json()
                return bool(
                    isinstance(data, dict)
                    and data.get("available") is True
                    and data.get("corpusVersion") == corpus_version
                    and response.headers.get("X-Draftly-Corpus-Version") == corpus_version
                )
        except (httpx.HTTPError, ValueError, TypeError):
            return False

    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
        del scope, corpus_version
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(
                    f"{self._base_url}/search", params={"q": query, "limit": 12}
                )
                response.raise_for_status()
                hits = response.json()
                version = response.headers.get("X-Draftly-Corpus-Version", "")
                if not isinstance(hits, list) or _VERSION.fullmatch(version) is None:
                    raise ValueError("Unattested retrieval response")
                authorities: tuple[AuthorityMetadata, ...] = ()
                source_version = None
                gaps = ["authority-metadata-unsupported"]
                references = _GAZETTE.findall(query)
                if version.startswith("legal-index-v2:"):
                    ids = {
                        h["source_id"]
                        for h in hits
                        if isinstance(h, dict) and isinstance(h.get("source_id"), str)
                    }
                    ids.update(value.upper() for value in re.findall(r"\bSRC\d+\b", query, re.I))
                    metadata_response = await client.get(
                        f"{self._base_url}/v1/legal-authorities",
                        params=[
                            ("release_version", version),
                            *[("source_id", key) for key in sorted(ids)],
                            *[("reference", value) for value in references],
                        ],
                    )
                    metadata_response.raise_for_status()
                    data = metadata_response.json()
                    if (
                        not isinstance(data, dict)
                        or data.get("corpusVersion") != version
                        or metadata_response.headers.get("X-Draftly-Corpus-Version") != version
                    ):
                        raise ValueError("Metadata release mismatch")
                    source_version = data.get("sourceReleaseVersion")
                    if (
                        not isinstance(source_version, str)
                        or re.fullmatch(r"legal-sources-v1:[0-9a-f]{64}", source_version) is None
                    ):
                        raise ValueError("Source envelope identity missing")
                    authorities = tuple(_METADATA.validate_python(data["authorities"]))
                    if any(a.release_version != version for a in authorities) or len(
                        {a.source_id for a in authorities}
                    ) != len(authorities):
                        raise ValueError("Authority release mismatch")
                    gaps = data["coverageGaps"]
                    if not isinstance(gaps, list) or any(not isinstance(g, str) for g in gaps):
                        raise ValueError("Invalid coverage response")
                elif references:
                    gaps.append("requested-authority-missing")
                if any(
                    isinstance(hit, dict) and hit.get("passages_withheld") is True for hit in hits
                ):
                    gaps = list(dict.fromkeys([*gaps, "source-passages-withheld"]))
                by_id = {a.source_id: a for a in authorities}
                passages = []
                for hit in hits:
                    if (
                        not isinstance(hit, dict)
                        or not isinstance(hit.get("excerpt"), str)
                        or not hit["excerpt"].strip()
                    ):
                        continue
                    source_id, section_id = hit.get("source_id"), hit.get("section_id")
                    if not isinstance(source_id, str) or not isinstance(section_id, str):
                        raise ValueError("Invalid passage identity")
                    metadata = by_id.get(source_id)
                    if version.startswith("legal-index-v2:") and metadata is None:
                        raise ValueError("Passage lacks signed metadata")
                    kind = AuthorityKind(metadata.kind) if metadata else AuthorityKind.STATUTE
                    section = section_id.rsplit(":s", 1)[-1]
                    passages.append(
                        RetrievalPassage(
                            source_id=source_id,
                            authority_id=section_id,
                            title=metadata.title if metadata else str(hit.get("title", "")),
                            reference=metadata.reference
                            if metadata and hit.get("extraction_confidence") == "document_fallback"
                            else f"Section {section}",
                            text=hit["excerpt"],
                            page=0,
                            corpus_version=version,
                            verified=bool(metadata and metadata.review_state == "approved"),
                            kind=kind,
                            source_url=metadata.source_url if metadata else None,
                            authority_metadata=metadata,
                        )
                    )
                # An exact missing Gazette cannot be answered from unrelated topical Acts.
                if "requested-authority-missing" in gaps:
                    passages = []
                return SearchResult(
                    passages=passages,
                    degraded_channels=["dense", "graph"],
                    corpus_version=version,
                    source_release_version=source_version,
                    authorities=authorities,
                    coverage_gaps=gaps,
                )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("research.retrieval_engine_unavailable", error_class=type(exc).__name__)
            return SearchResult(
                degraded_channels=["retrieval-engine"],
                coverage_gaps=["source-release-unavailable"],
                status=RetrievalStatus.UNAVAILABLE,
            )
