from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository


@pytest.fixture
def repos(tmp_path: Path) -> tuple[ReviewDecisionRepository, ProductRepository]:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'review_decision.db').as_posix()}")
    session = runtime.session_factory()
    yield ReviewDecisionRepository(session), ProductRepository(session)
    session.close()
    reset_product_database_runtime()


def _create_startup_and_run(
    product_repo: ProductRepository,
) -> tuple[str, str]:
    startup = product_repo.create_startup(
        name="Review Decision Test",
        website="https://review-decision.example.com",
        country="Brazil",
        sector="AI",
        description="Test startup for review decision entity",
        product_summary="Test summary",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    product_repo.session.commit()
    return startup.id, run.id


# ---------------------------------------------------------------------------
# approve cria ReviewDecision
# ---------------------------------------------------------------------------


def test_approve_creates_review_decision(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="test-analyst",
        notes="Approved with caveats",
    )
    review_repo.session.commit()

    assert record.id is not None
    assert record.decision == "approve"
    assert record.reviewer == "test-analyst"


# ---------------------------------------------------------------------------
# reject cria ReviewDecision
# ---------------------------------------------------------------------------


def test_reject_creates_review_decision(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="reject",
        reviewer="test-analyst",
        notes="Not a fit for NVIDIA",
    )
    review_repo.session.commit()

    assert record.id is not None
    assert record.decision == "reject"


# ---------------------------------------------------------------------------
# request_more_evidence cria ReviewDecision
# ---------------------------------------------------------------------------


def test_request_more_evidence_creates_review_decision(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="request_more_evidence",
        reviewer="test-analyst",
        notes="Need more evidence on GPU usage",
    )
    review_repo.session.commit()

    assert record.id is not None
    assert record.decision == "request_more_evidence"


# ---------------------------------------------------------------------------
# ReviewDecision contém run_id, startup_id e thread_id
# ---------------------------------------------------------------------------


def test_contains_run_startup_and_thread_ids(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="test-analyst",
        notes="Looks good",
        thread_id="thread-abc-123",
    )
    review_repo.session.commit()

    assert record.analysis_run_id == run_id
    assert record.startup_id == startup_id
    assert record.thread_id == "thread-abc-123"


# ---------------------------------------------------------------------------
# ReviewDecision contém review_payload_snapshot
# ---------------------------------------------------------------------------


def test_contains_review_payload_snapshot(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    payload = {
        "run_id": run_id,
        "reason": "Evidence validation flagged issues",
        "severity": "medium",
        "expected_human_actions": ["approve", "reject", "request_more_evidence"],
        "resumable": True,
    }

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="test-analyst",
        notes="Looks good",
        review_payload_snapshot=payload,
    )
    review_repo.session.commit()

    assert record.review_payload_snapshot == payload
    assert record.review_payload_snapshot["run_id"] == run_id
    assert record.review_payload_snapshot["severity"] == "medium"


# ---------------------------------------------------------------------------
# status_before_resume e status_after_resume
# ---------------------------------------------------------------------------


def test_stores_status_before_and_after_resume(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="test-analyst",
        notes="Looks good",
        status_before_resume="awaiting_review",
    )
    review_repo.session.commit()

    assert record.status_before_resume == "awaiting_review"
    assert record.status_after_resume is None

    review_repo.update_status_after_resume(record.id, status_after_resume="completed")
    review_repo.session.commit()

    updated = review_repo.get_latest_for_run(run_id)
    assert updated is not None
    assert updated.status_after_resume == "completed"


# ---------------------------------------------------------------------------
# decisão inválida não persiste ReviewDecision (schema validation)
# ---------------------------------------------------------------------------


def test_invalid_decision_not_persisted() -> None:
    from pydantic import ValidationError

    from src.api.product_schemas import WorkflowReviewDecisionCreate

    with pytest.raises(ValidationError):
        WorkflowReviewDecisionCreate(decision="invalid_decision")


# ---------------------------------------------------------------------------
# múltiplas decisões por run — append-only
# ---------------------------------------------------------------------------


def test_multiple_decisions_per_run_append_only(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    for i, dec in enumerate(["approve", "reject", "request_more_evidence"]):
        review_repo.create(
            analysis_run_id=run_id,
            startup_id=startup_id,
            decision=dec,
            reviewer=f"user-{i}",
            notes=f"Review {i}",
        )
    review_repo.session.commit()

    all_records = review_repo.list_for_run(run_id)
    assert len(all_records) == 3


# ---------------------------------------------------------------------------
# não armazena traceback interno, segredo ou token
# ---------------------------------------------------------------------------


def test_does_not_store_secrets(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    record = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="test-analyst",
        notes="Clean review",
        metadata={"source": "api"},
    )
    review_repo.session.commit()

    json_str = str(record.metadata_json)
    for secret_word in ("token", "secret", "password", "key", "Traceback", 'File "'):
        assert secret_word not in json_str.lower(), f"Secret word found: {secret_word}"
