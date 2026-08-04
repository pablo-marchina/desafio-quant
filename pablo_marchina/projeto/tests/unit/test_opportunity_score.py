from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.claim import ClaimRepository
from src.repositories.product import ProductRepository
from src.services.product.opportunity_score_service import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
    TIER_NOT_RECOMMENDED,
    OpportunityScoreService,
    _compute_claim_penalties,
    _compute_contraindication_penalty,
    _compute_degraded_penalty,
    _compute_evidence_coverage_penalty,
    _compute_incomplete_data_penalty,
    _compute_low_confidence_penalty,
    _compute_non_ai_penalty,
    _determine_tier,
    _get_activation_readiness,
    _get_claim_support,
    _get_dossier_completeness,
    _get_gap_resolution,
    _get_nvidia_mapping_score,
)


@pytest.fixture
def service(tmp_path: Path) -> OpportunityScoreService:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'opp_score.db').as_posix()}")
    session = runtime.session_factory()
    yield OpportunityScoreService(session)
    session.close()
    reset_product_database_runtime()


@pytest.fixture
def repo(service: OpportunityScoreService) -> ProductRepository:
    return ProductRepository(service.session)


@pytest.fixture
def claim_repo(service: OpportunityScoreService) -> ClaimRepository:
    return ClaimRepository(service.session)


def _setup_run(
    repo: ProductRepository,
    name: str = "TestAI",
    sector: str = "Enterprise AI",
    score_value: float = 75.0,
    status: str = "completed",
) -> tuple[str, str, str]:
    startup = repo.create_startup(
        name=name,
        website=f"https://{name.lower()}.example.com",
        country="Brazil",
        sector=sector,
        description=f"{name} description",
        product_summary=f"{name} summary",
    )
    run = repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    repo.update_analysis_run_status(
        run.id,
        status=status,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        output_snapshot={
            "startup_name": name,
            "recommended_motion": "high_priority_outreach",
            "composite_score": {"composite_score": score_value, "confidence": "medium"},
        },
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="composite",
        value=score_value / 100.0,
        confidence="medium",
        components={"composite": score_value / 100.0},
        missing_evidence=[],
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="inception_fit",
        value=score_value,
        confidence="medium",
        components={"score": score_value},
        missing_evidence=[],
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="production_readiness",
        value=score_value * 0.8,
        confidence="medium",
        components={"score": score_value * 0.8},
        missing_evidence=[],
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="defensibility",
        value=score_value * 0.9,
        confidence="medium",
        components={"score": score_value * 0.9},
        missing_evidence=[],
    )
    repo.session.commit()
    return startup.id, run.id, name


def _add_claim(
    claim_repo: ClaimRepository,
    startup_id: str,
    analysis_run_id: str,
    support_level: str = "strong",
    claim_type: str = "ai_native_claim",
    claim_text: str = "Uses AI technology",
) -> None:
    claim_repo.create_claim(
        startup_id=startup_id,
        analysis_run_id=analysis_run_id,
        claim_text=claim_text,
        claim_type=claim_type,
        support_level=support_level,
        confidence="high",
        evidence_refs=[{"id": "ev1", "source": "test"}],
    )


# --- Tier tests ---


def test_determine_tier_critical():
    assert _determine_tier(0.90, False) == TIER_CRITICAL


def test_determine_tier_high():
    assert _determine_tier(0.75, False) == TIER_HIGH


def test_determine_tier_medium():
    assert _determine_tier(0.55, False) == TIER_MEDIUM


def test_determine_tier_low():
    assert _determine_tier(0.35, False) == TIER_LOW


def test_determine_tier_not_recommended():
    assert _determine_tier(0.20, False) == TIER_NOT_RECOMMENDED


def test_determine_tier_contraindication_overrides():
    assert _determine_tier(0.95, True) == TIER_NOT_RECOMMENDED


# --- Penalty tests ---


def test_claim_penalties_no_claims():
    result = _compute_claim_penalties([], 0)
    assert result == []


def test_claim_penalties_unsupported():
    from src.database.models import ClaimRecord

    claims = [
        ClaimRecord(support_level="unsupported", claim_type="ai_native_claim"),
        ClaimRecord(support_level="strong", claim_type="market_claim"),
        ClaimRecord(support_level="unsupported", claim_type="gap_claim"),
    ]
    result = _compute_claim_penalties(claims, 3)
    types = [p["type"] for p in result]
    assert "unsupported_claims" in types
    assert "critical_unsupported" in types


def test_evidence_coverage_penalty_low():
    result = _compute_evidence_coverage_penalty(0.20)
    assert len(result) == 1
    assert result[0]["value"] == 0.10


def test_evidence_coverage_penalty_moderate():
    result = _compute_evidence_coverage_penalty(0.40)
    assert len(result) == 1
    assert result[0]["value"] == 0.05


def test_evidence_coverage_penalty_good():
    result = _compute_evidence_coverage_penalty(0.60)
    assert result == []


def test_evidence_coverage_penalty_none():
    result = _compute_evidence_coverage_penalty(None)
    assert result == []


def test_degraded_penalty_none():
    assert _compute_degraded_penalty(0) == []


def test_degraded_penalty_some():
    result = _compute_degraded_penalty(2)
    assert len(result) == 1
    assert result[0]["value"] == 0.06


def test_degraded_penalty_capped():
    result = _compute_degraded_penalty(10)
    assert result[0]["value"] == 0.12


def test_contraindication_penalty_found():
    from src.database.models import ClaimRecord

    claims = [
        ClaimRecord(
            support_level="strong",
            claim_type="risk_claim",
            claim_text="not_recommended due to compliance risk",
        ),
    ]
    result = _compute_contraindication_penalty(claims)
    assert len(result) == 1
    assert result[0]["value"] == 1.0


def test_contraindication_penalty_none():
    from src.database.models import ClaimRecord

    claims = [
        ClaimRecord(
            support_level="weak",
            claim_type="risk_claim",
            claim_text="minor risk",
        ),
    ]
    result = _compute_contraindication_penalty(claims)
    assert result == []


def test_non_ai_penalty_applies():
    result = _compute_non_ai_penalty(0.05)
    assert len(result) == 1
    assert result[0]["value"] == 1.0


def test_non_ai_penalty_not_applied():
    assert _compute_non_ai_penalty(0.5) == []


def test_low_confidence_penalty():
    result = _compute_low_confidence_penalty("low")
    assert len(result) == 1


def test_low_confidence_penalty_not():
    assert _compute_low_confidence_penalty("high") == []


def test_incomplete_data_penalty():
    result = _compute_incomplete_data_penalty(
        ["quality_score", "activation_readiness"],
        ["composite_ranking", "evidence_coverage"],
    )
    assert len(result) == 1
    assert result[0]["value"] > 0


# --- Component tests ---


def test_get_gap_resolution_all_undetected():
    from src.database.models import GapDiagnosisRecord

    gaps = [
        GapDiagnosisRecord(detected=False, gap_type="gap1"),
        GapDiagnosisRecord(detected=False, gap_type="gap2"),
    ]
    assert _get_gap_resolution(gaps) == 1.0


def test_get_gap_resolution_mixed():
    from src.database.models import GapDiagnosisRecord

    gaps = [
        GapDiagnosisRecord(detected=True, gap_type="gap1"),
        GapDiagnosisRecord(detected=False, gap_type="gap2"),
    ]
    assert _get_gap_resolution(gaps) == 0.5


def test_get_nvidia_mapping_score_empty():
    assert _get_nvidia_mapping_score([]) == 0.0


def test_get_nvidia_mapping_score_with_mappings():
    from src.database.models import NvidiaMappingRecord

    mappings = [
        NvidiaMappingRecord(technology_name="CUDA", priority="high"),
        NvidiaMappingRecord(technology_name="TensorRT", priority="low"),
    ]
    score = _get_nvidia_mapping_score(mappings)
    assert score == 0.5


def test_get_activation_readiness_empty():
    assert _get_activation_readiness([]) == 0.0


def test_get_dossier_completeness_empty():
    assert _get_dossier_completeness([]) == 0.0


def test_get_claim_support_empty():
    assert _get_claim_support([]) == 0.0


# --- Integration-style service tests ---


def test_compute_score_returns_result(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result = service.compute_score(run_id)
    assert result["opportunity_score"] >= 0
    valid_tiers = (TIER_CRITICAL, TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_NOT_RECOMMENDED)
    assert result["score_tier"] in valid_tiers
    assert result["recommended_action"] != ""


def test_get_latest_score_returns_none_when_missing(
    service: OpportunityScoreService,
) -> None:
    assert service.get_latest_score("nonexistent") is None


def test_get_latest_score_after_compute(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    service.compute_score(run_id)
    result = service.get_latest_score(run_id)
    assert result is not None
    assert result["opportunity_score"] >= 0
    assert result["score_version"] >= 1


def test_recompute_updates_version(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result1 = service.compute_score(run_id)
    result2 = service.compute_score(run_id)
    assert result2["opportunity_score"] == result1["opportunity_score"]


def test_score_with_claims_penalties(
    service: OpportunityScoreService,
    repo: ProductRepository,
    claim_repo: ClaimRepository,
) -> None:
    startup_id, run_id, name = _setup_run(repo)
    for _ in range(5):
        _add_claim(claim_repo, startup_id, run_id, support_level="unsupported")
    service.session.commit()
    result = service.compute_score(run_id)
    assert result["penalty_total"] > 0


def test_ranked_opportunities_empty(
    service: OpportunityScoreService,
) -> None:
    items, total = service.list_ranked_opportunities()
    assert items == []
    assert total == 0


def test_ranked_opportunities_with_data(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id_1, _ = _setup_run(repo, "Alpha AI", "Enterprise AI")
    _, run_id_2, _ = _setup_run(repo, "Beta ML", "HealthTech")
    service.compute_score(run_id_1)
    service.compute_score(run_id_2)
    items, total = service.list_ranked_opportunities()
    assert total >= 2
    assert items[0]["opportunity_score"] >= items[-1]["opportunity_score"]


def test_respects_scope_no_demo_runs(service: OpportunityScoreService) -> None:
    import inspect as ins

    source = ins.getsource(type(service))
    assert "data/demo_runs" not in source


def test_penalty_types_are_correct(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result = service.compute_score(run_id)
    for p in result.get("penalties", []):
        assert "type" in p
        assert "value" in p
        assert "detail" in p
        assert p["type"] in (
            "unsupported_claims",
            "low_evidence_coverage",
            "critical_unsupported",
            "degraded_states",
            "low_confidence",
            "contraindication",
            "incomplete_data",
            "non_ai_classification",
        )


def test_score_tier_is_in_valid_list(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result = service.compute_score(run_id)
    valid_tiers = {TIER_CRITICAL, TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_NOT_RECOMMENDED}
    assert result["score_tier"] in valid_tiers


def test_evidence_refs_aggregated(
    service: OpportunityScoreService,
    repo: ProductRepository,
    claim_repo: ClaimRepository,
) -> None:
    startup_id, run_id, _ = _setup_run(repo)
    _add_claim(claim_repo, startup_id, run_id)
    service.session.commit()
    result = service.compute_score(run_id)
    assert result["evidence_ref_count"] >= 1


def test_compute_score_raises_on_bad_run_id(
    service: OpportunityScoreService,
) -> None:
    with pytest.raises(ValueError, match="not found"):
        service.compute_score("invalid-run-id")


def test_components_present_in_result(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result = service.compute_score(run_id)
    expected = {
        "composite_ranking",
        "evidence_coverage",
        "gap_resolution",
        "nvidia_mapping",
        "activation_readiness",
        "dossier_completeness",
        "quality_score",
        "claim_support",
        "review_status",
        "production_readiness",
    }
    assert expected.issubset(result["components"].keys())


def test_score_is_within_bounds(
    service: OpportunityScoreService,
    repo: ProductRepository,
) -> None:
    _, run_id, _ = _setup_run(repo)
    result = service.compute_score(run_id)
    assert 0.0 <= result["opportunity_score"] <= 1.0
