"""Tests for src.scoring.source_quality."""

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
from src.scoring.source_quality import (
    SOURCE_QUALITY_WEIGHTS_DECISION_ID,
    ScoreStatus,
    SourceQualityFeatures,
    compute_source_quality_score,
    extract_source_quality_features,
)

_NOW = datetime(2026, 6, 17, tzinfo=UTC)


def _make_evidence_item(
    **overrides: Any,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "source_type": "news",
        "robots_allowed": True,
        "compliance_status": "compliant",
        "status": "fetched",
        "http_status_code": 200,
        "extraction_status": "success",
        "duplicate": False,
        "content_bytes": 5000,
        "latency_ms": 500.0,
        "collected_at": "2026-06-15T00:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# 1. Features are extracted correctly
# ---------------------------------------------------------------------------


class TestExtractSourceQualityFeatures:
    def test_full_features_from_news_source(self) -> None:
        item = _make_evidence_item()
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.source_category == "news"
        assert feats.source_authority_prior == 0.8
        assert feats.robots_allowed is True
        assert feats.compliance_status == "compliant"
        assert feats.fetch_success is True
        assert feats.extraction_success is True
        assert feats.duplicate_status == "unique"
        assert feats.content_bytes == 5000
        assert feats.latency_ms == 500.0
        assert feats.source_freshness_days is not None
        assert feats.source_freshness_days < 3.0
        assert feats.source_independence_type == "third_party"

    def test_features_from_official_site(self) -> None:
        item = _make_evidence_item(source_type="official_site")
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.source_category == "official_site"
        assert feats.source_authority_prior == 1.0
        assert feats.source_independence_type == "self_reported"

    def test_features_duplicate_source(self) -> None:
        item = _make_evidence_item(duplicate=True)
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.duplicate_status == "duplicate"

    def test_features_fetch_failed(self) -> None:
        item = _make_evidence_item(status="failed", http_status_code=503)
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.fetch_success is False

    def test_features_no_collected_at(self) -> None:
        item = _make_evidence_item(collected_at=None)
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.source_freshness_days is None

    def test_features_invalid_source_type_falls_back_to_directory(self) -> None:
        item = _make_evidence_item(source_type="unknown_type")
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.source_category == "directory"
        assert feats.source_authority_prior == 0.4

    def test_features_empty_content(self) -> None:
        item = _make_evidence_item(content_bytes=0)
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.content_bytes == 0

    def test_features_high_latency(self) -> None:
        item = _make_evidence_item(latency_ms=15000.0)
        feats = extract_source_quality_features(item, now=_NOW)

        assert feats.latency_ms == 15000.0


# ---------------------------------------------------------------------------
# 2. Score blocked when weights are uncalibrated (default registry)
# ---------------------------------------------------------------------------


class TestComputeSourceQualityScoreDefault:
    def test_default_registry_allows_scoring(self) -> None:
        item = _make_evidence_item()
        result = compute_source_quality_score(item, now=_NOW)

        assert result.production_allowed is True
        assert result.score_status == ScoreStatus.CALIBRATED

    def test_default_registry_score_between_0_and_1(self) -> None:
        item = _make_evidence_item()
        result = compute_source_quality_score(item, now=_NOW)

        assert 0.0 <= result.score <= 1.0

    def test_default_registry_has_features(self) -> None:
        item = _make_evidence_item()
        result = compute_source_quality_score(item, now=_NOW)

        assert isinstance(result.features, SourceQualityFeatures)
        assert result.features.source_category == "news"

    def test_default_registry_has_calibration_decision_id(self) -> None:
        item = _make_evidence_item()
        result = compute_source_quality_score(item, now=_NOW)

        assert result.calibration_decision_id == SOURCE_QUALITY_WEIGHTS_DECISION_ID


# ---------------------------------------------------------------------------
# 3. Score numeric when calibration allows production
# ---------------------------------------------------------------------------


class TestComputeSourceQualityScoreCalibrated:
    _CALIBRATED_WEIGHTS: dict[str, float] = {
        "source_authority_prior": 0.30,
        "robots_allowed": 0.10,
        "compliance_status": 0.10,
        "fetch_success": 0.15,
        "extraction_success": 0.10,
        "duplicate_status": 0.05,
        "content_bytes": 0.05,
        "latency_ms": 0.05,
        "source_freshness_days": 0.05,
        "source_independence_type": 0.05,
    }

    def _make_calibrated_inventory(self) -> list[DecisionCalibrationRecord]:
        return [
            DecisionCalibrationRecord(
                decision_id=SOURCE_QUALITY_WEIGHTS_DECISION_ID,
                decision_name="Source Quality Score Weights",
                decision_type=DecisionType.WEIGHT,
                current_value=self._CALIBRATED_WEIGHTS,
                metric_name="source_quality_score_weights",
                value_origin="test",
                calibration_status=CalibrationStatus.CALIBRATED,
                production_allowed=True,
                owner="test",
            ),
        ]

    def test_score_between_0_and_1(self) -> None:
        inventory = self._make_calibrated_inventory()
        item = _make_evidence_item()
        result = compute_source_quality_score(item, inventory=inventory, now=_NOW)

        assert 0.0 <= result.score <= 1.0
        assert result.score_status == ScoreStatus.CALIBRATED

    def test_score_is_higher_for_better_source(self) -> None:
        inventory = self._make_calibrated_inventory()
        good_item = _make_evidence_item(
            source_type="official_site",
            robots_allowed=True,
            compliance_status="compliant",
            status="fetched",
            extraction_status="success",
            content_bytes=10000,
            latency_ms=100.0,
        )
        bad_item = _make_evidence_item(
            source_type="directory",
            robots_allowed=False,
            compliance_status="non_compliant",
            status="failed",
            extraction_status="failed",
            content_bytes=100,
            latency_ms=30000.0,
            duplicate=False,
        )
        good_result = compute_source_quality_score(good_item, inventory=inventory, now=_NOW)
        bad_result = compute_source_quality_score(bad_item, inventory=inventory, now=_NOW)

        assert good_result.score > bad_result.score

    def test_duplicate_lowers_score(self) -> None:
        inventory = self._make_calibrated_inventory()
        unique = _make_evidence_item(duplicate=False)
        dup = _make_evidence_item(duplicate=True)
        unique_result = compute_source_quality_score(unique, inventory=inventory, now=_NOW)
        dup_result = compute_source_quality_score(dup, inventory=inventory, now=_NOW)

        assert unique_result.score > dup_result.score

    def test_production_allowed_when_calibrated(self) -> None:
        inventory = self._make_calibrated_inventory()
        item = _make_evidence_item()
        result = compute_source_quality_score(item, inventory=inventory, now=_NOW)

        assert result.production_allowed is True
        assert result.score_status == ScoreStatus.CALIBRATED

    def test_weights_sum_to_one(self) -> None:
        total = sum(self._CALIBRATED_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# 4. Missing calibration generates explicit blocker
# ---------------------------------------------------------------------------


class TestMissingCalibration:
    def test_decision_not_in_inventory_gives_blocker(self) -> None:
        item = _make_evidence_item()
        result = compute_source_quality_score(item, inventory=[], now=_NOW)

        assert result.production_allowed is False
        assert len(result.blockers) >= 1
        assert SOURCE_QUALITY_WEIGHTS_DECISION_ID in " ".join(result.blockers)

    def test_uncalibrated_decision_gives_blocker(self) -> None:
        inventory = [
            DecisionCalibrationRecord(
                decision_id=SOURCE_QUALITY_WEIGHTS_DECISION_ID,
                decision_name="Test Uncalibrated",
                decision_type=DecisionType.WEIGHT,
                current_value={"source_authority_prior": 0.5},
                calibration_status=CalibrationStatus.UNCALIBRATED,
                production_allowed=False,
            )
        ]
        item = _make_evidence_item()
        result = compute_source_quality_score(item, inventory=inventory, now=_NOW)

        assert result.production_allowed is False
        assert result.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS


# ---------------------------------------------------------------------------
# 5. Registry decisions are required
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_registry_contains_scoring_decisions(self) -> None:
        inventory = get_project_decision_inventory()
        ids = {r.decision_id for r in inventory}
        assert SOURCE_QUALITY_WEIGHTS_DECISION_ID in ids

    def test_registry_scoring_decisions_are_calibrated(self) -> None:
        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == SOURCE_QUALITY_WEIGHTS_DECISION_ID:
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True
                return
        pytest.fail(f"{SOURCE_QUALITY_WEIGHTS_DECISION_ID} not found in registry")

    def test_no_llm_qdrant_internet_scraping(self) -> None:
        import sys

        before = set(sys.modules.keys())
        _make_evidence_item()
        extract_source_quality_features(_make_evidence_item(), now=_NOW)
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
