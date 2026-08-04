from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.claim import ClaimRepository
from src.repositories.product import ProductRepository


@pytest.fixture
def repo(tmp_path: Path) -> ClaimRepository:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'claims.db').as_posix()}")
    session = runtime.session_factory()
    yield ClaimRepository(session)
    session.close()
    reset_product_database_runtime()


def _setup_run(tmp_path: Path) -> tuple[ClaimRepository, str, str]:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'claims_setup.db').as_posix()}")
    session = runtime.session_factory()
    product_repo = ProductRepository(session)
    claim_repo = ClaimRepository(session)

    startup = product_repo.create_startup(
        name="Claim Test",
        website="https://claimtest.example.com",
        country="Brazil",
        sector="AI",
        description="",
        product_summary="",
    )
    product_repo.add_evidence(
        startup_id=startup.id,
        claim="Runs AI workloads",
        source_url="https://claimtest.example.com/tech",
        source_type="official_site",
        quote_or_evidence="Runs AI in production",
        confidence="high",
        collected_at=datetime.now(UTC),
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    session.commit()
    reset_product_database_runtime()
    return claim_repo, startup.id, run.id


def test_create_claim(repo: ClaimRepository) -> None:
    claim = repo.create_claim(
        startup_id="s1",
        analysis_run_id="r1",
        claim_text="This startup uses AI in production",
        claim_type="ai_native_claim",
        support_level="strong",
        confidence="high",
        evidence_refs=[{"evidence_id": "e1", "source_url": "https://example.com", "claim": "AI used"}],
        used_in_score=True,
    )
    assert claim.id is not None
    assert claim.claim_text == "This startup uses AI in production"
    assert claim.claim_type == "ai_native_claim"
    assert claim.support_level == "strong"
    assert claim.used_in_score is True
    assert claim.used_in_gap is False


def test_create_claims_bulk_and_list(repo: ClaimRepository) -> None:
    claims_data = [
        {
            "startup_id": "s1",
            "analysis_run_id": "r1",
            "claim_text": "Claim A",
            "claim_type": "ai_native_claim",
            "support_level": "strong",
            "confidence": "high",
            "evidence_refs": [],
        },
        {
            "startup_id": "s1",
            "analysis_run_id": "r1",
            "claim_text": "Claim B",
            "claim_type": "gap_claim",
            "support_level": "unsupported",
            "confidence": "low",
            "evidence_refs": [],
        },
        {
            "startup_id": "s1",
            "analysis_run_id": "r1",
            "claim_text": "Claim C",
            "claim_type": "uncertainty_claim",
            "support_level": "weak",
            "confidence": "medium",
            "evidence_refs": [{"evidence_id": "e2"}],
        },
    ]
    records = repo.create_claims_bulk(claims_data)
    assert len(records) == 3

    all_claims = repo.list_claims_for_analysis_run("r1")
    assert len(all_claims) == 3

    gap_claims = repo.list_claims_for_analysis_run("r1", claim_type="gap_claim")
    assert len(gap_claims) == 1

    unsupported = repo.list_claims_for_analysis_run("r1", support_level="unsupported")
    assert len(unsupported) == 1

    startup_claims = repo.list_claims_for_startup("s1")
    assert len(startup_claims) == 3


def test_update_claim_review_status(repo: ClaimRepository) -> None:
    claim = repo.create_claim(
        startup_id="s1",
        analysis_run_id="r1",
        claim_text="Review test claim",
        claim_type="gap_claim",
        support_level="unsupported",
        confidence="low",
    )
    updated = repo.update_claim_review_status(
        claim.id,
        review_status="needs_more_evidence",
        reviewer_notes="Please add evidence for this gap",
    )
    assert updated is not None
    assert updated.review_status == "needs_more_evidence"
    assert updated.reviewer_notes == "Please add evidence for this gap"


def test_update_nonexistent_claim_returns_none(repo: ClaimRepository) -> None:
    result = repo.update_claim_review_status("nonexistent", review_status="approved")
    assert result is None


def test_count_claims_by_support_level(repo: ClaimRepository) -> None:
    for level in ["strong", "strong", "medium", "weak", "unsupported"]:
        repo.create_claim(
            startup_id="s1",
            analysis_run_id="r1",
            claim_text=f"Claim {level}",
            claim_type="ai_native_claim",
            support_level=level,
            confidence="high" if level == "strong" else "medium",
        )

    counts = repo.count_claims_by_support_level("r1")
    assert counts.get("strong") == 2
    assert counts.get("medium") == 1
    assert counts.get("weak") == 1
    assert counts.get("unsupported") == 1


def test_get_evidence_coverage_summary_empty_run(repo: ClaimRepository) -> None:
    cov = repo.get_evidence_coverage_summary("empty_run")
    assert cov["total_claims"] == 0
    assert cov["evidence_coverage"] == 0.0


def test_get_evidence_coverage_summary(repo: ClaimRepository) -> None:
    for i, (level, ctype) in enumerate(
        [
            ("strong", "ai_native_claim"),
            ("unsupported", "gap_claim"),
            ("weak", "defensibility_claim"),
            ("medium", "nvidia_fit_claim"),
            ("strong", "production_readiness_claim"),
        ]
    ):
        repo.create_claim(
            startup_id="s1",
            analysis_run_id="r1",
            claim_text=f"Claim {i}",
            claim_type=ctype,
            support_level=level,
            confidence="high" if level == "strong" else ("medium" if level == "medium" else "low"),
        )

    cov = repo.get_evidence_coverage_summary("r1")
    assert cov["total_claims"] == 5
    assert cov["supported_claims"] == 3
    assert cov["unsupported_claims"] == 1
    assert cov["weak_claims"] == 1
    assert cov["critical_claims"] == 4
    assert cov["critical_supported_claims"] == 2
    assert cov["evidence_coverage"] == 0.6


def test_list_unsupported_critical_claims(repo: ClaimRepository) -> None:
    repo.create_claim(
        startup_id="s1",
        analysis_run_id="r1",
        claim_text="Unsupported gap",
        claim_type="gap_claim",
        support_level="unsupported",
        confidence="low",
    )
    repo.create_claim(
        startup_id="s1",
        analysis_run_id="r1",
        claim_text="Supported gap",
        claim_type="gap_claim",
        support_level="strong",
        confidence="high",
        evidence_refs=[{"evidence_id": "e1"}],
    )
    repo.create_claim(
        startup_id="s1",
        analysis_run_id="r1",
        claim_text="Unsupported market",
        claim_type="market_claim",
        support_level="unsupported",
        confidence="low",
    )

    critical = repo.list_unsupported_critical_claims("r1")
    assert len(critical) == 1
    assert critical[0].claim_text == "Unsupported gap"


def test_delete_claims_for_run(repo: ClaimRepository) -> None:
    repo.create_claim(startup_id="s1", analysis_run_id="r1", claim_text="C1", claim_type="ai_native_claim")
    repo.create_claim(startup_id="s1", analysis_run_id="r1", claim_text="C2", claim_type="gap_claim")
    repo.create_claim(startup_id="s2", analysis_run_id="r2", claim_text="C3", claim_type="market_claim")

    deleted = repo.delete_claims_for_run("r1")
    assert deleted == 2

    remaining = repo.list_claims_for_analysis_run("r1")
    assert len(remaining) == 0

    other = repo.list_claims_for_analysis_run("r2")
    assert len(other) == 1
