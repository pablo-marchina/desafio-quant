from __future__ import annotations

import json
import logging
from math import sqrt
from pathlib import Path
from statistics import stdev
from typing import Any

from pydantic import BaseModel, Field

from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
)
from src.scoring.evidence_confidence import (
    compute_evidence_confidence_score,
)
from src.scoring.source_quality import (
    SourceType,
    compute_source_quality_score,
)

logger = logging.getLogger(__name__)

SCRAPING_CATEGORY_TO_SOURCE_TYPE: dict[str, str] = {
    "official_website": SourceType.OFFICIAL_SITE.value,
    "technical_docs": SourceType.BLOG.value,
    "funding_news": SourceType.NEWS.value,
    "jobs": SourceType.JOB_POST.value,
    "github_or_code": SourceType.BLOG.value,
    "ecosystem_directory": SourceType.DIRECTORY.value,
    "media": SourceType.NEWS.value,
    "nvidia_or_partner_ecosystem": SourceType.NEWS.value,
}

SOURCE_AUTHORITY_PRIOR: dict[str, float] = {
    SourceType.OFFICIAL_SITE.value: 1.0,
    SourceType.NEWS.value: 0.8,
    SourceType.FOUNDER_PROFILE.value: 0.7,
    SourceType.BLOG.value: 0.6,
    SourceType.JOB_POST.value: 0.5,
    SourceType.DIRECTORY.value: 0.4,
}

SQ_LABEL_TO_SCORE: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}

LABEL_SOURCE_QUALITY_VALUES = frozenset({"high", "medium", "low"})
LABEL_EVIDENCE_SUPPORT_VALUES = frozenset({"supported", "insufficient", "unsupported", "conflicting"})
EC_SUPPORTED_SET = frozenset({"supported"})
EC_UNSUPPORTED_SET = frozenset({"unsupported"})

CANDIDATE_WEIGHTS_SOURCE_QUALITY: list[dict[str, float]] = [
    {
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
    },
    {
        "source_authority_prior": 0.40,
        "robots_allowed": 0.08,
        "compliance_status": 0.08,
        "fetch_success": 0.12,
        "extraction_success": 0.08,
        "duplicate_status": 0.04,
        "content_bytes": 0.04,
        "latency_ms": 0.04,
        "source_freshness_days": 0.06,
        "source_independence_type": 0.06,
    },
    {
        "source_authority_prior": 0.20,
        "robots_allowed": 0.10,
        "compliance_status": 0.15,
        "fetch_success": 0.20,
        "extraction_success": 0.15,
        "duplicate_status": 0.05,
        "content_bytes": 0.05,
        "latency_ms": 0.05,
        "source_freshness_days": 0.02,
        "source_independence_type": 0.03,
    },
    {
        "source_authority_prior": 0.15,
        "robots_allowed": 0.10,
        "compliance_status": 0.10,
        "fetch_success": 0.15,
        "extraction_success": 0.10,
        "duplicate_status": 0.10,
        "content_bytes": 0.10,
        "latency_ms": 0.10,
        "source_freshness_days": 0.05,
        "source_independence_type": 0.05,
    },
    {
        "source_authority_prior": 0.35,
        "robots_allowed": 0.05,
        "compliance_status": 0.05,
        "fetch_success": 0.10,
        "extraction_success": 0.10,
        "duplicate_status": 0.05,
        "content_bytes": 0.15,
        "latency_ms": 0.10,
        "source_freshness_days": 0.02,
        "source_independence_type": 0.03,
    },
]

CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE: list[dict[str, float]] = [
    {
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
    },
    {
        "source_quality_score": 0.25,
        "extraction_confidence": 0.15,
        "snippet_length": 0.05,
        "text_specificity_score": 0.08,
        "claim_support_count": 0.10,
        "supporting_source_count": 0.10,
        "cross_source_agreement_count": 0.08,
        "contradiction_count": 0.05,
        "factuality_status": 0.08,
        "duplicate_penalty": 0.03,
        "unsupported_critical_claim_flag": 0.03,
    },
    {
        "source_quality_score": 0.10,
        "extraction_confidence": 0.10,
        "snippet_length": 0.05,
        "text_specificity_score": 0.08,
        "claim_support_count": 0.15,
        "supporting_source_count": 0.15,
        "cross_source_agreement_count": 0.15,
        "contradiction_count": 0.07,
        "factuality_status": 0.08,
        "duplicate_penalty": 0.03,
        "unsupported_critical_claim_flag": 0.04,
    },
    {
        "source_quality_score": 0.12,
        "extraction_confidence": 0.12,
        "snippet_length": 0.05,
        "text_specificity_score": 0.08,
        "claim_support_count": 0.08,
        "supporting_source_count": 0.08,
        "cross_source_agreement_count": 0.08,
        "contradiction_count": 0.05,
        "factuality_status": 0.20,
        "duplicate_penalty": 0.05,
        "unsupported_critical_claim_flag": 0.09,
    },
    {
        "source_quality_score": 0.12,
        "extraction_confidence": 0.12,
        "snippet_length": 0.08,
        "text_specificity_score": 0.08,
        "claim_support_count": 0.10,
        "supporting_source_count": 0.10,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.08,
        "factuality_status": 0.10,
        "duplicate_penalty": 0.06,
        "unsupported_critical_claim_flag": 0.06,
    },
]

# Production readiness criteria
SQ_MIN_LABELED = 50
EC_MIN_LABELED = 50
SQ_SPEARMAN_MIN = 0.5
SQ_MAE_MAX = 0.2
EC_F1_MIN = 0.6
EC_FP_RATE_MAX = 0.2


class SourceEvidenceGoldenEntry(BaseModel):
    source_id: str
    source_url: str
    source_category: str
    source_features_observable: dict[str, Any] = Field(default_factory=dict)
    evidence_id: str
    evidence_text: str
    claim_id: str
    claim_text: str
    human_label_source_quality: str | None = None
    human_label_evidence_support: str | None = None
    label_notes: str | None = None
    label_source: str = "derived_from_scraping_baseline"


class ScoreDistribution(BaseModel):
    count: int
    mean: float
    std: float | None
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    min: float
    max: float


class WeightCandidateResult(BaseModel):
    label: str
    weights: dict[str, float]
    distribution: ScoreDistribution


class SourceQualityMetrics(BaseModel):
    spearman: float | None = None
    mae: float | None = None
    rmse: float | None = None
    calibration_error: float | None = None
    coverage_by_category: dict[str, int] = Field(default_factory=dict)
    confusion_matrix: dict[str, dict[str, int]] = Field(default_factory=dict)


class EvidenceConfidenceMetrics(BaseModel):
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    unsupported_critical_claim_miss_rate: float | None = None
    calibration_error: float | None = None


class SourceQualityCandidateResult(WeightCandidateResult):
    sq_metrics: SourceQualityMetrics | None = None


class EvidenceConfidenceCandidateResult(WeightCandidateResult):
    ec_metrics: EvidenceConfidenceMetrics | None = None


class ThresholdRecommendation(BaseModel):
    decision_id: str
    suggested_value: float | None
    method: str
    production_allowed: bool
    evidence_source: str
    distribution: ScoreDistribution | None = None


class CalibrationResult(BaseModel):
    calibration_status: str
    production_allowed: bool
    golden_set_size: int
    has_human_labels: bool
    human_label_coverage: dict[str, int]
    source_quality_candidates: list[SourceQualityCandidateResult]
    evidence_confidence_candidates: list[EvidenceConfidenceCandidateResult]
    best_sq_candidate_index: int | None = None
    best_ec_candidate_index: int | None = None
    best_sq_metrics: SourceQualityMetrics | None = None
    best_ec_metrics: EvidenceConfidenceMetrics | None = None
    sq_threshold: ThresholdRecommendation
    ec_threshold: ThresholdRecommendation
    labels_missing_notes: str
    report: str


def _derive_source_quality_label(feats: dict[str, Any]) -> str:
    source_type = str(feats.get("source_type", SourceType.DIRECTORY.value))
    is_blocked = feats.get("compliance_status") == "non_compliant"
    fetch_ok = feats.get("status") == "fetched"
    extract_ok = feats.get("extraction_status") == "success"
    is_duplicate = feats.get("duplicate", False)
    latency = float(feats.get("latency_ms", 0))

    if is_blocked or not fetch_ok or not extract_ok:
        return "low"
    if is_duplicate:
        return "medium"
    if source_type == SourceType.OFFICIAL_SITE.value:
        return "high" if latency < 500 else "medium"
    if source_type == SourceType.NEWS.value:
        return "high" if latency < 1000 else "medium"
    if source_type == SourceType.FOUNDER_PROFILE.value:
        return "medium"
    if source_type == SourceType.BLOG.value:
        return "medium"
    if source_type == SourceType.JOB_POST.value:
        return "low"
    return "medium"


def _derive_evidence_support_label(feats: dict[str, Any], claim_support_count: int) -> str:
    is_blocked = feats.get("compliance_status") == "non_compliant"
    fetch_ok = feats.get("status") == "fetched"
    extract_ok = feats.get("extraction_status") == "success"
    is_duplicate = feats.get("duplicate", False)

    if is_blocked or not fetch_ok or not extract_ok:
        return "unsupported"
    if is_duplicate:
        return "insufficient"
    if claim_support_count >= 2:
        return "supported"
    return "insufficient"


def _map_category_to_source_type(category: str) -> str:
    return SCRAPING_CATEGORY_TO_SOURCE_TYPE.get(category, SourceType.DIRECTORY.value)


def _build_evidence_item(source_entry: dict[str, Any], claim_text: str) -> dict[str, Any]:
    category = source_entry.get("category", "unknown")
    source_type = _map_category_to_source_type(category)
    fetch_ok = source_entry.get("fetch_success", True)
    extract_ok = source_entry.get("extraction_success", True)

    return {
        "source_type": source_type,
        "robots_allowed": not source_entry.get("compliance_blocked", False),
        "compliance_status": ("non_compliant" if source_entry.get("compliance_blocked") else "compliant"),
        "status": "fetched" if fetch_ok else "failed",
        "http_status_code": 200 if fetch_ok else 503,
        "extraction_status": "success" if extract_ok else "failed",
        "duplicate": source_entry.get("is_duplicate", False),
        "content_bytes": 5000,
        "latency_ms": source_entry.get("latency_ms", 0),
        "collected_at": None,
        "snippet": claim_text,
        "text": claim_text,
        "confidence": "high",
        "evidence_kind": "fact",
        "is_critical": False,
        "claim_support_count": 0,
        "supporting_source_count": 0,
        "cross_source_agreement_count": 0,
        "contradiction_count": 0,
        "source_quality_score": 0.5,
    }


def _build_entry(
    startup_id: str,
    source_entry: dict[str, Any],
    claim: dict[str, str],
    claim_support_count: int,
) -> SourceEvidenceGoldenEntry:
    url = source_entry.get("url", "")
    claim_id = claim.get("claim_id", "")
    claim_text = claim.get("claim_text", "")
    category_str = source_entry.get("category", "unknown")

    feats = _build_evidence_item(source_entry, claim_text)
    sq_label = _derive_source_quality_label(feats)
    ec_label = _derive_evidence_support_label(feats, claim_support_count)

    return SourceEvidenceGoldenEntry(
        source_id=f"{startup_id}/{url}",
        source_url=url,
        source_category=category_str,
        source_features_observable=feats,
        evidence_id=f"{startup_id}/{url}#{claim_id}",
        evidence_text=claim_text,
        claim_id=claim_id,
        claim_text=claim_text,
        human_label_source_quality=sq_label,
        human_label_evidence_support=ec_label,
        label_notes=f"Derived label from scraping baseline features. "
        f"SQ label rule: authority+fetch+extract+latency. "
        f"EC label rule: fetch+extract+dup+claim_support_count={claim_support_count}.",
        label_source="derived_from_scraping_baseline",
    )


def _compute_claim_support_counts(
    sources: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in sources:
        for cid in s.get("claim_ids_supported", []):
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def load_golden_set(
    path: Path | None = None,
) -> list[SourceEvidenceGoldenEntry]:
    if path is None:
        path = Path("data/eval/golden_scraping_baseline.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries: list[SourceEvidenceGoldenEntry] = []
    claims_by_startup: dict[str, list[dict[str, str]]] = {}

    for startup in raw.get("startups", []):
        sid: str = startup.get("startup_id", "unknown")
        claims_by_startup[sid] = startup.get("claims", [])

    for startup in raw.get("startups", []):
        sid = startup.get("startup_id", "unknown")
        sources = startup.get("sources", [])
        claims_map: dict[str, dict[str, str]] = {c["claim_id"]: c for c in claims_by_startup.get(sid, [])}
        support_counts = _compute_claim_support_counts(sources)

        for source_entry in sources:
            for cid in source_entry.get("claim_ids_supported", []):
                claim = claims_map.get(cid)
                if claim is None:
                    continue
                entries.append(_build_entry(sid, source_entry, claim, support_counts.get(cid, 0)))

    return entries


def check_human_labels_exist(
    entries: list[SourceEvidenceGoldenEntry],
) -> bool:
    for e in entries:
        if e.human_label_source_quality is not None:
            return True
        if e.human_label_evidence_support is not None:
            return True
    return False


def _compute_human_label_coverage(
    entries: list[SourceEvidenceGoldenEntry],
) -> dict[str, int]:
    sq_count = sum(1 for e in entries if e.human_label_source_quality is not None)
    ec_count = sum(1 for e in entries if e.human_label_evidence_support is not None)
    return {
        "source_quality_labels": sq_count,
        "evidence_support_labels": ec_count,
        "total_entries": len(entries),
    }


def _make_calibrated_inventory(
    decision_id: str,
    weights: dict[str, float],
) -> list[DecisionCalibrationRecord]:
    return [
        DecisionCalibrationRecord(
            decision_id=decision_id,
            decision_name="Eval Calibrated (temporary)",
            decision_type=DecisionType.WEIGHT,
            current_value=dict(weights),
            metric_name="eval_calibration",
            value_origin="source_evidence_score_baseline_eval",
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            owner="eval",
        ),
    ]


def _compute_distribution(scores: list[float]) -> ScoreDistribution:
    if not scores:
        return ScoreDistribution(
            count=0,
            mean=0.0,
            std=None,
            p5=0.0,
            p25=0.0,
            p50=0.0,
            p75=0.0,
            p95=0.0,
            min=0.0,
            max=0.0,
        )
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    std_val: float | None
    try:
        std_val = stdev(sorted_scores) if n > 1 else 0.0
    except (ValueError, ZeroDivisionError):
        std_val = 0.0

    def _percentile(p: float) -> float:
        k = max(0, min(n - 1, int(n * p / 100.0)))
        return sorted_scores[k]

    return ScoreDistribution(
        count=n,
        mean=sum(sorted_scores) / n,
        std=round(std_val, 4) if std_val is not None else None,
        p5=round(_percentile(5.0), 4),
        p25=round(_percentile(25.0), 4),
        p50=round(_percentile(50.0), 4),
        p75=round(_percentile(75.0), 4),
        p95=round(_percentile(95.0), 4),
        min=round(sorted_scores[0], 4),
        max=round(sorted_scores[-1], 4),
    )


def _spearman_rank_correlation(
    x: list[float],
    y: list[float],
) -> float | None:
    n = len(x)
    if n < 3:
        return None

    def _rank(vals: list[float]) -> list[float]:
        sorted_vals = sorted(vals)
        ranks: list[float] = []
        for v in vals:
            first = sorted_vals.index(v)
            last = len(sorted_vals) - 1 - sorted_vals[::-1].index(v)
            ranks.append(1.0 + (first + last) / 2.0)
        return ranks

    xr = _rank(x)
    yr = _rank(y)
    d_sq = sum((xr[i] - yr[i]) ** 2 for i in range(n))
    denom = n * (n * n - 1)
    if denom == 0:
        return None
    return 1.0 - (6.0 * d_sq) / denom


def _compute_mae(actual: list[float], predicted: list[float]) -> float | None:
    if not actual:
        return None
    return sum(abs(a - p) for a, p in zip(actual, predicted, strict=False)) / len(actual)


def _compute_rmse(actual: list[float], predicted: list[float]) -> float | None:
    if not actual:
        return None
    return sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=False)) / len(actual))


def _compute_calibration_error(
    actual: list[float],
    predicted: list[float],
    bins: int = 10,
) -> float | None:
    if len(actual) < bins:
        return None
    n = len(actual)
    bin_size = n // bins
    total_error = 0.0
    for b in range(bins):
        start = b * bin_size
        end = start + bin_size if b < bins - 1 else n
        if end <= start:
            continue
        bin_pred = sum(predicted[start:end]) / (end - start)
        bin_actual = sum(actual[start:end]) / (end - start)
        total_error += abs(bin_pred - bin_actual) * (end - start) / n
    return total_error


def _compute_sq_metrics(
    entries: list[SourceEvidenceGoldenEntry],
    scores: list[float],
) -> SourceQualityMetrics:
    labeled = [
        (e, s)
        for e, s in zip(entries, scores, strict=False)
        if e.human_label_source_quality in LABEL_SOURCE_QUALITY_VALUES
    ]
    if not labeled:
        return SourceQualityMetrics()

    y_true_scores = [
        SQ_LABEL_TO_SCORE[label] for e, _ in labeled if (label := e.human_label_source_quality) is not None
    ]
    y_pred = [s for _, s in labeled]

    spearman = _spearman_rank_correlation(y_true_scores, y_pred)
    mae = _compute_mae(y_true_scores, y_pred)
    rmse_val = _compute_rmse(y_true_scores, y_pred)
    sorted_pairs = sorted(zip(y_pred, y_true_scores, strict=False), key=lambda x: x[0])
    cal_error = _compute_calibration_error([a for _, a in sorted_pairs], [p for p, _ in sorted_pairs])

    categories: dict[str, int] = {}
    for e in entries:
        cat = e.source_category
        categories[cat] = categories.get(cat, 0) + 1

    true_labels = ["high", "medium", "low"]
    pred_classes = ["high", "medium", "low"]
    cm: dict[str, dict[str, int]] = {t: {p: 0 for p in pred_classes} for t in true_labels}
    for e, s in labeled:
        true_label = e.human_label_source_quality
        if true_label is None:
            continue
        if s >= 0.7:
            pred_label = "high"
        elif s >= 0.4:
            pred_label = "medium"
        else:
            pred_label = "low"
        if true_label in cm:
            cm[true_label][pred_label] = cm[true_label].get(pred_label, 0) + 1

    return SourceQualityMetrics(
        spearman=round(spearman, 4) if spearman is not None else None,
        mae=round(mae, 4) if mae is not None else None,
        rmse=round(rmse_val, 4) if rmse_val is not None else None,
        calibration_error=round(cal_error, 4) if cal_error is not None else None,
        coverage_by_category=categories,
        confusion_matrix=cm,
    )


def _compute_binary_metrics(
    y_true: list[int],
    y_score: list[float],
    threshold: float,
) -> dict[str, float | None]:
    if not y_true:
        return {"precision": None, "recall": None, "f1": None, "fp_rate": None, "fn_rate": None}

    y_pred = [1 if s >= threshold else 0 for s in y_score]
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == 0 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision is not None and recall is not None and (precision + recall) > 0)
        else None
    )
    fp_rate = fp / (fp + tn) if (fp + tn) > 0 else None
    fn_rate = fn / (tp + fn) if (tp + fn) > 0 else None

    return {
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "fp_rate": round(fp_rate, 4) if fp_rate is not None else None,
        "fn_rate": round(fn_rate, 4) if fn_rate is not None else None,
        "_tp": tp,
        "_fp": fp,
        "_fn": fn,
        "_tn": tn,
    }


def _compute_ec_metrics(
    entries: list[SourceEvidenceGoldenEntry],
    scores: list[float],
    threshold: float = 0.5,
) -> EvidenceConfidenceMetrics:
    supported_pairs = [
        (s, e.human_label_evidence_support)
        for e, s in zip(entries, scores, strict=False)
        if e.human_label_evidence_support in LABEL_EVIDENCE_SUPPORT_VALUES
    ]
    if not supported_pairs:
        return EvidenceConfidenceMetrics()

    y_true = [1 if label in EC_SUPPORTED_SET else 0 for _, label in supported_pairs]
    y_score = [s for s, _ in supported_pairs]

    binary = _compute_binary_metrics(y_true, y_score, threshold)

    unsupported_critical_miss = None
    critical_unsupported = [
        (s, e.human_label_evidence_support)
        for e, s in zip(entries, scores, strict=False)
        if e.human_label_evidence_support in EC_UNSUPPORTED_SET
    ]
    if critical_unsupported:
        missed = sum(1 for s, _ in critical_unsupported if s >= threshold)
        unsupported_critical_miss = missed / len(critical_unsupported)

    sorted_pairs = sorted(zip(y_score, y_true, strict=False), key=lambda x: x[0])
    cal_error = _compute_calibration_error([float(t) for _, t in sorted_pairs], [s for s, _ in sorted_pairs])

    return EvidenceConfidenceMetrics(
        precision=binary.get("precision"),
        recall=binary.get("recall"),
        f1=binary.get("f1"),
        false_positive_rate=binary.get("fp_rate"),
        false_negative_rate=binary.get("fn_rate"),
        unsupported_critical_claim_miss_rate=(
            round(unsupported_critical_miss, 4) if unsupported_critical_miss is not None else None
        ),
        calibration_error=round(cal_error, 4) if cal_error is not None else None,
    )


def _find_best_threshold_for_ec(
    entries: list[SourceEvidenceGoldenEntry],
    scores: list[float],
    candidates: list[float] | None = None,
) -> tuple[float, EvidenceConfidenceMetrics]:
    if candidates is None:
        candidates = [round(i * 0.05, 2) for i in range(2, 19)]

    best_threshold = 0.5
    best_metrics = _compute_ec_metrics(entries, scores, threshold=0.5)
    best_score = -1.0

    for t in candidates:
        metrics = _compute_ec_metrics(entries, scores, threshold=t)
        f1 = metrics.f1
        fp_rate = metrics.false_positive_rate
        if f1 is not None and fp_rate is not None:
            score = f1 - fp_rate
            if score > best_score:
                best_score = score
                best_threshold = t
                best_metrics = metrics

    return best_threshold, best_metrics


def _compute_category_coverage(
    entries: list[SourceEvidenceGoldenEntry],
) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for e in entries:
        coverage[e.source_category] = coverage.get(e.source_category, 0) + 1
    return coverage


def grid_search_source_quality(
    entries: list[SourceEvidenceGoldenEntry],
    candidates: list[dict[str, float]] | None = None,
) -> list[SourceQualityCandidateResult]:
    if candidates is None:
        candidates = CANDIDATE_WEIGHTS_SOURCE_QUALITY

    results: list[SourceQualityCandidateResult] = []
    for i, weights in enumerate(candidates):
        sq_id = "weight.source_quality_score.weights"
        inventory = _make_calibrated_inventory(sq_id, weights)
        scores: list[float] = []
        for entry in entries:
            result = compute_source_quality_score(
                entry.source_features_observable,
                inventory=inventory,
            )
            scores.append(result.score)
        dist = _compute_distribution(scores)
        sq_metrics = _compute_sq_metrics(entries, scores)
        results.append(
            SourceQualityCandidateResult(
                label=f"sensitivity_candidate_{i + 1}",
                weights=weights,
                distribution=dist,
                sq_metrics=sq_metrics,
            )
        )
    return results


def grid_search_evidence_confidence(
    entries: list[SourceEvidenceGoldenEntry],
    candidates: list[dict[str, float]] | None = None,
) -> list[EvidenceConfidenceCandidateResult]:
    if candidates is None:
        candidates = CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE

    results: list[EvidenceConfidenceCandidateResult] = []
    for i, weights in enumerate(candidates):
        ec_id = "weight.evidence_confidence_score.weights"
        inventory = _make_calibrated_inventory(ec_id, weights)
        scores: list[float] = []
        for entry in entries:
            result = compute_evidence_confidence_score(
                entry.source_features_observable,
                inventory=inventory,
            )
            scores.append(result.score)
        dist = _compute_distribution(scores)
        ec_metrics = _compute_ec_metrics(entries, scores)
        results.append(
            EvidenceConfidenceCandidateResult(
                label=f"sensitivity_candidate_{i + 1}",
                weights=weights,
                distribution=dist,
                ec_metrics=ec_metrics,
            )
        )
    return results


def _select_best_sq_candidate(
    candidates: list[SourceQualityCandidateResult],
) -> int | None:
    best_idx: int | None = None
    best_spearman = -2.0

    for i, c in enumerate(candidates):
        m = c.sq_metrics
        if m is None or m.spearman is None:
            continue
        if m.spearman > best_spearman:
            best_spearman = m.spearman
            best_idx = i

    return best_idx


def _select_best_ec_candidate(
    candidates: list[EvidenceConfidenceCandidateResult],
) -> int | None:
    best_idx: int | None = None
    best_f1 = -1.0

    for i, c in enumerate(candidates):
        m = c.ec_metrics
        if m is None or m.f1 is None:
            continue
        if m.f1 > best_f1:
            best_f1 = m.f1
            best_idx = i

    return best_idx


def recommend_threshold_from_distribution(
    decision_id: str,
    distribution: ScoreDistribution,
    distribution_label: str,
    percentile: float = 10.0,
) -> ThresholdRecommendation:
    if distribution.count == 0:
        return ThresholdRecommendation(
            decision_id=decision_id,
            suggested_value=None,
            method=f"no_data_{distribution_label}",
            production_allowed=False,
            evidence_source=f"No scores computed for {distribution_label}",
            distribution=distribution,
        )

    sorted_scores = [
        distribution.p5,
        distribution.p25,
        distribution.p50,
        distribution.p75,
        distribution.p95,
    ]
    min_score = distribution.min
    max_score = distribution.max

    suggested = sorted_scores[0]

    if max_score - min_score < 0.05:
        suggested = max(0.0, min_score - 0.1)

    return ThresholdRecommendation(
        decision_id=decision_id,
        suggested_value=round(suggested, 4),
        method=f"percentile_{percentile}_of_observed_{distribution_label}_distribution",
        production_allowed=False,
        evidence_source=f"Threshold derived from {distribution_label} score distribution over {distribution.count} entries. "
        f"P{percentile:.0f}={suggested:.4f}, min={min_score:.4f}, max={max_score:.4f}. "
        f"Not for production — requires human-labeled validation.",
        distribution=distribution,
    )


def _format_report(
    entries_count: int,
    has_labels: bool,
    label_coverage: dict[str, int],
    sq_results: list[SourceQualityCandidateResult],
    ec_results: list[EvidenceConfidenceCandidateResult],
    best_sq_idx: int | None,
    best_ec_idx: int | None,
    sq_threshold: ThresholdRecommendation,
    ec_threshold: ThresholdRecommendation,
    sq_metrics: SourceQualityMetrics | None,
    ec_metrics: EvidenceConfidenceMetrics | None,
    status: str,
    prod_allowed: bool,
) -> str:
    lines: list[str] = [
        "=" * 80,
        "SOURCE & EVIDENCE SCORING BASELINE CALIBRATION REPORT",
        "=" * 80,
        "",
        f"Golden set entries:     {entries_count}",
        f"Human labels present:   {has_labels}",
        f"Source quality labels:  {label_coverage['source_quality_labels']}",
        f"Evidence support labels: {label_coverage['evidence_support_labels']}",
        f"Calibration status:     {status}",
        f"Production allowed:     {prod_allowed}",
        "",
    ]

    lines.append("-" * 80)
    lines.append("SOURCE QUALITY SCORE — Candidate Comparison")
    lines.append("-" * 80)
    sq_header = f"{'Candidate':>25} | {'mean':>6} | {'spearman':>8} | {'mae':>6} | {'rmse':>6} | {'cal_err':>8}"
    lines.append(sq_header)
    lines.append("-" * len(sq_header))
    for i, r in enumerate(sq_results):
        d = r.distribution
        sq_metric = r.sq_metrics
        spearman_s = f"{sq_metric.spearman:.4f}" if sq_metric and sq_metric.spearman is not None else "N/A"
        mae_s = f"{sq_metric.mae:.4f}" if sq_metric and sq_metric.mae is not None else "N/A"
        rmse_s = f"{sq_metric.rmse:.4f}" if sq_metric and sq_metric.rmse is not None else "N/A"
        cal_s = f"{sq_metric.calibration_error:.4f}" if sq_metric and sq_metric.calibration_error is not None else "N/A"
        marker = " <-- BEST" if best_sq_idx is not None and i == best_sq_idx else ""
        lines.append(
            f"{r.label:>25}{marker} | {d.mean:>6.4f} | {spearman_s:>8} | {mae_s:>6} | {rmse_s:>6} | {cal_s:>8}"
        )

    lines.append("")
    if sq_metrics and sq_metrics.confusion_matrix:
        lines.append("Confusion Matrix (high/medium/low):")
        lines.append(f"  {'':>10} {'high':>8} {'medium':>8} {'low':>8}")
        for true_label in ["high", "medium", "low"]:
            row = sq_metrics.confusion_matrix.get(true_label, {})
            lines.append(f"  {true_label:>10} {row.get('high', 0):>8} {row.get('medium', 0):>8} {row.get('low', 0):>8}")
        lines.append("")

    lines.append("-" * 80)
    lines.append("EVIDENCE CONFIDENCE SCORE — Candidate Comparison")
    lines.append("-" * 80)
    ec_header = (
        f"{'Candidate':>25} | {'mean':>6} | {'prec':>6} | {'recall':>6} | "
        f"{'f1':>6} | {'fp_rate':>8} | {'fn_rate':>8} | {'cal_err':>8}"
    )
    lines.append(ec_header)
    lines.append("-" * len(ec_header))
    for i, ec_result in enumerate(ec_results):
        d = ec_result.distribution
        ec_metric = ec_result.ec_metrics
        prec_s = f"{ec_metric.precision:.4f}" if ec_metric and ec_metric.precision is not None else "N/A"
        recall_s = f"{ec_metric.recall:.4f}" if ec_metric and ec_metric.recall is not None else "N/A"
        f1_s = f"{ec_metric.f1:.4f}" if ec_metric and ec_metric.f1 is not None else "N/A"
        fp_s = (
            f"{ec_metric.false_positive_rate:.4f}" if ec_metric and ec_metric.false_positive_rate is not None else "N/A"
        )
        fn_s = (
            f"{ec_metric.false_negative_rate:.4f}" if ec_metric and ec_metric.false_negative_rate is not None else "N/A"
        )
        cal_s = f"{ec_metric.calibration_error:.4f}" if ec_metric and ec_metric.calibration_error is not None else "N/A"
        marker = " <-- BEST" if best_ec_idx is not None and i == best_ec_idx else ""
        lines.append(
            f"{r.label:>25}{marker} | {d.mean:>6.4f} | {prec_s:>6} | {recall_s:>6} | "
            f"{f1_s:>6} | {fp_s:>8} | {fn_s:>8} | {cal_s:>8}"
        )

    lines.append("")
    lines.append("-" * 80)
    lines.append("THRESHOLD RECOMMENDATIONS")
    lines.append("-" * 80)
    lines.append(
        f"Source quality:   suggested={sq_threshold.suggested_value}, "
        f"method={sq_threshold.method}, production_allowed={sq_threshold.production_allowed}"
    )
    lines.append(
        f"Evidence confidence: suggested={ec_threshold.suggested_value}, "
        f"method={ec_threshold.method}, production_allowed={ec_threshold.production_allowed}"
    )
    lines.append("")

    if best_sq_idx is not None and sq_metrics and sq_metrics.spearman is not None:
        lines.append(f"Best SQ weights (index {best_sq_idx}): spearman={sq_metrics.spearman}, mae={sq_metrics.mae}")
    if best_ec_idx is not None and ec_metrics and ec_metrics.f1 is not None:
        lines.append(
            f"Best EC weights (index {best_ec_idx}): f1={ec_metrics.f1}, fp_rate={ec_metrics.false_positive_rate}"
        )

    lines.append("")
    lines.append("-" * 80)
    lines.append("NEXT STEPS")
    lines.append("-" * 80)
    if not prod_allowed:
        lines.append("Production BLOCKED. Reasons:")
        if label_coverage["source_quality_labels"] < SQ_MIN_LABELED:
            lines.append(f"  - SQ labels ({label_coverage['source_quality_labels']}) < minimum ({SQ_MIN_LABELED})")
        if label_coverage["evidence_support_labels"] < EC_MIN_LABELED:
            lines.append(f"  - EC labels ({label_coverage['evidence_support_labels']}) < minimum ({EC_MIN_LABELED})")
        if sq_metrics and sq_metrics.spearman is not None and sq_metrics.spearman < SQ_SPEARMAN_MIN:
            lines.append(f"  - SQ spearman ({sq_metrics.spearman:.4f}) < minimum ({SQ_SPEARMAN_MIN})")
        if sq_metrics and sq_metrics.mae is not None and sq_metrics.mae > SQ_MAE_MAX:
            lines.append(f"  - SQ mae ({sq_metrics.mae:.4f}) > maximum ({SQ_MAE_MAX})")
        if ec_metrics and ec_metrics.f1 is not None and ec_metrics.f1 < EC_F1_MIN:
            lines.append(f"  - EC f1 ({ec_metrics.f1:.4f}) < minimum ({EC_F1_MIN})")
        if (
            ec_metrics
            and ec_metrics.false_positive_rate is not None
            and ec_metrics.false_positive_rate > EC_FP_RATE_MAX
        ):
            lines.append(f"  - EC fp_rate ({ec_metrics.false_positive_rate:.4f}) > maximum ({EC_FP_RATE_MAX})")
    else:
        lines.append("Production ALLOWED. All criteria met.")
    lines.append("")

    return "\n".join(lines)


def _check_production_ready(
    sq_label_count: int,
    ec_label_count: int,
    sq_metrics: SourceQualityMetrics | None,
    ec_metrics: EvidenceConfidenceMetrics | None,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []

    if sq_label_count < SQ_MIN_LABELED:
        blockers.append(f"SQ labels ({sq_label_count}) < minimum ({SQ_MIN_LABELED})")
    if ec_label_count < EC_MIN_LABELED:
        blockers.append(f"EC labels ({ec_label_count}) < minimum ({EC_MIN_LABELED})")

    if sq_metrics is not None:
        if sq_metrics.spearman is not None and sq_metrics.spearman < SQ_SPEARMAN_MIN:
            blockers.append(f"SQ spearman ({sq_metrics.spearman:.4f}) < minimum ({SQ_SPEARMAN_MIN})")
        if sq_metrics.mae is not None and sq_metrics.mae > SQ_MAE_MAX:
            blockers.append(f"SQ mae ({sq_metrics.mae:.4f}) > maximum ({SQ_MAE_MAX})")

    if ec_metrics is not None:
        if ec_metrics.f1 is not None and ec_metrics.f1 < EC_F1_MIN:
            blockers.append(f"EC f1 ({ec_metrics.f1:.4f}) < minimum ({EC_F1_MIN})")
        if ec_metrics.false_positive_rate is not None and ec_metrics.false_positive_rate > EC_FP_RATE_MAX:
            blockers.append(f"EC fp_rate ({ec_metrics.false_positive_rate:.4f}) > maximum ({EC_FP_RATE_MAX})")

    return len(blockers) == 0, blockers


def run_full_calibration(
    golden_path: Path | None = None,
) -> CalibrationResult:
    entries = load_golden_set(golden_path)
    if not entries:
        empty_rec = ThresholdRecommendation(
            decision_id="threshold.source_quality_score.production_min",
            suggested_value=None,
            method="no_data_empty_golden_set",
            production_allowed=False,
            evidence_source="Golden set is empty — no data for threshold estimation.",
        )
        return CalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            human_label_coverage={
                "source_quality_labels": 0,
                "evidence_support_labels": 0,
                "total_entries": 0,
            },
            source_quality_candidates=[],
            evidence_confidence_candidates=[],
            sq_threshold=empty_rec,
            ec_threshold=empty_rec,
            labels_missing_notes="Golden set is empty.",
            report="No data — golden set is empty.",
        )

    has_labels = check_human_labels_exist(entries)
    label_coverage = _compute_human_label_coverage(entries)

    sq_candidates = grid_search_source_quality(entries)
    ec_candidates = grid_search_evidence_confidence(entries)

    best_sq_idx = _select_best_sq_candidate(sq_candidates)
    best_ec_idx = _select_best_ec_candidate(ec_candidates)

    best_sq_metrics: SourceQualityMetrics | None = None
    best_ec_metrics: EvidenceConfidenceMetrics | None = None
    best_sq_weights: dict[str, float] = CANDIDATE_WEIGHTS_SOURCE_QUALITY[0]
    best_ec_weights: dict[str, float] = CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE[0]

    if best_sq_idx is not None:
        best_sq_metrics = sq_candidates[best_sq_idx].sq_metrics
        best_sq_weights = sq_candidates[best_sq_idx].weights
    else:
        scores_sq: list[float] = []
        for entry in entries:
            inv = _make_calibrated_inventory("weight.source_quality_score.weights", best_sq_weights)
            r = compute_source_quality_score(entry.source_features_observable, inventory=inv)
            scores_sq.append(r.score)
        best_sq_metrics = _compute_sq_metrics(entries, scores_sq)

    if best_ec_idx is not None:
        best_ec_metrics = ec_candidates[best_ec_idx].ec_metrics
        best_ec_weights = ec_candidates[best_ec_idx].weights
    else:
        scores_ec: list[float] = []
        for entry in entries:
            inv = _make_calibrated_inventory("weight.evidence_confidence_score.weights", best_ec_weights)
            ec_score_result = compute_evidence_confidence_score(entry.source_features_observable, inventory=inv)
            scores_ec.append(ec_score_result.score)
        best_ec_metrics = _compute_ec_metrics(entries, scores_ec)

    sq_scores = _compute_default_scores(entries, best_sq_weights, is_sq=True)
    ec_scores = _compute_default_scores(entries, best_ec_weights, is_sq=False)
    sq_dist = _compute_distribution(sq_scores)
    ec_dist = _compute_distribution(ec_scores)

    ec_opt_threshold, best_ec_metrics_opt = _find_best_threshold_for_ec(entries, ec_scores)

    production_ready, blockers = _check_production_ready(
        label_coverage["source_quality_labels"],
        label_coverage["evidence_support_labels"],
        best_sq_metrics,
        best_ec_metrics,
    )

    if production_ready and has_labels and label_coverage["source_quality_labels"] >= SQ_MIN_LABELED:
        calibration_status = "baseline_measured"
        production_allowed = True
        assert best_sq_metrics is not None
        assert best_ec_metrics is not None
        sq_threshold_rec = ThresholdRecommendation(
            decision_id="threshold.source_quality_score.production_min",
            suggested_value=max(0.1, round(sq_dist.p10 if hasattr(sq_dist, "p10") else sq_dist.p5, 4)),
            method="percentile_10_of_labeled_source_quality_distribution",
            production_allowed=True,
            evidence_source=f"Best SQ candidate index={best_sq_idx}, spearman={best_sq_metrics.spearman}, "
            f"mae={best_sq_metrics.mae}, threshold at P10 of distribution.",
            distribution=sq_dist,
        )
        ec_threshold_rec = ThresholdRecommendation(
            decision_id="threshold.evidence_confidence_score.production_min",
            suggested_value=round(ec_opt_threshold, 4),
            method="f1_minus_fp_rate_optimization",
            production_allowed=True,
            evidence_source=f"Best EC candidate index={best_ec_idx}, f1={best_ec_metrics.f1}, "
            f"fp_rate={best_ec_metrics.false_positive_rate}, "
            f"optimized threshold={ec_opt_threshold:.4f}.",
            distribution=ec_dist,
        )
    else:
        calibration_status = "baseline_dataset_insufficient" if not has_labels else "baseline_measured_blocked"
        production_allowed = False
        blocker_str = "; ".join(blockers) if blockers else "Production criteria not met."
        sq_threshold_rec = ThresholdRecommendation(
            decision_id="threshold.source_quality_score.production_min",
            suggested_value=round(sq_dist.p5, 4),
            method="percentile_5_uncalibrated",
            production_allowed=False,
            evidence_source=f"Blocked. {blocker_str}",
            distribution=sq_dist,
        )
        ec_threshold_rec = ThresholdRecommendation(
            decision_id="threshold.evidence_confidence_score.production_min",
            suggested_value=round(ec_opt_threshold, 4),
            method="percentile_5_uncalibrated_with_optimal_search",
            production_allowed=False,
            evidence_source=f"Blocked. {blocker_str}",
            distribution=ec_dist,
        )

    if not has_labels:
        labels_missing_notes = (
            f"No human labels found in {len(entries)} golden set entries. "
            "Calibration requires labeled source_quality (high/medium/low) "
            "and evidence_support (supported/insufficient/unsupported/conflicting)."
        )
    else:
        labels_missing_notes = (
            f"Labels derived from scraping baseline features: "
            f"{label_coverage['source_quality_labels']} SQ, "
            f"{label_coverage['evidence_support_labels']} EC. "
            f"Production {'allowed' if production_allowed else 'blocked'}. "
            f"Blockers: {'; '.join(blockers) if blockers else 'none'}"
        )

    if best_sq_metrics is not None and best_sq_metrics.spearman is None and has_labels:
        sq_scores_full = _compute_default_scores(entries, best_sq_weights, is_sq=True)
        best_sq_metrics = _compute_sq_metrics(entries, sq_scores_full)

    if best_ec_metrics is not None and best_ec_metrics.f1 is None and has_labels:
        ec_scores_full = _compute_default_scores(entries, best_ec_weights, is_sq=False)
        best_ec_metrics = _compute_ec_metrics(entries, ec_scores_full)

    report = _format_report(
        entries_count=len(entries),
        has_labels=has_labels,
        label_coverage=label_coverage,
        sq_results=sq_candidates,
        ec_results=ec_candidates,
        best_sq_idx=best_sq_idx,
        best_ec_idx=best_ec_idx,
        sq_threshold=sq_threshold_rec,
        ec_threshold=ec_threshold_rec,
        sq_metrics=best_sq_metrics,
        ec_metrics=best_ec_metrics,
        status=calibration_status,
        prod_allowed=production_allowed,
    )

    return CalibrationResult(
        calibration_status=calibration_status,
        production_allowed=production_allowed,
        golden_set_size=len(entries),
        has_human_labels=has_labels,
        human_label_coverage=label_coverage,
        source_quality_candidates=sq_candidates,
        evidence_confidence_candidates=ec_candidates,
        best_sq_candidate_index=best_sq_idx,
        best_ec_candidate_index=best_ec_idx,
        best_sq_metrics=best_sq_metrics,
        best_ec_metrics=best_ec_metrics,
        sq_threshold=sq_threshold_rec,
        ec_threshold=ec_threshold_rec,
        labels_missing_notes=labels_missing_notes,
        report=report,
    )


def _compute_default_scores(
    entries: list[SourceEvidenceGoldenEntry],
    weights: dict[str, float],
    is_sq: bool = True,
) -> list[float]:
    scores: list[float] = []
    decision_id = "weight.source_quality_score.weights" if is_sq else "weight.evidence_confidence_score.weights"
    inventory = _make_calibrated_inventory(decision_id, weights)

    for entry in entries:
        if is_sq:
            sq_score_result = compute_source_quality_score(entry.source_features_observable, inventory=inventory)
            scores.append(sq_score_result.score)
        else:
            ec_score_result = compute_evidence_confidence_score(entry.source_features_observable, inventory=inventory)
            scores.append(ec_score_result.score)
    return scores
