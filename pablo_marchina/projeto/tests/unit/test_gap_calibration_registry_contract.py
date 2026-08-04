from __future__ import annotations

import math

from src.diagnosis.gap_diagnosis_scoring import REQUIRED_CALIBRATION_DECISIONS
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    get_project_decision_inventory,
    validate_decision_for_production,
)


def test_gap_diagnosis_registry_contains_every_required_decision() -> None:
    inventory = {record.decision_id: record for record in get_project_decision_inventory()}

    assert set(REQUIRED_CALIBRATION_DECISIONS).issubset(inventory)
    for decision_id in REQUIRED_CALIBRATION_DECISIONS:
        record = inventory[decision_id]
        assert record.calibration_status == CalibrationStatus.BASELINE_MEASURED
        assert record.production_allowed is True
        assert record.evidence_source
        assert "synthetic" in (record.notes or "").casefold()
        assert validate_decision_for_production(record).passed is True


def test_gap_diagnosis_weight_groups_are_normalized() -> None:
    inventory = {record.decision_id: record for record in get_project_decision_inventory()}
    severity = inventory["gap_diagnosis.severity_weights"].current_value
    confidence = inventory["gap_diagnosis.confidence_weights"].current_value

    assert isinstance(severity, dict)
    assert isinstance(confidence, dict)
    assert math.isclose(sum(severity.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(confidence.values()), 1.0, abs_tol=1e-9)
    assert inventory["gap_diagnosis.production_threshold"].current_value == 0.3197
    assert inventory["gap_diagnosis.minimum_evidence_coverage"].current_value == 0.20
