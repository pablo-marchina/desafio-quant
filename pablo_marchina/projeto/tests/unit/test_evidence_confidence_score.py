"""Tests for src.scoring.evidence_confidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
    get_project_decision_inventory,
)
from src.scoring.evidence_confidence import (
    EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID,
    EvidenceConfidenceFeatures,
    ScoreStatus,
    compute_evidence_confidence_score,
    extract_evidence_confidence_features,
)

_NOW = datetime(2026, 6, 17, tzinfo=UTC)


def _make_evidence_item(
    **overrides: Any,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "source_type": "news",
        "source_quality_score": 0.8,
        "confidence": "high",
        "evidence_kind": "fact",
        "snippet": "The company raised $10M in Series A funding for its AI platform.",
        "is_critical": False,
        "duplicate": False,
        "collected_at": "2026-06-15T00:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# 1. Features are extracted correctly
# ---------------------------------------------------------------------------


class TestExtractEvidenceConfidenceFeatures:
    def test_full_features_from_news_fact(self) -> None:
        item = _make_evidence_item()
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.source_quality_score == 0.8
        assert feats.extraction_confidence == 1.0
        assert feats.snippet_length > 0
        assert feats.text_specificity_score > 0.0
        assert feats.claim_support_count == 0
        assert feats.supporting_source_count == 0
        assert feats.cross_source_agreement_count == 0
        assert feats.contradiction_count == 0
        assert feats.factuality_status == "fact"
        assert feats.duplicate_penalty == 0.0
        assert feats.unsupported_critical_claim_flag is False

    def test_recency_days_computed(self) -> None:
        item = _make_evidence_item(collected_at="2026-06-15T00:00:00+00:00")
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.evidence_recency_days is not None
        assert feats.evidence_recency_days == pytest.approx(2.0, abs=0.01)

    def test_no_collected_at(self) -> None:
        item = _make_evidence_item(collected_at=None)
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.evidence_recency_days is None

    def test_duplicate_penalty_applied(self) -> None:
        item = _make_evidence_item(duplicate=True)
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.duplicate_penalty == 0.3

    def test_unsupported_critical_claim_flag(self) -> None:
        item = _make_evidence_item(
            is_critical=True,
            evidence_kind="unverified",
        )
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.unsupported_critical_claim_flag is True

    def test_low_confidence_maps_to_float(self) -> None:
        item = _make_evidence_item(confidence="low")
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.extraction_confidence == 0.3

    def test_medium_confidence_maps_to_float(self) -> None:
        item = _make_evidence_item(confidence="medium")
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.extraction_confidence == 0.6

    def test_short_snippet_low_specificity(self) -> None:
        item = _make_evidence_item(snippet="Uses AI.")
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.snippet_length == 8
        assert feats.text_specificity_score < 0.5

    def test_long_detailed_snippet_high_specificity(self) -> None:
        item = _make_evidence_item(
            snippet=(
                "StartupX raised $10M in Series A funding from NVIDIA and Monashees "
                "to build AI-powered analytics for healthcare providers in Brazil. "
                "The platform processes 1M+ records daily using custom ML models."
            ),
        )
        feats = extract_evidence_confidence_features(item, now=_NOW)

        assert feats.snippet_length > 100
        assert feats.text_specificity_score > 0.5


# ---------------------------------------------------------------------------
# 2. Score blocked when weights are uncalibrated (default registry)
# ---------------------------------------------------------------------------


class TestComputeEvidenceConfidenceScoreBlocked:
    def test_blocked_when_weights_uncalibrated(self) -> None:
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, now=_NOW)

        assert result.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS
        assert result.production_allowed is False
        assert len(result.blockers) >= 1

    def test_blocked_result_has_zero_score(self) -> None:
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, now=_NOW)

        assert result.score == 0.0

    def test_blocked_result_has_features(self) -> None:
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, now=_NOW)

        assert isinstance(result.features, EvidenceConfidenceFeatures)
        assert result.features.source_quality_score == 0.8

    def test_blocked_has_calibration_decision_id(self) -> None:
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, now=_NOW)

        assert result.calibration_decision_id == EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID


# ---------------------------------------------------------------------------
# 3. Score numeric when calibration allows production
# ---------------------------------------------------------------------------


class TestComputeEvidenceConfidenceScoreCalibrated:
    _CALIBRATED_WEIGHTS: dict[str, float] = {
        "source_quality_score": 0.15,
        "extraction_confidence": 0.15,
        "snippet_length": 0.05,
        "text_specificity_score": 0.10,
        "claim_support_count": 0.10,
        "supporting_source_count": 0.10,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.05,
        "factuality_status": 0.10,
        "duplicate_penalty": 0.05,
        "unsupported_critical_claim_flag": 0.05,
    }

    def _make_calibrated_inventory(self) -> list[DecisionCalibrationRecord]:
        return [
            DecisionCalibrationRecord(
                decision_id=EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID,
                decision_name="Evidence Confidence Score Weights",
                decision_type=DecisionType.WEIGHT,
                current_value=self._CALIBRATED_WEIGHTS,
                metric_name="evidence_confidence_score_weights",
                value_origin="test",
                calibration_status=CalibrationStatus.CALIBRATED,
                production_allowed=True,
                owner="test",
            ),
        ]

    def test_score_between_0_and_1(self) -> None:
        inventory = self._make_calibrated_inventory()
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, inventory=inventory, now=_NOW)

        assert 0.0 <= result.score <= 1.0
        assert result.score_status == ScoreStatus.CALIBRATED

    def test_score_higher_for_good_evidence(self) -> None:
        inventory = self._make_calibrated_inventory()
        good = _make_evidence_item(
            source_quality_score=1.0,
            confidence="high",
            evidence_kind="fact",
            snippet="NVIDIA invested $50M in Series B for GPU-powered ML platform.",
            duplicate=False,
        )
        bad = _make_evidence_item(
            source_quality_score=0.3,
            confidence="low",
            evidence_kind="unverified",
            snippet="",
            duplicate=True,
        )
        good_result = compute_evidence_confidence_score(good, inventory=inventory, now=_NOW)
        bad_result = compute_evidence_confidence_score(bad, inventory=inventory, now=_NOW)

        assert good_result.score > bad_result.score

    def test_production_allowed_when_calibrated(self) -> None:
        inventory = self._make_calibrated_inventory()
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, inventory=inventory, now=_NOW)

        assert result.production_allowed is True

    def test_unsupported_critical_lowers_score(self) -> None:
        inventory = self._make_calibrated_inventory()
        supported = _make_evidence_item(is_critical=False, evidence_kind="fact")
        unsupported = _make_evidence_item(is_critical=True, evidence_kind="unverified")
        supported_result = compute_evidence_confidence_score(supported, inventory=inventory, now=_NOW)
        unsupported_result = compute_evidence_confidence_score(unsupported, inventory=inventory, now=_NOW)

        assert supported_result.score > unsupported_result.score

    def test_weights_sum_to_one(self) -> None:
        total = sum(self._CALIBRATED_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# 4. Missing calibration generates explicit blocker
# ---------------------------------------------------------------------------


class TestMissingCalibration:
    def test_decision_not_in_inventory_gives_blocker(self) -> None:
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, inventory=[], now=_NOW)

        assert result.production_allowed is False
        assert len(result.blockers) >= 1
        assert EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID in " ".join(result.blockers)

    def test_uncalibrated_decision_gives_blocker(self) -> None:
        inventory = [
            DecisionCalibrationRecord(
                decision_id=EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID,
                decision_name="Test Uncalibrated",
                decision_type=DecisionType.WEIGHT,
                current_value={"source_quality_score": 0.5},
                calibration_status=CalibrationStatus.UNCALIBRATED,
                production_allowed=False,
            )
        ]
        item = _make_evidence_item()
        result = compute_evidence_confidence_score(item, inventory=inventory, now=_NOW)

        assert result.production_allowed is False
        assert result.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS


# ---------------------------------------------------------------------------
# 5. Registry decisions are required
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_registry_contains_ec_decision(self) -> None:
        inventory = get_project_decision_inventory()
        ids = {r.decision_id for r in inventory}
        assert EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID in ids

    def test_registry_ec_decision_is_uncalibrated(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID:
                assert rec.calibration_status == CalibrationStatus.UNCALIBRATED
                assert rec.production_allowed is False
                return
        pytest.fail(f"{EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID} not found in registry")

    def test_no_llm_qdrant_internet_scraping(self) -> None:
        import sys

        before = set(sys.modules.keys())
        extract_evidence_confidence_features(_make_evidence_item(), now=_NOW)
        after = set(sys.modules.keys())
        new_imports = after - before
        banned = {
            "langchain",
            "qdrant_client",
            "httpx",
            "aiohttp",
            "requests",
            "openai",
            "anthropic",
        }
        triggered = {m for m in new_imports if any(b in m for b in banned)}
        assert not triggered, f"Banned imports detected: {triggered}"
