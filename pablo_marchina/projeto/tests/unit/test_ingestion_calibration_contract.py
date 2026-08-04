from __future__ import annotations

from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.rag.ingestion_pipeline import REQUIRED_INGESTION_DECISIONS


def test_all_required_ingestion_decisions_have_measured_production_evidence() -> None:
    inventory = {record.decision_id: record for record in get_project_decision_inventory()}

    assert set(REQUIRED_INGESTION_DECISIONS).issubset(inventory)
    for decision_id in REQUIRED_INGESTION_DECISIONS:
        record = inventory[decision_id]
        validation = validate_decision_for_production(record)
        assert validation.passed, f"{decision_id}: {validation.reasons}"
        assert record.calibration_status in {
            CalibrationStatus.BENCHMARK_BASED,
            CalibrationStatus.BASELINE_MEASURED,
        }
        assert record.production_allowed is True
        assert record.evidence_source
        assert record.last_calibrated_at is not None


def test_ingestion_calibration_matches_live_release_baseline() -> None:
    inventory = {record.decision_id: record for record in get_project_decision_inventory()}

    assert inventory["rag.chunk_size"].current_value == "markdown_h2_heading_boundaries"
    assert inventory["rag.chunk_overlap"].current_value == 0
    assert inventory["rag.ingestion_batch_size"].current_value == 32
    assert inventory["rag.min_corpus_documents"].current_value == 20
    assert inventory["rag.min_corpus_chunks"].current_value == 50
    assert inventory["rag.embedding_dimension_expected"].current_value == 1024
    assert "hash_matched_manifest" in str(inventory["rag.corpus_staleness_policy"].current_value)
