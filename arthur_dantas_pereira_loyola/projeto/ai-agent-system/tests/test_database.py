from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from radar.database import (
    get_all_source_documents,
    get_all_startups,
    get_run_by_id,
    get_run_evidence_claims,
    get_run_recommendations,
    get_run_source_documents,
    get_run_validation,
    get_startup_by_id,
    init_db,
    save_evidence_claim,
    save_recommendation,
    save_run,
    save_source_document,
    save_startup,
    save_validation,
    update_run_status,
)
from radar.database.connection import get_db_path


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    db_path = Path(get_db_path())
    if db_path.exists():
        db_path.unlink()
    init_db()
    yield
    if db_path.exists():
        db_path.unlink()


def test_init_db_creates_tables() -> None:
    init_db()
    from radar.database.connection import get_connection

    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
    assert "startups" in names
    assert "runs" in names
    assert "source_documents" in names
    assert "evidence_claims" in names
    assert "validations" in names
    assert "recommendations" in names


def test_save_and_get_run() -> None:
    run_id = save_run("test query")
    assert run_id > 0

    run = get_run_by_id(run_id)
    assert run is not None
    assert run["query"] == "test query"
    assert run["status"] == "pending"


def test_update_run_status() -> None:
    run_id = save_run("test")
    update_run_status(run_id, "completed")
    run = get_run_by_id(run_id)
    assert run["status"] == "completed"
    assert run["completed_at"] is not None


def test_save_and_get_startup() -> None:
    data = {
        "id": f"startup_{uuid4().hex}",
        "name": "Tech AI",
        "sector": "AI",
        "product": "Chatbot",
        "description": "AI chatbot",
        "founders": ["Alice"],
        "customers": ["Bob"],
        "funding": "$1M",
        "cited_technologies": ["LLM"],
        "ai_usage_summary": "Uses LLMs",
        "classification_label": "AI-Native",
        "classification_confidence": 0.9,
        "classification_rationale": "Core product is AI",
    }
    startup_id = save_startup(data)
    assert startup_id == data["id"]

    startup = get_startup_by_id(startup_id)
    assert startup is not None
    assert startup["name"] == "Tech AI"
    assert startup["classification_label"] == "AI-Native"


def test_save_startup_updates_existing() -> None:
    data = {
        "id": "startup_test",
        "name": "Same Name",
        "sector": "AI",
    }
    save_startup(data)
    data2 = {**data, "sector": "ML"}
    save_startup(data2)
    startups = get_all_startups()
    assert len(startups) == 1


def test_save_and_get_recommendation() -> None:
    run_id = save_run("test")
    rec_id = f"rec_{uuid4().hex}"
    save_recommendation(
        run_id,
        {
            "id": rec_id,
            "technology": "NVIDIA NIM",
            "target_gap": "Inference optimization",
            "technical_justification": "NIM speeds up LLM serving",
            "business_justification": "Reduces cost",
            "priority": "high",
            "implementation_complexity": "medium",
            "suggested_next_action": "Deploy NIM",
            "startup_evidence_ids": ["claim_1"],
            "nvidia_knowledge_ids": ["nv_1"],
        },
    )

    recs = get_run_recommendations(run_id)
    assert len(recs) == 1
    assert recs[0]["technology"] == "NVIDIA NIM"


def _save_example_source(run_id: int, src_id: str) -> None:
    now = datetime.now(UTC)
    save_source_document(
        run_id,
        {
            "id": src_id,
            "url": "https://example.com",
            "domain": "example.com",
            "source_type": "news",
            "title": "Article",
            "text": "Content here",
            "retrieved_at": now,
            "collection_method": "fixture",
        },
    )


def test_save_source_document() -> None:
    run_id = save_run("test")
    src_id = f"src_{uuid4().hex}"
    _save_example_source(run_id, src_id)
    assert get_run_by_id(run_id) is not None


def test_save_evidence_claim() -> None:
    run_id = save_run("test")
    claim_id = f"claim_{uuid4().hex}"
    src_id = f"src_{uuid4().hex}"
    _save_example_source(run_id, src_id)
    save_evidence_claim(
        run_id,
        {
            "id": claim_id,
            "source_document_id": src_id,
            "text": "Uses AI",
            "claim_type": "ai_usage",
            "confidence": 0.8,
        },
    )
    assert get_run_by_id(run_id) is not None


def test_get_source_documents_with_claim_summary() -> None:
    run_id = save_run("test")
    src_id = f"src_{uuid4().hex}"
    _save_example_source(run_id, src_id)
    save_evidence_claim(
        run_id,
        {
            "id": f"claim_{uuid4().hex}",
            "source_document_id": src_id,
            "text": "Uses AI",
            "claim_type": "ai_usage",
            "confidence": 0.8,
        },
    )

    all_sources = get_all_source_documents()
    run_sources = get_run_source_documents(run_id)
    claims = get_run_evidence_claims(run_id)

    assert all_sources[0]["id"] == src_id
    assert all_sources[0]["claim_count"] == 1
    assert all_sources[0]["average_claim_confidence"] == 0.8
    assert run_sources[0]["id"] == src_id
    assert claims[0]["source_document_id"] == src_id
    assert claims[0]["confidence"] == 0.8


def test_save_validation() -> None:
    run_id = save_run("test")
    save_validation(
        run_id,
        {
            "has_minimum_evidence": True,
            "source_quality": "strong",
            "supporting_evidence_ids": ["e1", "e2"],
            "conflicts": [],
            "caveats": ["Small sample"],
            "requires_human_review": False,
        },
    )
    validation = get_run_validation(run_id)
    assert validation is not None
    assert validation["has_minimum_evidence"] is True
    assert validation["source_quality"] == "strong"
    assert validation["supporting_evidence_ids"] == ["e1", "e2"]
    assert validation["caveats"] == ["Small sample"]
    assert validation["requires_human_review"] is False


def test_get_all_startups_returns_in_order() -> None:
    s1 = {"id": "s1", "name": "Alpha"}
    s2 = {"id": "s2", "name": "Beta"}
    save_startup(s1)
    save_startup(s2)
    startups = get_all_startups()
    names = [s["name"] for s in startups]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_run_by_id_none() -> None:
    assert get_run_by_id(999) is None


def test_get_startup_by_id_none() -> None:
    assert get_startup_by_id("nonexistent") is None

