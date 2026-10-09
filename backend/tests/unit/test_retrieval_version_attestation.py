"""Platform-owned frozen engine handoff, using synthetic import/index seams."""

import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path
from types import ModuleType

import httpx
from fastapi import APIRouter, FastAPI

from src.modules.research.domain.models import Scope, ScopeType
from src.modules.research.infrastructure.retrieval.http_adapter import HttpStatuteRetrievalAdapter


async def test_frozen_producer_and_consumer_share_actual_index_identity(monkeypatch, tmp_path):
    for name in [
        "draftly",
        "draftly.retrieval",
        "draftly.case_retrieval",
        "draftly.retrieval.index",
        "draftly.case_retrieval.index",
        "draftly.retrieval.api",
        "case_api",
    ]:
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    statute = sys.modules["draftly.retrieval.index"]
    statute.INDEX_DIR = tmp_path / "statutes"
    recorded = {"statutes": "synthetic frozen index A", "cases": "synthetic cases"}
    (tmp_path / "frozen-fingerprints.json").write_text(json.dumps(recorded), encoding="utf-8")
    app = FastAPI()

    @app.get("/search")
    def search():
        return [
            {
                "section_id": "SYN:s1",
                "source_id": "SYN",
                "excerpt": "  Synthetic saved exact excerpt\n",
            }
        ]

    @app.get("/health")
    def health():
        return {"ok": True}

    sys.modules["draftly.retrieval.api"].app = app
    sys.modules["case_api"].router = APIRouter()
    sys.modules["case_api"].install_dense_gate = lambda: None
    deployment = Path(__file__).parents[3] / "deploy/retrieval"
    # Docker installs both modules beside one another under /app. Load the real
    # sibling here without leaving its module or deployment paths in other tests.
    spec = importlib.util.spec_from_file_location("legal_release", deployment / "legal_release.py")
    assert spec is not None and spec.loader is not None
    legal_release = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "legal_release", legal_release)
    spec.loader.exec_module(legal_release)
    for name in ("TRUST", "REQUIRED", "ACTIVE"):
        monkeypatch.setattr(legal_release, name, tmp_path / name)
    runpy.run_path(str(deployment / "serve_frozen.py"))
    expected = "statutes-index-v1:" + hashlib.sha256(recorded["statutes"].encode()).hexdigest()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://synthetic.invalid"
    ) as client:
        response = await client.get("/search", params={"q": "synthetic"})
        assert response.headers["X-Draftly-Corpus-Version"] == expected
        assert "X-Draftly-Corpus-Version" not in (await client.get("/health")).headers
        metadata = await client.get("/v1/legal-authorities", params={"release_version": expected})
        assert metadata.json() == {
            "corpusVersion": expected,
            "sourceReleaseVersion": None,
            "authorities": [],
            "coverageGaps": ["authority-metadata-unsupported"],
        }
        mismatch = await client.get(
            "/v1/legal-authorities", params={"release_version": "wrong-caller-version"}
        )
        assert mismatch.status_code == 409
    adapter = HttpStatuteRetrievalAdapter(
        base_url="http://synthetic.invalid", transport=httpx.ASGITransport(app)
    )
    result = await adapter.search("synthetic", Scope(ScopeType.LIBRARY), "wrong-caller-version")
    assert result.passages[0].corpus_version == expected
    assert result.passages[0].text == "  Synthetic saved exact excerpt\n"
    assert statute.corpus_fingerprint([]) == recorded["statutes"]
