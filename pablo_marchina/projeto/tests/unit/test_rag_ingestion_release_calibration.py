from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    get_project_decision_inventory,
    validate_decision_for_production,
)

REQUIRED = {
    "rag.chunk_size",
    "rag.chunk_overlap",
    "rag.ingestion_batch_size",
    "rag.min_corpus_documents",
    "rag.min_corpus_chunks",
    "rag.corpus_staleness_policy",
    "rag.embedding_dimension_expected",
}


def test_release_ingestion_decisions_are_measured_and_allowed() -> None:
    records = {item.decision_id: item for item in get_project_decision_inventory()}
    assert REQUIRED <= records.keys()
    for decision_id in REQUIRED:
        record = records[decision_id]
        assert record.calibration_status not in {
            CalibrationStatus.UNCALIBRATED,
            CalibrationStatus.BLOCKED,
        }
        assert validate_decision_for_production(record).passed
    assert records["rag.min_corpus_documents"].current_value == 20
    assert records["rag.min_corpus_chunks"].current_value == 50
    assert records["rag.ingestion_batch_size"].current_value == 32
    assert records["rag.embedding_dimension_expected"].current_value == 1024
