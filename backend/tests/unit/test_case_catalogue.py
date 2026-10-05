"""Synthetic records exercise fidelity and publication boundaries."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


def wrapper():
    path = Path(__file__).parents[3] / "deploy/retrieval/case_catalogue.py"
    spec = importlib.util.spec_from_file_location("case_catalogue", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(tmp_path):
    module = wrapper()
    inputs = {}
    for collection in ("LKCA", "LKSC"):
        records = [
            {
                "case_id": f"{collection}-2000-{i}",
                "case_name": f"Synthetic case {i}",
                "neutral_citation": f"[2000] {collection} {i}",
                "deciding_court": "Supreme Court",
                "decision_date": "2000-01-02",
                "reported_year": 2000,
                "file": f"2000/{i}.html",
                "text": "Original\r\nsynthetic judgment — unchanged",
                "has_encoding_errors": True,
            }
            for i in range(1, 4)
        ]
        inputs[collection] = tmp_path / f"{collection}.jsonl"
        inputs[collection].write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    db = tmp_path / "cases.sqlite"
    module.build_catalogue(inputs, db)
    return module, db


def test_import_fidelity_and_metadata_policy(corpus):
    module, db = corpus
    with sqlite3.connect(db) as conn:
        original = json.loads(conn.execute("SELECT raw_json FROM cases LIMIT 1").fetchone()[0])
        assert original["text"] == "Original\r\nsynthetic judgment — unchanged"
    catalogue = module.CaseCatalogue(db)
    result = catalogue.detail("commonlii-LKCA-2000-1")
    assert result["item"]["collection"] == "LKCA"
    assert result["item"]["decidingCourt"] == "Supreme Court"
    assert result["item"]["text"] is None
    assert result["item"]["verificationState"] == "parsed-unverified"
    assert "encoding-errors" in result["item"]["qualityWarnings"]
    assert result["coverage"]["catalogueRecords"] == 6


def test_keyset_page_and_metadata_query(corpus):
    module, db = corpus
    catalogue = module.CaseCatalogue(db)
    first = catalogue.list(limit=2, collection="LKCA")
    second = catalogue.list(
        limit=2, collection="LKCA", after_id=first["items"][-1]["id"], after_year=2000
    )
    assert first["hasMore"] is True
    assert second["hasMore"] is False
    assert len({r["id"] for r in first["items"] + second["items"]}) == 3
    assert catalogue.list(query="judgment")["items"] == []  # no text search in browse


def test_display_requires_exact_audience_checksum_and_reference(corpus):
    module, db = corpus
    catalogue = module.CaseCatalogue(db)
    record = catalogue.detail("commonlii-LKCA-2000-1")["item"]
    approval = {
        "audience": "authenticated-library",
        "approvalReference": "synthetic-review-1",
        "userIds": ["synthetic-user"],
        "records": {record["id"]: record["textSha256"]},
    }
    catalogue = module.CaseCatalogue(db, approval=approval)
    assert catalogue.detail(record["id"], actor_id="synthetic-user")["item"]["text"] is not None
    assert catalogue.detail("commonlii-LKCA-2000-2")["item"]["text"] is None
    approval["audience"] = "internal-research"
    assert module.CaseCatalogue(db, approval=approval).detail(record["id"])["item"]["text"] is None


def test_unknown_case_is_distinct_from_unavailable(corpus, tmp_path):
    module, db = corpus
    assert module.CaseCatalogue(db).detail("missing") is None
    with pytest.raises(module.CatalogueUnavailableError):
        module.CaseCatalogue(tmp_path / "missing.sqlite").list()


def test_dense_only_results_never_publish(corpus):
    module, db = corpus
    catalogue = module.CaseCatalogue(db)
    hits = [{"case_id": "commonlii-LKCA-2000-1", "matched_signals": ["dense"], "score": 0.9}]
    assert catalogue.project_search(hits)["outcome"] == "no_similar_cases"
    hits[0]["matched_signals"] = ["lexical", "dense"]
    result = catalogue.project_search(hits)
    assert result["outcome"] == "similar_cases_found"
    assert result["items"][0]["case"]["text"] is None


def test_malformed_approval_actor_allowlist_fails_closed(corpus):
    module, db = corpus
    with pytest.raises(module.CatalogueUnavailableError):
        module.CaseCatalogue(
            db,
            approval={
                "audience": "authenticated-library",
                "approvalReference": "synthetic-review",
                "userIds": "synthetic-user",
                "records": {},
            },
        )


def test_reader_checksum_mismatch_and_unknown_actor_never_get_text(corpus):
    module, db = corpus
    record = module.CaseCatalogue(db).detail("commonlii-LKCA-2000-1")["item"]
    approval = {
        "audience": "authenticated-library",
        "approvalReference": "synthetic-review",
        "userIds": ["synthetic-user"],
        "records": {record["id"]: "a" * 64},
    }
    assert (
        module.CaseCatalogue(db, approval=approval).detail(record["id"], actor_id="synthetic-user")[
            "item"
        ]["text"]
        is None
    )
    approval["records"][record["id"]] = record["textSha256"]
    assert (
        module.CaseCatalogue(db, approval=approval).detail(record["id"], actor_id="other-user")[
            "item"
        ]["text"]
        is None
    )
