from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    get_project_decision_inventory,
)

EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID = "weight.evidence_confidence_score.weights"


class ScoreStatus(str, Enum):
    CALIBRATED = "calibrated"
    BLOCKED_UNCALIBRATED_WEIGHTS = "blocked_uncalibrated_weights"


class EvidenceConfidenceFeatures(BaseModel):
    source_quality_score: float = Field(ge=0.0, le=1.0)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    snippet_length: int
    text_specificity_score: float = Field(ge=0.0, le=1.0)
    claim_support_count: int = 0
    supporting_source_count: int = 0
    cross_source_agreement_count: int = 0
    contradiction_count: int = 0
    factuality_status: str = "unverified"
    duplicate_penalty: float = Field(ge=0.0, le=1.0)
    unsupported_critical_claim_flag: bool
    evidence_recency_days: float | None = None


class EvidenceConfidenceScoreResult(BaseModel):
    score: float
    score_status: ScoreStatus
    production_allowed: bool
    features: EvidenceConfidenceFeatures
    calibration_decision_id: str = EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID
    blockers: list[str] = Field(default_factory=list)


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _confidence_to_float(value: Any) -> float:
    raw = str(value).lower()
    if raw.endswith(".high") or raw == "high":
        return 1.0
    if raw.endswith(".medium") or raw == "medium":
        return 0.6
    if raw.endswith(".low") or raw == "low":
        return 0.3
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.5


def _specificity(text: str) -> float:
    if not text:
        return 0.0
    tokens = text.split()
    numerics = sum(any(ch.isdigit() for ch in t) for t in tokens)
    technical = sum(t.lower().strip(".,") in {"ai", "ml", "gpu", "nvidia", "series", "funding", "model", "models", "platform", "records", "daily", "healthcare"} for t in tokens)
    return min(1.0, len(text) / 180.0 + numerics * 0.08 + technical * 0.03)


def extract_evidence_confidence_features(item: Any, *, now: datetime | None = None) -> EvidenceConfidenceFeatures:
    now = now or datetime.now(UTC)
    snippet = str(_get(item, "snippet", _get(item, "quote_or_evidence", _get(item, "text", ""))) or "")
    kind = str(_get(item, "evidence_kind", "unverified"))
    if "." in kind:
        kind = kind.split(".")[-1]
    kind = kind.lower()
    collected_at = _parse_dt(_get(item, "collected_at"))
    recency = None if collected_at is None else max(0.0, (now - collected_at).total_seconds() / 86400.0)
    duplicate = bool(_get(item, "duplicate", False))
    critical = bool(_get(item, "is_critical", False)) or str(_get(item, "criticality", "")).lower() == "critical"
    return EvidenceConfidenceFeatures(
        source_quality_score=max(0.0, min(1.0, float(_get(item, "source_quality_score", 0.5) or 0.5))),
        extraction_confidence=_confidence_to_float(_get(item, "confidence", 0.5)),
        snippet_length=len(snippet),
        text_specificity_score=_specificity(snippet),
        claim_support_count=int(_get(item, "claim_support_count", 0) or 0),
        supporting_source_count=int(_get(item, "supporting_source_count", 0) or 0),
        cross_source_agreement_count=int(_get(item, "cross_source_agreement_count", 0) or 0),
        contradiction_count=int(_get(item, "contradiction_count", 0) or 0),
        factuality_status=kind,
        duplicate_penalty=0.3 if duplicate else 0.0,
        unsupported_critical_claim_flag=bool(critical and kind in {"unverified", "unsupported", "claim"}),
        evidence_recency_days=recency,
    )


def _fv(name: str, f: EvidenceConfidenceFeatures) -> float:
    if name == "source_quality_score": return f.source_quality_score
    if name == "extraction_confidence": return f.extraction_confidence
    if name == "snippet_length": return min(1.0, f.snippet_length / 180.0)
    if name == "text_specificity_score": return f.text_specificity_score
    if name == "claim_support_count": return min(1.0, f.claim_support_count / 3.0)
    if name == "supporting_source_count": return min(1.0, f.supporting_source_count / 3.0)
    if name == "cross_source_agreement_count": return min(1.0, f.cross_source_agreement_count / 3.0)
    if name == "contradiction_count": return max(0.0, 1.0 - min(1.0, f.contradiction_count / 2.0))
    if name == "factuality_status": return 1.0 if f.factuality_status in {"fact", "supported"} else 0.2
    if name == "duplicate_penalty": return 1.0 - f.duplicate_penalty
    if name == "unsupported_critical_claim_flag": return 0.0 if f.unsupported_critical_claim_flag else 1.0
    return 0.0


def compute_evidence_confidence_score(item: Any, *, inventory: list[DecisionCalibrationRecord] | None = None, now: datetime | None = None) -> EvidenceConfidenceScoreResult:
    features = extract_evidence_confidence_features(item, now=now)
    inventory = get_project_decision_inventory() if inventory is None else inventory
    rec = next((r for r in inventory if r.decision_id == EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID), None)
    if rec is None or not rec.production_allowed or rec.calibration_status not in {CalibrationStatus.CALIBRATED, CalibrationStatus.BASELINE_MEASURED}:
        return EvidenceConfidenceScoreResult(score=0.0, score_status=ScoreStatus.BLOCKED_UNCALIBRATED_WEIGHTS, production_allowed=False, features=features, blockers=[f"{EVIDENCE_CONFIDENCE_WEIGHTS_DECISION_ID} missing or not calibrated for production"])
    weights = rec.current_value if isinstance(rec.current_value, dict) else {}
    total_w = sum(float(v) for v in weights.values()) or 1.0
    score = sum(_fv(k, features) * float(w) for k, w in weights.items()) / total_w
    return EvidenceConfidenceScoreResult(score=max(0.0, min(1.0, score)), score_status=ScoreStatus.CALIBRATED, production_allowed=True, features=features)
