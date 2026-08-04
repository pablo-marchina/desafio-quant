from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.claim import ClaimRepository
from src.repositories.product import ProductRepository
from src.services.product.claim_ledger import (
    ClaimLedgerService,
    _calculate_support_level,
    _confidence_to_float,
)


@pytest.fixture
def service(tmp_path: Path) -> ClaimLedgerService:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    session = runtime.session_factory()
    yield ClaimLedgerService(session)
    session.close()
    reset_product_database_runtime()


def test_confidence_to_float() -> None:
    assert _confidence_to_float("high") == 1.0
    assert _confidence_to_float("medium") == 0.6
    assert _confidence_to_float("low") == 0.3
    assert _confidence_to_float("unknown") == 0.0


def test_calculate_support_level() -> None:
    assert _calculate_support_level([{"id": "e1"}], "high") == "strong"
    assert _calculate_support_level([{"id": "e1"}], "medium") == "medium"
    assert _calculate_support_level([{"id": "e1"}], "low") == "weak"
    assert _calculate_support_level([], "high") == "unsupported"


def test_build_claims_from_existing_records_empty(service: ClaimLedgerService) -> None:
    session = service.session
    product_repo = ProductRepository(session)
    startup = product_repo.create_startup(
        name="Empty Test",
        website="https://empty.example.com",
        country="Brazil",
        sector="AI",
        description="",
        product_summary="",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    session.commit()

    claims = service.build_claims_from_existing_records(run)
    assert isinstance(claims, list)


def test_build_claims_with_evidence_and_gaps(service: ClaimLedgerService) -> None:
    session = service.session
    product_repo = ProductRepository(session)
    startup = product_repo.create_startup(
        name="Full Test",
        website="https://full.example.com",
        country="Brazil",
        sector="AI",
        description="AI company",
        product_summary="Inference platform",
    )
    ev = product_repo.add_evidence(
        startup_id=startup.id,
        claim="Runs GPU inference",
        source_url="https://full.example.com/tech",
        source_type="official_site",
        quote_or_evidence="Runs GPU inference in production",
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
    product_repo.save_score(
        analysis_run_id=run.id,
        score_type="defensibility",
        value=85.0,
        confidence="high",
        components={"evidence_used": [{"id": ev.id}], "total_score": 85.0},
        missing_evidence=["Need more customer data"],
    )
    product_repo.save_score(
        analysis_run_id=run.id,
        score_type="inception_fit",
        value=70.0,
        confidence="medium",
        components={},
        missing_evidence=[],
    )
    product_repo.save_score(
        analysis_run_id=run.id,
        score_type="production_readiness",
        value=60.0,
        confidence="medium",
        components={},
        missing_evidence=[],
    )
    product_repo.save_gap(
        analysis_run_id=run.id,
        gap_type="high_inference_cost",
        detected=True,
        confidence="medium",
        evidence_tag="inferred",
        reasoning="High GPU usage",
        evidence_refs=[{"id": ev.id, "claim": ev.claim}],
    )
    product_repo.save_mapping(
        analysis_run_id=run.id,
        gap_record_id=None,
        technology_name="NVIDIA Triton",
        addresses_gap="high_inference_cost",
        justification="Triton optimizes inference",
        recommendation_action="approach_now",
        priority="high",
    )
    session.commit()
    session.refresh(run)

    claims = service.build_claims_from_existing_records(run)
    assert len(claims) >= 4

    claim_texts = [c["claim_text"] for c in claims]
    has_evidence_claim = any("Runs GPU inference" in ct for ct in claim_texts)
    assert has_evidence_claim, "Should have claim from evidence"

    has_score_claim = any("defensibility" in ct for ct in claim_texts)
    assert has_score_claim, "Should have claim from score"

    has_gap_claim = any("high_inference_cost" in ct for ct in claim_texts)
    assert has_gap_claim, "Should have claim from gap"

    has_mapping_claim = any("NVIDIA Triton" in ct for ct in claim_texts)
    assert has_mapping_claim, "Should have claim from mapping"

    has_uncertainty = any("Missing evidence" in ct for ct in claim_texts)
    assert has_uncertainty, "Should have uncertainty claim for missing evidence"


def test_persist_claims_for_run_is_idempotent(service: ClaimLedgerService) -> None:
    session = service.session
    product_repo = ProductRepository(session)
    startup = product_repo.create_startup(
        name="Idempotent Test",
        website="https://idempotent.example.com",
        country="Brazil",
        sector="AI",
        description="",
        product_summary="",
    )
    product_repo.add_evidence(
        startup_id=startup.id,
        claim="Runs AI",
        source_url="https://idempotent.example.com/tech",
        source_type="official_site",
        quote_or_evidence="Runs AI",
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
    session.refresh(run)

    first = service.persist_claims_for_run(run)
    assert len(first) > 0

    second = service.persist_claims_for_run(run)
    assert len(second) > 0

    repo = ClaimRepository(session)
    all_after = repo.list_claims_for_analysis_run(run.id)
    assert len(all_after) == len(second), "Should be idempotent"


def test_get_evidence_coverage_for_analysis_run(service: ClaimLedgerService) -> None:
    session = service.session
    product_repo = ProductRepository(session)
    startup = product_repo.create_startup(
        name="Coverage Test",
        website="https://coverage.example.com",
        country="Brazil",
        sector="AI",
        description="",
        product_summary="",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    session.commit()

    session.refresh(startup)
    session.refresh(run)

    cov = service.get_evidence_coverage_for_analysis_run(run.id)
    assert cov["total_claims"] == 0
    assert cov["evidence_coverage"] == 0.0


def test_detect_unsupported_claims_empty_run(service: ClaimLedgerService) -> None:
    session = service.session
    product_repo = ProductRepository(session)
    startup = product_repo.create_startup(
        name="Detect Test",
        website="https://detect.example.com",
        country="Brazil",
        sector="AI",
        description="",
        product_summary="",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    session.commit()

    issues = service.detect_unsupported_claims(run.id)
    assert isinstance(issues, list)


def test_detect_unsupported_critical_claims(service: ClaimLedgerService) -> None:
    session = service.session
    claim_repo = ClaimRepository(session)

    claim_repo.create_claim(
        startup_id="s1",
        analysis_run_id="r_unsupported",
        claim_text="Unsupported gap",
        claim_type="gap_claim",
        support_level="unsupported",
        confidence="low",
    )
    session.commit()

    issues = service.detect_unsupported_claims("r_unsupported")
    codes = [i["code"] for i in issues]
    assert "UNSUPPORTED_CRITICAL_CLAIM" in codes


def test_detect_low_evidence_coverage(service: ClaimLedgerService) -> None:
    session = service.session
    claim_repo = ClaimRepository(session)

    claim_repo.create_claim(
        startup_id="s1",
        analysis_run_id="r_low_cov",
        claim_text="Supported claim",
        claim_type="ai_native_claim",
        support_level="strong",
        confidence="high",
        evidence_refs=[{"id": "e1"}],
    )
    for _ in range(4):
        claim_repo.create_claim(
            startup_id="s1",
            analysis_run_id="r_low_cov",
            claim_text="Unsupported claim",
            claim_type="uncertainty_claim",
            support_level="unsupported",
            confidence="low",
        )
    session.commit()

    issues = service.detect_unsupported_claims("r_low_cov")
    codes = [i["code"] for i in issues]
    assert "LOW_EVIDENCE_COVERAGE" in codes
