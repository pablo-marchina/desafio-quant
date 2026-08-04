from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.extraction.schemas import SourceType
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    get_project_decision_inventory,
)

SOURCE_QUALITY_WEIGHTS_DECISION_ID = "weight.source_quality_score.weights"


class ScoreStatus(str, Enum):
    CALIBRATED = "calibrated"
    BLOCKED_UNCALIBRATED_WEIGHTS = "blocked_uncalibrated_weights"


class SourceQualityFeatures(BaseModel):
    source_category: str
    source_authority_prior: float = Field(ge=0.0, le=1.0)
    robots_allowed: bool
    compliance_status: str
    fetch_success: bool
    extraction_success: bool
    duplicate_status: str
    content_bytes: int
    latency_ms: float
    source_freshness_days: float | None = None
    source_independence_type: str


class SourceQualityScoreResult(BaseModel):
    score: float
    score_status: ScoreStatus
    production_allowed: bool
    features: SourceQualityFeatures
    calibration_decision_id: str = SOURCE_QUALITY_WEIGHTS_DECISION_ID
    blockers: list[str] = Field(default_factory=list)


_AUTHORITY = {
    "official_site": 1.0,
    "official_website": 1.0,
    "news": 0.8,
    "blog": 0.6,
    "founder_profile": 0.55,
    "jobs": 0.5,
    "job_post": 0.5,
    "directory": 0.4,
}


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def extract_source_quality_features(item: Any, *, now: datetime | None = None) -> SourceQualityFeatures:
    now = now or datetime.now(UTC)
    raw_type = str(_get(item, "source_type", "directory"))
    if "." in raw_type:
        raw_type = raw_type.split(".")[-1]
    raw_type = raw_type.lower()
    source_category = raw_type if raw_type in _AUTHORITY else "directory"
    authority = _AUTHORITY.get(source_category, 0.4)
    collected_at = _parse_dt(_get(item, "collected_at"))
    freshness = None
    if collected_at is not None:
        freshness = max(0.0, (now - collected_at).total_seconds() / 86400.0)
    status = str(_get(item, "status", "fetched")).lower()
    http_status = _get(item, "http_status_code", 200)
    extraction_status = str(_get(item, "extraction_status", "success")).lower()
    return SourceQualityFeatures(
        source_category=source_category,
        source_authority_prior=float(authority),
        robots_allowed=bool(_get(item, "robots_allowed", True)),
        compliance_status=str(_get(item, "compliance_status", "compliant")),
        fetch_success=(status in {"fetched", "success", "ok"} and int(http_status or 0) < 400),
        extraction_success=extraction_status in {"success", "ok", "extracted"},
        duplicate_status="duplicate" if bool(_get(item, "duplicate", False)) else "unique",
        content_bytes=int(_get(item, "content_bytes", len(str(_get(item, "text", "")))) or 0),
        latency_ms=float(_get(item, "latency_ms", 0.0) or 0.0),
        source_freshness_days=freshness,
        source_independence_type="self_reported" if source_category in {"official_site", "official_website"} else "third_party",
    )


def _feature_value(name: str, f: SourceQualityFeatures) -> float:
    if name == "source_authority_prior":
        return f.source_authority_prior
    if name == "robots_allowed":
        return 1.0 if f.robots_allowed else 0.0
    if name == "compliance_status":
        return 1.0 if f.compliance_status == "compliant" else 0.0
    if name == "fetch_success":
        return 1.0 if f.fetch_success else 0.0
    if name == "extraction_success":
        return 1.0 if f.extraction_success else 0.0
    if name == "duplicate_status":
        return 0.0 if f.duplicate_status == "duplicate" else 1.0
    if name == "content_bytes":
        return min(1.0, max(0.0, f.content_bytes / 5000.0))
    if name == "latency_ms":
        return max(0.0, 1.0 - min(f.latency_ms, 30000.0) / 30000.0)
    if name == "source_freshness_days":
        if f.source_freshness_days is None:
            return 0.5
        return max(0.0, 1.0 - min(f.source_freshness_days, 365.0) / 365.0)
    if name == "source_independence_type":
        return 0.85 if f.source_independence_type == "third_party" else 0.65
    return 0.0


def _find_decision(inventory: list[DecisionCalibrationRecord], decision_id: str) -> DecisionCalibrationRecord | None:
    return next((r for r in inventory if r.decision_id == decision_id), None)


def compute_source_quality_score(
    item: Any,
    *,
    inventory: list[DecisionCalibrationRecord] | None = None,
    now: datetime | None = None,
) -> SourceQualityScoreResult:
    features = extract_source_quality_features(item, now=now)
    inventory = get_project_decision_inventory() if inventory is None else inventory
    rec = _find_decision(inventory, SOURCE_QUALITY_WEIGHTS_DECISION_ID)
    if rec is None or not rec.production_allowed or rec.calibration_status not in {CalibrationStatus.CALIBRATED, CalibrationStatus.BASELINE_MEASURED}:
        reason = f"{SOURCE_QUALITY_WEIGHTS_DECISION_ID} missing or not calibrated for production"
        return SourceQualityScoreResult(score=0.0, score_status=ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS, production_allowed=False, features=features, blockers=[reason])
    weights = rec.current_value if isinstance(rec.current_value, dict) else {}
    if not weights:
        return SourceQualityScoreResult(score=0.0, score_status=ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS, production_allowed=False, features=features, blockers=[f"{SOURCE_QUALITY_WEIGHTS_DECISION_ID} has no weights"])
    total_w = sum(float(v) for v in weights.values()) or 1.0
    score = sum(_feature_value(k, features) * float(w) for k, w in weights.items()) / total_w
    return SourceQualityScoreResult(score=max(0.0, min(1.0, score)), score_status=ScoreStatus.CALIBRATED, production_allowed=True, features=features)

