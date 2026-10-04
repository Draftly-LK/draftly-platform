"""Versioned private boundary; only bounded research evidence leaves search."""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Annotated

from case_catalogue import CaseCatalogue, CatalogueUnavailableError
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/cases")
_dense_degraded: ContextVar[bool] = ContextVar("case_dense_degraded", default=False)


def catalogue() -> CaseCatalogue:
    approval = {}
    path = os.getenv("CASE_DISPLAY_APPROVAL_FILE", "")
    if path:
        try:
            approval = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(503, "Case display policy unavailable.") from None
    catalogue_path = Path(os.getenv("CASE_CATALOGUE_PATH", "/app/data/case-catalogue/cases.sqlite"))
    return CaseCatalogue(catalogue_path, approval=approval)


@router.get("")
def list_cases(
    query: str | None = Query(None, max_length=256),
    collection: str | None = Query(None, pattern="^(LKCA|LKSC)$"),
    court: str | None = Query(None, max_length=128),
    year: int | None = Query(None, ge=1700, le=2200),
    limit: int = Query(25, ge=1, le=100),
    after_id: str | None = Query(None, max_length=128),
    after_year: int | None = Query(None, ge=1700, le=2200),
) -> dict:
    try:
        return catalogue().list(
            query=query,
            collection=collection,
            court=court,
            year=year,
            limit=limit,
            after_id=after_id,
            after_year=after_year,
        )
    except CatalogueUnavailableError:
        raise HTTPException(503, "Case corpus unavailable.") from None


@router.get("/{case_id}")
def get_case(
    case_id: str, actor_id: Annotated[str | None, Header(alias="X-Draftly-Actor")] = None
) -> dict:
    try:
        result = catalogue().detail(case_id, actor_id=actor_id)
    except CatalogueUnavailableError:
        raise HTTPException(503, "Case corpus unavailable.") from None
    if result is None:
        raise HTTPException(404, "Case not found.")
    return result


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    limit: int = Field(default=8, ge=1, le=25)


def install_dense_gate() -> None:
    from draftly.case_retrieval import embeddings

    original = embeddings.dense_lookup
    enabled = os.getenv("DRAFTLY_CASE_DENSE_ENABLED") == "1" and bool(
        os.getenv("DRAFTLY_CASE_DENSE_APPROVAL")
    )

    def guarded(query_text: str, *, limit: int = 12) -> list[tuple[str, float]]:
        if not enabled:
            return []
        try:
            if not embeddings.embedding_status()["available"]:
                _dense_degraded.set(True)
                return []
            return original(query_text, limit=limit)
        except Exception:
            _dense_degraded.set(True)
            return []

    embeddings.dense_lookup = guarded


@router.post("/search")
def search_cases(body: SearchBody) -> dict:
    from draftly.case_retrieval.models import CaseQuery
    from draftly.case_retrieval.search import find_similar

    token = _dense_degraded.set(False)
    try:
        cat = catalogue()
        result = find_similar(CaseQuery(text=body.query, limit=body.limit))
        projected = cat.project_search([hit.to_dict(include_text=False) for hit in result.hits])
        enabled = os.getenv("DRAFTLY_CASE_DENSE_ENABLED") == "1" and bool(
            os.getenv("DRAFTLY_CASE_DENSE_APPROVAL")
        )
        projected["denseStatus"] = (
            "unavailable"
            if _dense_degraded.get()
            else "enabled-status-unknown"
            if enabled
            else "disabled"
        )
        projected["degradedChannels"] = ["dense"] if _dense_degraded.get() else []
        return projected
    except Exception:
        raise HTTPException(503, "Case retrieval unavailable.") from None
    finally:
        _dense_degraded.reset(token)
