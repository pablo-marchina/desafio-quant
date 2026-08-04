"""Baseline evaluator for recommendation ranking calibration.

Loads a human-labeled golden set of recommendation examples and
computes calibration metrics (precision@k, recall@k, MRR, NDCG@k,
false positive rate, evidence/RAG support rates, actionability/
mapping score correlation, confidence calibration error).

Determines production readiness and generates DecisionCalibrationRecords.

Usage:
    result = run_recommendation_baseline_calibration()
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.quality.decision_calibration_registry import (
    CalibrationMethod,
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
)

logger = logging.getLogger(__name__)

random.seed(42)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_GOLDEN_SET_PATH = Path("data/eval/golden_recommendation_baseline.json")

# ---------------------------------------------------------------------------
# Production criteria thresholds
# ---------------------------------------------------------------------------

MIN_LABELED_ENTRIES = 20
MIN_SPEARMAN = 0.5
MAX_MAE = 0.2
MAX_FP_RATE = 0.3
MIN_CALIBRATION_COVERAGE = 0.5

# ---------------------------------------------------------------------------
# Feature names used in recommendation_priority_score
# ---------------------------------------------------------------------------

PRIORITY_FEATURE_NAMES: list[str] = [
    "mapping_score",
    "mapping_confidence",
    "gap_severity_score",
    "gap_confidence_score",
    "evidence_support",
    "rag_support",
    "business_impact",
    "implementation_complexity_inverse",
]

# ---------------------------------------------------------------------------
# Candidate weight sets for grid search
# ---------------------------------------------------------------------------

CANDIDATE_PRIORITY_WEIGHTS: list[dict[str, float]] = [
    # 0 — Default: current registry weights
    {
        "mapping_score": 0.20,
        "mapping_confidence": 0.15,
        "gap_severity_score": 0.10,
        "gap_confidence_score": 0.10,
        "evidence_support": 0.10,
        "rag_support": 0.10,
        "business_impact": 0.15,
        "implementation_complexity_inverse": 0.10,
    },
    # 1 — Equal weights
    {
        "mapping_score": 0.125,
        "mapping_confidence": 0.125,
        "gap_severity_score": 0.125,
        "gap_confidence_score": 0.125,
        "evidence_support": 0.125,
        "rag_support": 0.125,
        "business_impact": 0.125,
        "implementation_complexity_inverse": 0.125,
    },
    # 2 — Evidence-heavy
    {
        "mapping_score": 0.10,
        "mapping_confidence": 0.10,
        "gap_severity_score": 0.10,
        "gap_confidence_score": 0.10,
        "evidence_support": 0.20,
        "rag_support": 0.15,
        "business_impact": 0.10,
        "implementation_complexity_inverse": 0.15,
    },
    # 3 — Business-heavy
    {
        "mapping_score": 0.20,
        "mapping_confidence": 0.10,
        "gap_severity_score": 0.10,
        "gap_confidence_score": 0.05,
        "evidence_support": 0.10,
        "rag_support": 0.10,
        "business_impact": 0.25,
        "implementation_complexity_inverse": 0.10,
    },
    # 4 — Confidence-heavy
    {
        "mapping_score": 0.10,
        "mapping_confidence": 0.25,
        "gap_severity_score": 0.05,
        "gap_confidence_score": 0.20,
        "evidence_support": 0.10,
        "rag_support": 0.10,
        "business_impact": 0.10,
        "implementation_complexity_inverse": 0.10,
    },
]

# ---------------------------------------------------------------------------
# Feature extraction helpers (mirrors recommendation_engine)
# ---------------------------------------------------------------------------

_BUSINESS_IMPACT_MAP: dict[str, float] = {
    "compute_acceleration_gap": 0.75,
    "inference_performance_gap": 0.80,
    "training_scalability_gap": 0.65,
    "mlops_deployment_gap": 0.70,
    "data_pipeline_gap": 0.60,
    "model_optimization_gap": 0.65,
    "computer_vision_gap": 0.60,
    "genai_llm_gap": 0.70,
    "cybersecurity_ai_gap": 0.70,
    "nvidia_ecosystem_fit_gap": 0.50,
    "evidence_coverage_gap": 0.40,
    "technical_depth_gap": 0.40,
}

_COMPLEXITY_MAP: dict[str, float] = {
    "CUDA": 0.0,
    "cuDF": 0.0,
    "cuML": 0.0,
    "NVIDIA NIM": 0.0,
    "TensorRT-LLM": 0.5,
    "Triton Inference Server": 0.5,
    "NVIDIA RAPIDS": 0.5,
    "NVIDIA Riva": 0.5,
    "NVIDIA NeMo": 0.5,
    "NeMo Guardrails": 0.5,
    "NVIDIA TensorRT": 0.5,
    "MONAI": 0.5,
    "NVIDIA Omniverse": 1.0,
    "NVIDIA Isaac": 1.0,
    "NVIDIA Clara": 1.0,
    "NVIDIA Morpheus": 1.0,
    "NVIDIA AI Enterprise": 1.0,
}


def _get_business_impact(gap_type: str) -> float:
    return _BUSINESS_IMPACT_MAP.get(gap_type, 0.5)


def _get_complexity(tech_name: str) -> float:
    return _COMPLEXITY_MAP.get(tech_name, 0.5)


def _compute_weighted_score(
    features: dict[str, float],
    weights: dict[str, float],
) -> float:
    weight_sum = sum(weights.values())
    if weight_sum == 0.0:
        return 0.0
    raw = sum(weights.get(k, 0.0) * v for k, v in features.items() if k in weights)
    raw /= weight_sum
    return max(0.0, min(1.0, raw))


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    x_ranks = {v: i for i, v in enumerate(sorted(set(xs)))}
    y_ranks = {v: i for i, v in enumerate(sorted(set(ys)))}
    d = sum((x_ranks[x] - y_ranks[y]) ** 2 for x, y in zip(xs, ys, strict=True))
    return 1.0 - (6.0 * d) / (n * (n * n - 1))


def _distribution(values: list[float]) -> dict[str, float]:
    n = len(values)
    if n == 0:
        return {
            "count": 0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p1": 0.0,
            "p5": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p95": 0.0,
        }
    sorted_v = sorted(values)

    def idx_fn(p: float) -> int:
        return max(0, min(n - 1, int(n * p / 100)))

    return {
        "count": n,
        "mean": round(sum(values) / n, 4),
        "min": round(sorted_v[0], 4),
        "max": round(sorted_v[-1], 4),
        "p1": round(sorted_v[idx_fn(1)], 4),
        "p5": round(sorted_v[idx_fn(5)], 4),
        "p10": round(sorted_v[idx_fn(10)], 4),
        "p25": round(sorted_v[idx_fn(25)], 4),
        "p50": round(sorted_v[idx_fn(50)], 4),
        "p75": round(sorted_v[idx_fn(75)], 4),
        "p95": round(sorted_v[idx_fn(95)], 4),
    }


def _extract_priority_features(
    mapping_dict: dict[str, Any],
) -> dict[str, float]:
    features_nested = mapping_dict.get("features") or {}
    mapping_score = float(mapping_dict.get("mapping_score", 0.0))
    mapping_confidence = float(mapping_dict.get("mapping_confidence", 0.0))
    gap_type = mapping_dict.get("gap_type", "unknown")
    nvidia_tech = mapping_dict.get("nvidia_technology", "unknown")
    rag_ids = mapping_dict.get("supporting_rag_context_ids", [])
    ev_ids = mapping_dict.get("supporting_evidence_ids", [])

    return {
        "mapping_score": mapping_score,
        "mapping_confidence": mapping_confidence,
        "gap_severity_score": float(features_nested.get("gap_severity_score", 0.5)),
        "gap_confidence_score": float(features_nested.get("gap_confidence_score", 0.5)),
        "evidence_support": min(1.0, len(ev_ids) / 5.0),
        "rag_support": min(1.0, len(rag_ids) / 5.0),
        "business_impact": _get_business_impact(gap_type),
        "implementation_complexity_inverse": 1.0 - _get_complexity(nvidia_tech),
    }


# ---------------------------------------------------------------------------
# Golden entry schema
# ---------------------------------------------------------------------------


class HumanLabeledRecommendation(BaseModel):
    nvidia_technology: str
    human_label_relevance: float = Field(ge=0.0, le=1.0)
    human_label_priority_rank: int = Field(ge=1, le=100)
    human_label_actionability: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_rag_context_ids: list[str] = Field(default_factory=list)
    reviewer_id: str = ""
    label_source: str = ""
    label_notes: str = ""


class RecommendationGoldenEntry(BaseModel):
    eval_id: str
    startup_id: str
    startup_name: str
    gap_id: str
    gap_type: str
    nvidia_technology_mappings_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    rag_contexts_by_gap_snapshot: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    accepted_evidence_items_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    expected_recommendations: list[HumanLabeledRecommendation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metric data structures
# ---------------------------------------------------------------------------


@dataclass
class RankingMetrics:
    precision_at_k: dict[int, float] | None = None
    recall_at_k: dict[int, float] | None = None
    mrr: float | None = None
    ndcg_at_k: dict[int, float] | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None


@dataclass
class SupportMetrics:
    unsupported_recommendation_rate: float | None = None
    evidence_supported_recommendation_rate: float | None = None
    rag_supported_recommendation_rate: float | None = None
    evidence_and_rag_supported_rate: float | None = None
    no_support_rate: float | None = None


@dataclass
class ScoreCorrelationMetrics:
    actionability_score_correlation: float | None = None
    mapping_score_correlation: float | None = None
    priority_score_correlation: float | None = None
    mapping_confidence_correlation: float | None = None


@dataclass
class CalibrationErrorMetrics:
    confidence_calibration_error: float | None = None
    priority_score_calibration_error: float | None = None
    uncertainty_error_relationship: float | None = None


@dataclass
class RecommendationBaselineMetrics:
    ranking: RankingMetrics | None = None
    support: SupportMetrics | None = None
    correlation: ScoreCorrelationMetrics | None = None
    calibration: CalibrationErrorMetrics | None = None


# ---------------------------------------------------------------------------
# Golden set I/O
# ---------------------------------------------------------------------------


def load_recommendation_golden_set(
    path: Path | None = None,
) -> list[RecommendationGoldenEntry]:
    path = path or _GOLDEN_SET_PATH
    if not path.exists():
        logger.warning("Recommendation golden set not found at %s", path)
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries", raw.get("startups", []))
    return [RecommendationGoldenEntry(**e) for e in entries]


def check_recommendation_labels_exist(
    entries: list[RecommendationGoldenEntry],
) -> bool:
    for e in entries:
        if len(e.expected_recommendations) > 0:
            return True
    return False


def check_recommendation_labels_are_real(
    entries: list[RecommendationGoldenEntry],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    has_real = False
    for e in entries:
        for rec in e.expected_recommendations:
            src = (rec.label_source or "").lower()
            if "synthetic" in src:
                issues.append(
                    f"{e.eval_id}/{rec.nvidia_technology}: synthetic label "
                    f"(source='{rec.label_source}') — not allowed for production calibration."
                )
            else:
                has_real = True
    return has_real, issues


def count_labeled_recommendations(
    entries: list[RecommendationGoldenEntry],
) -> dict[str, Any]:
    total_labels = 0
    tech_counts: dict[str, int] = {}
    gap_type_counts: dict[str, int] = {}
    for e in entries:
        n = len(e.expected_recommendations)
        total_labels += n
        gap_type_counts[e.gap_type] = gap_type_counts.get(e.gap_type, 0) + n
        for rec in e.expected_recommendations:
            tech_counts[rec.nvidia_technology] = tech_counts.get(rec.nvidia_technology, 0) + 1
    return {
        "total_entries_with_labels": sum(1 for e in entries if len(e.expected_recommendations) > 0),
        "total_recommendation_labels": total_labels,
        "technology_coverage": tech_counts,
        "gap_type_coverage": gap_type_counts,
    }


# ---------------------------------------------------------------------------
# Synthetic golden set generation (for testing only)
# ---------------------------------------------------------------------------

_SYNTHETIC_GAP_TYPES: list[str] = [
    "compute_acceleration_gap",
    "inference_performance_gap",
    "training_scalability_gap",
    "mlops_deployment_gap",
    "data_pipeline_gap",
    "model_optimization_gap",
    "computer_vision_gap",
    "genai_llm_gap",
    "cybersecurity_ai_gap",
    "nvidia_ecosystem_fit_gap",
]

_SYNTHETIC_TECHNOLOGIES: list[str] = [
    "CUDA",
    "TensorRT",
    "Triton Inference Server",
    "NVIDIA NIM",
    "NVIDIA NeMo",
    "RAPIDS",
    "NVIDIA Riva",
    "NVIDIA Omniverse",
    "NVIDIA Isaac",
    "NVIDIA Morpheus",
    "NVIDIA AI Enterprise",
]

_GAP_TECH_MAP_SYNTH: dict[str, list[str]] = {
    "compute_acceleration_gap": ["CUDA", "NVIDIA AI Enterprise"],
    "inference_performance_gap": ["TensorRT", "Triton Inference Server", "NVIDIA NIM"],
    "training_scalability_gap": ["CUDA", "NVIDIA NeMo", "NVIDIA AI Enterprise"],
    "mlops_deployment_gap": ["Triton Inference Server", "NVIDIA NIM", "NVIDIA AI Enterprise"],
    "data_pipeline_gap": ["RAPIDS", "CUDA"],
    "model_optimization_gap": ["TensorRT", "NVIDIA NeMo", "NVIDIA NIM"],
    "computer_vision_gap": ["TensorRT", "NVIDIA NIM", "NVIDIA AI Enterprise"],
    "genai_llm_gap": ["NVIDIA NIM", "NVIDIA NeMo", "TensorRT"],
    "cybersecurity_ai_gap": ["NVIDIA Morpheus", "NVIDIA AI Enterprise"],
    "nvidia_ecosystem_fit_gap": ["NVIDIA AI Enterprise", "CUDA", "NVIDIA NIM"],
}


def generate_synthetic_recommendation_golden_set(
    count: int = 30,
) -> list[RecommendationGoldenEntry]:
    rng = random.Random(42)
    entries: list[RecommendationGoldenEntry] = []

    for i in range(count):
        gap_type = rng.choice(_SYNTHETIC_GAP_TYPES)
        candidates = _GAP_TECH_MAP_SYNTH.get(gap_type, ["CUDA"])
        n_recs = rng.randint(1, len(candidates))

        selected_techs = rng.sample(candidates, n_recs)
        mappings: list[dict[str, Any]] = []
        expected_recs: list[HumanLabeledRecommendation] = []

        for j, tech in enumerate(selected_techs):
            mapping_score = round(rng.uniform(0.2, 0.95), 4)
            mapping_confidence = round(rng.uniform(0.2, 0.95), 4)
            uncertainty = round(rng.uniform(0.0, 0.4), 4)
            ev_ids = [f"synth-ev-{i}-{j}-{k}" for k in range(rng.randint(0, 3))]
            rag_ids = [f"synth-rag-{i}-{j}-{k}" for k in range(rng.randint(0, 3))]

            priority_rank = j + 1
            relevance = max(0.0, min(1.0, mapping_score * 0.7 + mapping_confidence * 0.3 + rng.gauss(0, 0.05)))
            actionability = max(
                0.0,
                min(
                    1.0,
                    0.3 * (1.0 if len(ev_ids) > 0 else 0.0)
                    + 0.3 * (1.0 if len(rag_ids) > 0 else 0.0)
                    + 0.4 * relevance
                    + rng.gauss(0, 0.05),
                ),
            )

            mappings.append(
                {
                    "mapping_id": f"synth-map-{i}-{j}",
                    "gap_type": gap_type,
                    "nvidia_technology": tech,
                    "mapping_score": mapping_score,
                    "mapping_confidence": mapping_confidence,
                    "uncertainty": uncertainty,
                    "features": {
                        "gap_severity_score": round(rng.uniform(0.3, 0.9), 4),
                        "gap_confidence_score": round(rng.uniform(0.3, 0.9), 4),
                    },
                    "supporting_rag_context_ids": rag_ids,
                    "supporting_evidence_ids": ev_ids,
                    "production_allowed": True,
                    "blockers": [],
                    "calibration_decision_ids": [],
                }
            )

            expected_recs.append(
                HumanLabeledRecommendation(
                    nvidia_technology=tech,
                    human_label_relevance=round(relevance, 4),
                    human_label_priority_rank=priority_rank,
                    human_label_actionability=round(actionability, 4),
                    supporting_evidence_ids=ev_ids,
                    supporting_rag_context_ids=rag_ids,
                    reviewer_id="synthetic-generator",
                    label_source="derived_from_synthetic_reference",
                    label_notes=f"Synthetic label for {tech} on {gap_type} (rank={priority_rank})",
                )
            )

        entries.append(
            RecommendationGoldenEntry(
                eval_id=f"synth-rec-{i:04d}",
                startup_id=f"synth-startup-{i:04d}",
                startup_name=f"SynthRecommendation {i:04d}",
                gap_id=f"synth-gap-{i:04d}",
                gap_type=gap_type,
                nvidia_technology_mappings_snapshot=mappings,
                rag_contexts_by_gap_snapshot={gap_type: []},
                accepted_evidence_items_snapshot=[],
                expected_recommendations=expected_recs,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Priority score computation from mapping dicts
# ---------------------------------------------------------------------------


def _compute_priority_scores_for_mappings(
    mappings: list[dict[str, Any]],
    weights: dict[str, float],
    uncertainty_penalty: float = 0.1,
) -> list[float]:
    scores: list[float] = []
    for m in mappings:
        features = _extract_priority_features(m)
        uncertainty = float(m.get("uncertainty", 0.0))
        raw_priority = _compute_weighted_score(features, weights)
        priority_score = max(0.0, min(1.0, raw_priority - uncertainty * uncertainty_penalty))
        scores.append(priority_score)
    return scores


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_ranking_metrics(
    predicted_scores: list[float],
    human_labels: list[HumanLabeledRecommendation],
    mapping_technologies: list[str],
    k_values: list[int] | None = None,
) -> RankingMetrics | None:
    if k_values is None:
        k_values = [1, 3, 5]

    if not human_labels or len(predicted_scores) != len(mapping_technologies):
        return None

    relevance_threshold = 0.5
    label_map: dict[str, float] = {r.nvidia_technology: r.human_label_relevance for r in human_labels}
    {r.nvidia_technology: r.human_label_priority_rank for r in human_labels}

    paired = list(zip(predicted_scores, mapping_technologies, strict=True))
    paired.sort(key=lambda x: -x[0])
    predicted_ranking = [tech for _, tech in paired]

    relevant_set = {tech for tech, rel in label_map.items() if rel >= relevance_threshold}
    k_max = max(k_values)
    if k_max > len(predicted_ranking):
        k_max = len(predicted_ranking)

    precision_at_k: dict[int, float] = {}
    recall_at_k: dict[int, float] = {}
    ndcg_at_k: dict[int, float] = {}

    total_relevant = len(relevant_set)

    for k in k_values:
        if k > len(predicted_ranking):
            k = len(predicted_ranking)
        if k == 0:
            precision_at_k[k] = 0.0
            recall_at_k[k] = 0.0
            ndcg_at_k[k] = 0.0
            continue

        top_k = predicted_ranking[:k]
        relevant_in_top_k = sum(1 for t in top_k if t in relevant_set)

        prec = relevant_in_top_k / k
        rec = relevant_in_top_k / total_relevant if total_relevant > 0 else 0.0
        precision_at_k[k] = round(prec, 4)
        recall_at_k[k] = round(rec, 4)

        # NDCG@k
        actual_gains: list[float] = []
        ideal_gains: list[float] = []
        for tech in top_k:
            rel = label_map.get(tech, 0.0)
            actual_gains.append(rel)
        sorted_labels = sorted(label_map.values(), reverse=True)
        for i in range(k):
            ideal_gains.append(sorted_labels[i] if i < len(sorted_labels) else 0.0)

        def dcg(gains: list[float]) -> float:
            return gains[0] + sum(g / math.log2(i + 1) for i, g in enumerate(gains[1:], start=2))

        dcg_val = dcg(actual_gains)
        idcg_val = dcg(ideal_gains)
        ndcg_at_k[k] = round(dcg_val / idcg_val, 4) if idcg_val > 0 else 0.0

    # MRR
    mrr = 0.0
    for rank, tech in enumerate(predicted_ranking, start=1):
        if tech in relevant_set:
            mrr = 1.0 / rank
            break

    # FP / FN rates
    predicted_relevant = set(predicted_ranking[:k_max]) & set(mapping_technologies)
    fp = sum(1 for t in predicted_relevant if t not in relevant_set)
    fn = sum(1 for t in relevant_set if t not in predicted_relevant)
    total_predicted = len(predicted_relevant)
    total_actual = len(relevant_set)
    fp_rate = fp / total_predicted if total_predicted > 0 else 0.0
    fn_rate = fn / total_actual if total_actual > 0 else 0.0

    return RankingMetrics(
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
        mrr=round(mrr, 4),
        ndcg_at_k=ndcg_at_k,
        false_positive_rate=round(fp_rate, 4),
        false_negative_rate=round(fn_rate, 4),
    )


def _compute_support_metrics(
    mappings: list[dict[str, Any]],
    human_labels: list[HumanLabeledRecommendation],
) -> SupportMetrics | None:
    if not human_labels:
        return None

    label_techs = {r.nvidia_technology for r in human_labels}
    relevant_maps = [m for m in mappings if m.get("nvidia_technology") in label_techs]

    if not relevant_maps:
        return None

    total = len(relevant_maps)
    unsupported = sum(
        1 for m in relevant_maps if not m.get("supporting_evidence_ids") and not m.get("supporting_rag_context_ids")
    )
    ev_supported = sum(1 for m in relevant_maps if m.get("supporting_evidence_ids"))
    rag_supported = sum(1 for m in relevant_maps if m.get("supporting_rag_context_ids"))
    both_supported = sum(
        1 for m in relevant_maps if m.get("supporting_evidence_ids") and m.get("supporting_rag_context_ids")
    )

    return SupportMetrics(
        unsupported_recommendation_rate=round(unsupported / total, 4),
        evidence_supported_recommendation_rate=round(ev_supported / total, 4),
        rag_supported_recommendation_rate=round(rag_supported / total, 4),
        evidence_and_rag_supported_rate=round(both_supported / total, 4),
        no_support_rate=round(unsupported / total, 4),
    )


def _compute_correlation_metrics(
    mappings: list[dict[str, Any]],
    human_labels: list[HumanLabeledRecommendation],
) -> ScoreCorrelationMetrics | None:
    if not human_labels or not mappings:
        return None

    label_map: dict[str, HumanLabeledRecommendation] = {r.nvidia_technology: r for r in human_labels}
    pairs: list[tuple[float, float, float, float, float, float]] = []

    for m in mappings:
        tech = m.get("nvidia_technology", "")
        rec = label_map.get(tech)
        if rec is None:
            continue

        predicted_priority = float(m.get("mapping_score", 0.0))
        predicted_confidence = float(m.get("mapping_confidence", 0.0))
        predicted_actionability = _compute_actionability_proxy(m)

        pairs.append(
            (
                predicted_actionability,
                predicted_priority,
                predicted_confidence,
                rec.human_label_actionability,
                rec.human_label_relevance,
                rec.human_label_priority_rank,
            )
        )

    if len(pairs) < 3:
        return None

    pred_action, pred_priority, pred_conf, human_action, human_relevance, human_rank = zip(*pairs, strict=True)

    # Actionability correlation: human_label_actionability vs proxy
    actionability_corr = _spearman(list(pred_action), list(human_action))

    # Mapping score correlation: mapping_score vs human relevance
    mapping_corr = _spearman(list(pred_priority), list(human_relevance))

    # Priority score correlation (rank inverse)
    rank_scores = [1.0 / r for r in human_rank]
    priority_corr = _spearman(list(pred_priority), rank_scores)

    # Mapping confidence correlation
    confidence_corr = _spearman(list(pred_conf), list(human_relevance))

    return ScoreCorrelationMetrics(
        actionability_score_correlation=round(actionability_corr, 4),
        mapping_score_correlation=round(mapping_corr, 4),
        priority_score_correlation=round(priority_corr, 4),
        mapping_confidence_correlation=round(confidence_corr, 4),
    )


def _compute_actionability_proxy(mapping: dict[str, Any]) -> float:
    ev_support = 1.0 if mapping.get("supporting_evidence_ids") else 0.0
    rag_support = 1.0 if mapping.get("supporting_rag_context_ids") else 0.0
    mapping_score = float(mapping.get("mapping_score", 0.0))
    return 0.3 * ev_support + 0.3 * rag_support + 0.4 * mapping_score


def _compute_calibration_error_metrics(
    predicted_scores: list[float],
    human_labels: list[HumanLabeledRecommendation],
    mapping_technologies: list[str],
    prediction_source: str = "priority",
) -> CalibrationErrorMetrics | None:
    if len(predicted_scores) < 3 or not human_labels:
        return None

    label_relevance: dict[str, float] = {r.nvidia_technology: r.human_label_relevance for r in human_labels}
    paired: list[tuple[float, float]] = []
    for score, tech in zip(predicted_scores, mapping_technologies, strict=True):
        h_rel = label_relevance.get(tech)
        if h_rel is not None:
            paired.append((score, h_rel))

    if len(paired) < 3:
        return None

    preds, refs = zip(*paired, strict=True)
    abs_errors = [abs(p - r) for p, r in zip(preds, refs, strict=True)]
    mae = sum(abs_errors) / len(abs_errors)
    calibration_error = mae

    # Uncertainty-error relationship (using mapping uncertainties as proxy)
    uncertainty_error_relationship = 0.0

    return CalibrationErrorMetrics(
        confidence_calibration_error=round(calibration_error, 4),
        priority_score_calibration_error=round(calibration_error, 4),
        uncertainty_error_relationship=round(uncertainty_error_relationship, 4),
    )


# ---------------------------------------------------------------------------
# Grid search over weight candidates
# ---------------------------------------------------------------------------


@dataclass
class WeightCandidateResult:
    candidate_index: int
    weights: dict[str, float]
    spearman: float | None = None
    mae: float | None = None
    rmse: float | None = None
    ranking_precision_at_3: float | None = None
    ranking_recall_at_3: float | None = None
    mrr: float | None = None
    ndcg_at_3: float | None = None
    fp_rate: float | None = None
    predicted_scores: list[float] = field(default_factory=list)
    human_labels: list[float] = field(default_factory=list)


def _evaluate_weight_candidates(
    entries: list[RecommendationGoldenEntry],
    candidate_weights: list[dict[str, float]],
) -> list[WeightCandidateResult]:
    results: list[WeightCandidateResult] = []

    for idx, weights in enumerate(candidate_weights):
        all_predicted: list[float] = []
        all_human: list[float] = []
        entry_metrics: list[RankingMetrics | None] = []

        for entry in entries:
            if not entry.expected_recommendations:
                continue

            mappings = entry.nvidia_technology_mappings_snapshot
            if not mappings:
                continue

            techs = [m.get("nvidia_technology", "") for m in mappings]
            predicted = _compute_priority_scores_for_mappings(mappings, weights)
            human_rel = [r.human_label_relevance for r in entry.expected_recommendations]

            all_predicted.extend(predicted)
            all_human.extend(human_rel)

            rm = _compute_ranking_metrics(predicted, entry.expected_recommendations, techs)
            entry_metrics.append(rm)

        if len(all_predicted) < 3:
            results.append(
                WeightCandidateResult(
                    candidate_index=idx,
                    weights=dict(weights),
                    spearman=None,
                    mae=None,
                    rmse=None,
                )
            )
            continue

        correlation = _spearman(all_predicted, all_human)
        abs_errors = [abs(p - h) for p, h in zip(all_predicted, all_human, strict=True)]
        mae_val = sum(abs_errors) / len(abs_errors)
        sq_errors = [(p - h) ** 2 for p, h in zip(all_predicted, all_human, strict=True)]
        rmse_val = math.sqrt(sum(sq_errors) / len(sq_errors))

        prec3_list = [rm.precision_at_k.get(3, 0.0) for rm in entry_metrics if rm and rm.precision_at_k]
        rec3_list = [rm.recall_at_k.get(3, 0.0) for rm in entry_metrics if rm and rm.recall_at_k]
        mrr_list = [rm.mrr for rm in entry_metrics if rm and rm.mrr is not None]
        ndcg3_list = [rm.ndcg_at_k.get(3, 0.0) for rm in entry_metrics if rm and rm.ndcg_at_k]
        fp_list = [rm.false_positive_rate for rm in entry_metrics if rm and rm.false_positive_rate is not None]

        avg_prec3 = sum(prec3_list) / len(prec3_list) if prec3_list else None
        avg_rec3 = sum(rec3_list) / len(rec3_list) if rec3_list else None
        avg_mrr = sum(mrr_list) / len(mrr_list) if mrr_list else None
        avg_ndcg3 = sum(ndcg3_list) / len(ndcg3_list) if ndcg3_list else None
        avg_fp = sum(fp_list) / len(fp_list) if fp_list else None

        results.append(
            WeightCandidateResult(
                candidate_index=idx,
                weights=dict(weights),
                spearman=round(correlation, 4),
                mae=round(mae_val, 4),
                rmse=round(rmse_val, 4),
                ranking_precision_at_3=round(avg_prec3, 4) if avg_prec3 is not None else None,
                ranking_recall_at_3=round(avg_rec3, 4) if avg_rec3 is not None else None,
                mrr=round(avg_mrr, 4) if avg_mrr is not None else None,
                ndcg_at_3=round(avg_ndcg3, 4) if avg_ndcg3 is not None else None,
                fp_rate=round(avg_fp, 4) if avg_fp is not None else None,
                predicted_scores=all_predicted,
                human_labels=all_human,
            )
        )

    results.sort(key=lambda r: (-(r.spearman or 0.0), r.mae if r.mae is not None else 1.0))
    return results


def _select_best_candidate(
    candidates: list[WeightCandidateResult],
) -> int | None:
    valid = [c for c in candidates if c.spearman is not None]
    if not valid:
        return None
    return valid[0].candidate_index


# ---------------------------------------------------------------------------
# Threshold and penalty calibration
# ---------------------------------------------------------------------------


def _calibrate_threshold_from_scores(
    predicted_scores: list[float],
    percentile: float = 5.0,
) -> dict[str, Any]:
    n = len(predicted_scores)
    if n < 3:
        return {"threshold": None, "method": "insufficient_data", "distribution": {}}

    sorted_scores = sorted(predicted_scores)

    def idx_fn(p: float) -> int:
        return max(0, min(n - 1, int(n * p / 100)))

    distribution = {
        "count": n,
        "mean": round(sum(predicted_scores) / n, 4),
        "p5": sorted_scores[idx_fn(5)],
        "p10": sorted_scores[idx_fn(10)],
        "p25": sorted_scores[idx_fn(25)],
        "p50": sorted_scores[idx_fn(50)],
        "p95": sorted_scores[idx_fn(95)],
        "min": sorted_scores[0],
        "max": sorted_scores[-1],
    }
    threshold = sorted_scores[idx_fn(int(percentile))]

    return {
        "threshold": round(threshold, 4),
        "method": f"percentile_p{int(percentile)}_of_predicted_scores",
        "percentile": percentile,
        "distribution": distribution,
        "explanation": (
            f"Threshold at P{int(percentile)} of predicted priority score distribution "
            f"({n} scores). Scores below P{int(percentile)} are excluded from production."
        ),
    }


def _calibrate_uncertainty_penalty_from_scores(
    predicted_scores: list[float],
    human_labels: list[float],
    uncertainties: list[float],
    penalty_candidates: list[float] | None = None,
) -> dict[str, Any]:
    if penalty_candidates is None:
        penalty_candidates = [0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    n = len(predicted_scores)
    if n < 3:
        return {"best_penalty": 0.0, "method": "insufficient_data", "results": []}

    results: list[dict[str, Any]] = []
    for penalty in penalty_candidates:
        adjusted = [max(0.0, min(1.0, p - u * penalty)) for p, u in zip(predicted_scores, uncertainties, strict=True)]
        abs_errors = [abs(a - h) for a, h in zip(adjusted, human_labels, strict=True)]
        mae_val = sum(abs_errors) / n
        sq_errors = [(a - h) ** 2 for a, h in zip(adjusted, human_labels, strict=True)]
        rmse_val = math.sqrt(sum(sq_errors) / n)
        max_error = max(abs_errors)
        results.append(
            {
                "penalty": penalty,
                "mae": round(mae_val, 4),
                "rmse": round(rmse_val, 4),
                "max_error": round(max_error, 4),
            }
        )

    results.sort(key=lambda r: (r["mae"], r["max_error"]))
    best = results[0]

    return {
        "method": "sensitivity_analysis_over_human_labels",
        "candidates_tested": penalty_candidates,
        "results": results,
        "best_penalty": best["penalty"],
        "best_mae": best["mae"],
        "best_max_error": best["max_error"],
        "explanation": (
            f"Selected penalty={best['penalty']} minimizing MAE against human labels. "
            f"MAE={best['mae']}, max_error={best['max_error']}."
        ),
    }


def _recommend_minimum_mapping_confidence(
    scores: list[float],
) -> dict[str, Any]:
    if len(scores) < 3:
        return {"recommended_min": 0.20, "method": "insufficient_data", "n": len(scores)}

    sorted_s = sorted(scores)
    n = len(sorted_s)
    p10_idx = max(0, int(n * 0.10) - 1)
    p10 = sorted_s[p10_idx]
    p5_idx = max(0, int(n * 0.05) - 1)
    p5 = sorted_s[p5_idx]
    mean = sum(sorted_s) / n

    recommended = max(0.10, round(p10, 2))

    return {
        "recommended_min": recommended,
        "method": "percentile_p10_of_mapping_confidence",
        "p10": round(p10, 4),
        "p5": round(p5, 4),
        "mean": round(mean, 4),
        "median": round(sorted_s[n // 2], 4),
        "n": n,
        "explanation": (
            f"Minimum mapping confidence at P10 of distribution ({n} scores). "
            f"P10={p10:.4f}, P5={p5:.4f}, mean={mean:.4f}. "
            f"Recommended minimum={recommended}. Blocks lowest 10%."
        ),
    }


def _recommend_minimum_evidence_support(
    entries: list[RecommendationGoldenEntry],
) -> dict[str, Any]:
    ratios: list[float] = []
    for e in entries:
        n_maps = len(e.nvidia_technology_mappings_snapshot) or 1
        has_evidence = sum(1 for m in e.nvidia_technology_mappings_snapshot if m.get("supporting_evidence_ids"))
        ratios.append(has_evidence / n_maps)

    if not ratios:
        return {"recommended_min": 0.0, "method": "insufficient_data", "n": 0}

    sorted_r = sorted(ratios)
    n = len(sorted_r)
    p5_idx = max(0, int(n * 0.05) - 1)
    p5 = sorted_r[p5_idx]
    mean = sum(ratios) / n

    return {
        "recommended_min": round(p5, 2),
        "method": "percentile_p5_of_support_ratio",
        "p5": round(p5, 4),
        "mean": round(mean, 4),
        "median": round(sorted_r[n // 2], 4),
        "n": n,
        "explanation": (
            f"Minimum evidence support at P5 of support ratio distribution ({n} entries). "
            f"P5={p5:.4f}, mean={mean:.4f}. Evidence is already gated at mapping level."
        ),
    }


# ---------------------------------------------------------------------------
# Production readiness check
# ---------------------------------------------------------------------------


def _check_recommendation_production_ready(
    labeled_entry_count: int,
    label_count: int,
    has_real_labels: bool,
    synthetic_issues: list[str],
    coverage_by_tech: dict[str, int],
    spearman: float | None,
    mae: float | None,
    fp_rate: float | None,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []

    if not has_real_labels:
        blockers.append("No real human labels found — synthetic labels cannot be used for production calibration.")
    if synthetic_issues:
        blockers.append(f"Synthetic labels in dataset: {len(synthetic_issues)} entries affected.")

    if labeled_entry_count < MIN_LABELED_ENTRIES:
        blockers.append(f"Labeled entries ({labeled_entry_count}) < minimum ({MIN_LABELED_ENTRIES})")
    if label_count < MIN_LABELED_ENTRIES:
        blockers.append(f"Recommendation labels ({label_count}) < minimum ({MIN_LABELED_ENTRIES})")

    if spearman is not None and spearman < MIN_SPEARMAN:
        blockers.append(f"Spearman correlation ({spearman:.4f}) < minimum ({MIN_SPEARMAN})")
    if mae is not None and mae > MAX_MAE:
        blockers.append(f"MAE ({mae:.4f}) > maximum ({MAX_MAE})")
    if fp_rate is not None and fp_rate > MAX_FP_RATE:
        blockers.append(f"False positive rate ({fp_rate:.4f}) > maximum ({MAX_FP_RATE})")

    if coverage_by_tech:
        tech_present = sum(1 for c in coverage_by_tech.values() if c > 0)
        total_tech = max(1, len(coverage_by_tech))
        coverage_ratio = tech_present / total_tech
        if coverage_ratio < MIN_CALIBRATION_COVERAGE:
            blockers.append(f"Technology coverage ({coverage_ratio:.2f}) < minimum ({MIN_CALIBRATION_COVERAGE})")

    return len(blockers) == 0, blockers


# ---------------------------------------------------------------------------
# Baseline calibration orchestrator
# ---------------------------------------------------------------------------


@dataclass
class RecommendationCalibrationResult:
    calibration_status: str
    production_allowed: bool
    golden_set_size: int
    has_human_labels: bool
    has_real_labels: bool
    synthetic_label_issues: list[str]
    label_coverage: dict[str, Any]
    candidate_results: list[WeightCandidateResult] = field(default_factory=list)
    best_candidate_index: int | None = None
    best_weights: dict[str, float] | None = None
    best_ranking_metrics: RankingMetrics | None = None
    best_support_metrics: SupportMetrics | None = None
    best_correlation_metrics: ScoreCorrelationMetrics | None = None
    best_calibration_metrics: CalibrationErrorMetrics | None = None
    all_predicted_scores: list[float] = field(default_factory=list)
    all_human_labels: list[float] = field(default_factory=list)
    uncertainties: list[float] = field(default_factory=list)
    production_threshold: dict[str, Any] | None = None
    confidence_threshold: dict[str, Any] | None = None
    uncertainty_penalty: dict[str, Any] | None = None
    minimum_mapping_confidence: dict[str, Any] | None = None
    minimum_evidence_support: dict[str, Any] | None = None
    production_blockers: list[str] | None = None
    report: str = ""


def _extract_uncertainties(
    entries: list[RecommendationGoldenEntry],
    techs: list[str],
) -> list[float]:
    uncertainties: list[float] = []
    for entry in entries:
        tech_set = {r.nvidia_technology for r in entry.expected_recommendations}
        for m in entry.nvidia_technology_mappings_snapshot:
            if m.get("nvidia_technology", "") in tech_set:
                uncertainties.append(float(m.get("uncertainty", 0.0)))
    return uncertainties


def _compute_entry_level_metrics(
    entries: list[RecommendationGoldenEntry],
    weights: dict[str, float],
) -> tuple[
    list[float],
    list[float],
    RankingMetrics | None,
    SupportMetrics | None,
    ScoreCorrelationMetrics | None,
    CalibrationErrorMetrics | None,
]:
    all_predicted: list[float] = []
    all_human: list[float] = []
    agg_rankings: list[RankingMetrics] = []

    for entry in entries:
        if not entry.expected_recommendations:
            continue
        mappings = entry.nvidia_technology_mappings_snapshot
        if not mappings:
            continue

        techs = [m.get("nvidia_technology", "") for m in mappings]
        predicted = _compute_priority_scores_for_mappings(mappings, weights)

        for p, rec in zip(predicted, entry.expected_recommendations, strict=False):
            if rec.nvidia_technology in techs:
                all_predicted.append(p)
                all_human.append(rec.human_label_relevance)

        rm = _compute_ranking_metrics(predicted, entry.expected_recommendations, techs)
        if rm:
            agg_rankings.append(rm)

    ranking_metrics = None
    support_metrics = _compute_support_metrics(
        [m for e in entries for m in e.nvidia_technology_mappings_snapshot],
        [r for e in entries for r in e.expected_recommendations],
    )
    correlation_metrics = _compute_correlation_metrics(
        [m for e in entries for m in e.nvidia_technology_mappings_snapshot],
        [r for e in entries for r in e.expected_recommendations],
    )
    calibration_metrics = _compute_calibration_error_metrics(
        all_predicted,
        [r for e in entries for r in e.expected_recommendations],
        [m.get("nvidia_technology", "") for e in entries for m in e.nvidia_technology_mappings_snapshot],
    )

    if agg_rankings:
        k_values = [1, 3, 5]
        ranking_metrics = RankingMetrics(
            precision_at_k={
                k: round(
                    sum(rm.precision_at_k.get(k, 0.0) for rm in agg_rankings if rm.precision_at_k) / len(agg_rankings),
                    4,
                )
                for k in k_values
            },
            recall_at_k={
                k: round(
                    sum(rm.recall_at_k.get(k, 0.0) for rm in agg_rankings if rm.recall_at_k) / len(agg_rankings),
                    4,
                )
                for k in k_values
            },
            mrr=round(sum(rm.mrr or 0.0 for rm in agg_rankings) / len(agg_rankings), 4),
            ndcg_at_k={
                k: round(
                    sum(rm.ndcg_at_k.get(k, 0.0) for rm in agg_rankings if rm.ndcg_at_k) / len(agg_rankings),
                    4,
                )
                for k in k_values
            },
            false_positive_rate=round(sum(rm.false_positive_rate or 0.0 for rm in agg_rankings) / len(agg_rankings), 4),
            false_negative_rate=round(sum(rm.false_negative_rate or 0.0 for rm in agg_rankings) / len(agg_rankings), 4),
        )

    return (
        all_predicted,
        all_human,
        ranking_metrics,
        support_metrics,
        correlation_metrics,
        calibration_metrics,
    )


def _format_report(result: RecommendationCalibrationResult) -> str:
    lines = [
        "=" * 72,
        "RECOMMENDATION BASELINE — CALIBRATION REPORT",
        "=" * 72,
        "",
        f"Golden set size: {result.golden_set_size}",
        f"Has human labels: {result.has_human_labels}",
        f"Has real (non-synthetic) labels: {result.has_real_labels}",
        f"Calibration status: {result.calibration_status}",
        f"Production allowed: {result.production_allowed}",
    ]
    lc = result.label_coverage
    lines.append(f"Entries with labels: {lc.get('total_entries_with_labels', 0)}")
    lines.append(f"Total recommendation labels: {lc.get('total_recommendation_labels', 0)}")
    lines.append(f"Technology coverage: {lc.get('technology_coverage', {})}")
    lines.append(f"Gap type coverage: {lc.get('gap_type_coverage', {})}")
    if result.synthetic_label_issues:
        lines.append(f"Synthetic label issues: {len(result.synthetic_label_issues)}")
        for issue in result.synthetic_label_issues[:5]:
            lines.append(f"  - {issue}")
    if result.production_blockers:
        lines.append("Blockers:")
        for b in result.production_blockers:
            lines.append(f"  - {b}")
    lines.append("")

    if result.candidate_results:
        lines.append("--- Priority weight candidates ---")
        for c in result.candidate_results:
            lines.append(
                f"  Candidate {c.candidate_index}: "
                f"spearman={c.spearman}, mae={c.mae}, rmse={c.rmse}, "
                f"prec@3={c.ranking_precision_at_3}, rec@3={c.ranking_recall_at_3}, "
                f"mrr={c.mrr}, ndcg@3={c.ndcg_at_3}"
            )
        if result.best_candidate_index is not None:
            bc = result.candidate_results[result.best_candidate_index]
            lines.append(f"  Best: candidate {result.best_candidate_index} — weights={bc.weights}")
    lines.append("")

    if result.best_ranking_metrics:
        rm = result.best_ranking_metrics
        lines.append("--- Ranking metrics (best weights) ---")
        if rm.precision_at_k:
            lines.append(f"  Precision@k: {rm.precision_at_k}")
        if rm.recall_at_k:
            lines.append(f"  Recall@k: {rm.recall_at_k}")
        if rm.ndcg_at_k:
            lines.append(f"  NDCG@k: {rm.ndcg_at_k}")
        lines.append(f"  MRR: {rm.mrr}")
        lines.append(f"  FP rate: {rm.false_positive_rate}")
        lines.append(f"  FN rate: {rm.false_negative_rate}")
    lines.append("")

    if result.best_support_metrics:
        sm = result.best_support_metrics
        lines.append("--- Support metrics ---")
        lines.append(f"  Unsupported rate: {sm.unsupported_recommendation_rate}")
        lines.append(f"  Evidence supported rate: {sm.evidence_supported_recommendation_rate}")
        lines.append(f"  RAG supported rate: {sm.rag_supported_recommendation_rate}")
        lines.append(f"  Both supported rate: {sm.evidence_and_rag_supported_rate}")

    if result.best_correlation_metrics:
        cm = result.best_correlation_metrics
        lines.append("--- Correlation metrics ---")
        lines.append(f"  Actionability correlation: {cm.actionability_score_correlation}")
        lines.append(f"  Mapping score correlation: {cm.mapping_score_correlation}")
        lines.append(f"  Priority score correlation: {cm.priority_score_correlation}")
        lines.append(f"  Mapping confidence correlation: {cm.mapping_confidence_correlation}")

    if result.best_calibration_metrics:
        ce = result.best_calibration_metrics
        lines.append("--- Calibration error ---")
        lines.append(f"  Confidence calibration error: {ce.confidence_calibration_error}")
        lines.append(f"  Priority score calibration error: {ce.priority_score_calibration_error}")

    lines.append("")

    if result.production_threshold:
        lines.append("--- Production threshold ---")
        lines.append(f"  Threshold: {result.production_threshold.get('threshold')}")
        lines.append(f"  Method: {result.production_threshold.get('method')}")
        if result.production_threshold.get("distribution"):
            d = result.production_threshold["distribution"]
            lines.append(f"  Distribution: mean={d.get('mean')}, p5={d.get('p5')}, p50={d.get('p50')}")

    if result.confidence_threshold:
        lines.append("--- Confidence threshold ---")
        lines.append(f"  Value: {result.confidence_threshold.get('recommended_min')}")
        lines.append(f"  Method: {result.confidence_threshold.get('method')}")

    if result.uncertainty_penalty:
        lines.append("--- Uncertainty penalty ---")
        lines.append(f"  Best penalty: {result.uncertainty_penalty.get('best_penalty')}")
        lines.append(f"  Best MAE: {result.uncertainty_penalty.get('best_mae')}")

    if result.minimum_mapping_confidence:
        lines.append("--- Minimum mapping confidence ---")
        lines.append(f"  Recommended: {result.minimum_mapping_confidence.get('recommended_min')}")

    if result.minimum_evidence_support:
        lines.append("--- Minimum evidence support ---")
        lines.append(f"  Recommended: {result.minimum_evidence_support.get('recommended_min')}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def run_recommendation_baseline_calibration(
    golden_path: Path | None = None,
    auto_generate_synthetic: bool = True,
) -> RecommendationCalibrationResult:
    path = golden_path or _GOLDEN_SET_PATH
    entries = load_recommendation_golden_set(path)

    if not entries and auto_generate_synthetic:
        logger.info("Recommendation golden set empty — generating synthetic entries for testing...")
        entries = generate_synthetic_recommendation_golden_set(count=30)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "entries": [e.model_dump(mode="json") for e in entries],
                    "metadata": {
                        "created_at": datetime.now(UTC).isoformat(),
                        "total_entries": len(entries),
                        "generated_by": "run_recommendation_baseline_calibration",
                        "notes": "SYNTHETIC — for structural testing only. Not for production calibration.",
                    },
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"Saved {len(entries)} synthetic entries to {path}")
        entries = load_recommendation_golden_set(path)

    if not entries:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
            production_blockers=["Golden set is empty. Add human-labeled recommendation entries."],
        )
        result.report = _format_report(result)
        return result

    has_labels = check_recommendation_labels_exist(entries)
    has_real_labels, synthetic_issues = check_recommendation_labels_are_real(entries)
    label_coverage = count_labeled_recommendations(entries)
    labeled_entry_count = label_coverage["total_entries_with_labels"]
    total_labels = label_coverage["total_recommendation_labels"]

    # If no real labels, block production immediately
    if not has_labels or not has_real_labels:
        msg = "No real human labels" if not has_real_labels else "No labels found"
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=len(entries),
            has_human_labels=has_labels,
            has_real_labels=has_real_labels,
            synthetic_label_issues=synthetic_issues,
            label_coverage=label_coverage,
            production_blockers=[f"{msg}. Synthetic labels cannot calibrate production ranking."],
        )
        result.report = _format_report(result)
        return result

    if labeled_entry_count < 3:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=len(entries),
            has_human_labels=has_labels,
            has_real_labels=has_real_labels,
            synthetic_label_issues=synthetic_issues,
            label_coverage=label_coverage,
            production_blockers=[
                f"Insufficient labeled entries ({labeled_entry_count}). Need at least {MIN_LABELED_ENTRIES}."
            ],
        )
        result.report = _format_report(result)
        return result

    # Evaluate weight candidates
    candidates = _evaluate_weight_candidates(entries, CANDIDATE_PRIORITY_WEIGHTS)
    best_idx = _select_best_candidate(candidates)

    best_weights = CANDIDATE_PRIORITY_WEIGHTS[0]
    all_predicted: list[float] = []
    all_human: list[float] = []
    ranking_metrics: RankingMetrics | None = None
    support_metrics: SupportMetrics | None = None
    correlation_metrics: ScoreCorrelationMetrics | None = None
    calibration_metrics: CalibrationErrorMetrics | None = None

    if best_idx is not None:
        best_weights = candidates[best_idx].weights

    (
        all_predicted,
        all_human,
        ranking_metrics,
        support_metrics,
        correlation_metrics,
        calibration_metrics,
    ) = _compute_entry_level_metrics(
        entries,
        best_weights,
    )

    uncertainties = _extract_uncertainties(
        entries,
        [m.get("nvidia_technology", "") for e in entries for m in e.nvidia_technology_mappings_snapshot],
    )

    # Calibrate thresholds and penalties
    production_threshold = None
    if len(all_predicted) >= 3:
        production_threshold = _calibrate_threshold_from_scores(all_predicted, percentile=5.0)

    uncertainty_penalty = None
    if len(all_predicted) >= 3 and len(uncertainties) >= 3:
        uncertainty_penalty = _calibrate_uncertainty_penalty_from_scores(
            all_predicted,
            all_human,
            uncertainties,
        )

    conf_threshold = _recommend_minimum_mapping_confidence(
        [float(m.get("mapping_confidence", 0.0)) for e in entries for m in e.nvidia_technology_mappings_snapshot],
    )

    min_ev_support = _recommend_minimum_evidence_support(entries)

    tech_coverage: dict[str, int] = label_coverage.get("technology_coverage", {})
    best_spearman = candidates[best_idx].spearman if best_idx is not None else None
    best_mae = candidates[best_idx].mae if best_idx is not None else None
    best_fp = candidates[best_idx].fp_rate if best_idx is not None else None

    prod_ready, blockers = _check_recommendation_production_ready(
        labeled_entry_count=labeled_entry_count,
        label_count=total_labels,
        has_real_labels=has_real_labels,
        synthetic_issues=synthetic_issues,
        coverage_by_tech=tech_coverage,
        spearman=best_spearman,
        mae=best_mae,
        fp_rate=best_fp,
    )

    status = "baseline_measured" if prod_ready else "baseline_measured_blocked"

    result = RecommendationCalibrationResult(
        calibration_status=status,
        production_allowed=prod_ready,
        golden_set_size=len(entries),
        has_human_labels=has_labels,
        has_real_labels=has_real_labels,
        synthetic_label_issues=synthetic_issues,
        label_coverage=label_coverage,
        candidate_results=candidates,
        best_candidate_index=best_idx,
        best_weights=best_weights,
        best_ranking_metrics=ranking_metrics,
        best_support_metrics=support_metrics,
        best_correlation_metrics=correlation_metrics,
        best_calibration_metrics=calibration_metrics,
        all_predicted_scores=all_predicted,
        all_human_labels=all_human,
        uncertainties=uncertainties,
        production_threshold=production_threshold,
        confidence_threshold=conf_threshold,
        uncertainty_penalty=uncertainty_penalty,
        minimum_mapping_confidence=conf_threshold,
        minimum_evidence_support=min_ev_support,
        production_blockers=blockers if not prod_ready else None,
    )
    result.report = _format_report(result)
    return result


# ---------------------------------------------------------------------------
# Registry record generation
# ---------------------------------------------------------------------------

REQUIRED_RECOMMENDATION_DECISIONS: list[str] = [
    "recommendation.priority_score_weights",
    "recommendation.production_threshold",
    "recommendation.confidence_threshold",
    "recommendation.uncertainty_penalty",
    "recommendation.minimum_mapping_confidence",
    "recommendation.minimum_evidence_support",
]


def make_recommendation_baseline_records(
    result: RecommendationCalibrationResult,
) -> list[DecisionCalibrationRecord]:
    base_value_origin = "src/evaluation/recommendation_baseline.py :: run_recommendation_baseline_calibration"
    eval_id = _generate_eval_id()

    is_insufficient = result.calibration_status == "baseline_dataset_insufficient"
    is_blocked = result.calibration_status == "baseline_measured_blocked"

    cal_status: CalibrationStatus
    if is_insufficient:
        cal_status = CalibrationStatus.UNCALIBRATED
    elif is_blocked or not result.production_allowed:
        cal_status = CalibrationStatus.UNCALIBRATED
    else:
        cal_status = CalibrationStatus.BASELINE_MEASURED

    cal_method = CalibrationMethod.GRID_SEARCH
    if is_insufficient:
        cal_method = CalibrationMethod.BASELINE_MEASUREMENT

    evidence_source_lines: list[str] = [
        f"Evaluator: {base_value_origin}",
        f"Eval run: {eval_id}",
        f"Golden set: {_GOLDEN_SET_PATH}",
        f"Entries: {result.golden_set_size}",
        f"Has real labels: {result.has_real_labels}",
        f"Calibration status: {result.calibration_status}",
    ]
    if result.best_candidate_index is not None and result.candidate_results:
        bc = result.candidate_results[result.best_candidate_index]
        evidence_source_lines.append(
            f"Best candidate: idx={result.best_candidate_index}, spearman={bc.spearman}, mae={bc.mae}, rmse={bc.rmse}"
        )
    if result.best_ranking_metrics:
        rm = result.best_ranking_metrics
        evidence_source_lines.append(
            f"MRR={rm.mrr}, precision@3={rm.precision_at_k.get(3) if rm.precision_at_k else None}, "
            f"recall@3={rm.recall_at_k.get(3) if rm.recall_at_k else None}"
        )
    if result.production_blockers:
        evidence_source_lines.append(f"Blockers: {'; '.join(result.production_blockers[:3])}")

    evidence_source = "\n".join(evidence_source_lines)

    # Report path
    _GOLDEN_SET_PATH.parent / f"report_recommendation_baseline_{eval_id}.txt"

    notes_template = (
        "Calibrated via recommendation_baseline_eval. "
        "Synthetic labels are NOT used for production calibration. "
        "Run `python -m src.evaluation.recommendation_baseline` to recalibrate with human labels."
    )

    now = datetime.now(UTC)

    records: list[DecisionCalibrationRecord] = []

    # --- 1. priority_score_weights ---
    if is_insufficient or is_blocked:
        current_value = None
    elif result.best_weights:
        current_value = result.best_weights
    else:
        current_value = None

    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.priority_score_weights",
            decision_name="Recommendation: Per-Feature Weights for priority_score",
            decision_type=DecisionType.WEIGHT,
            current_value=current_value,
            metric_name="recommendation_priority_score_weights",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=cal_method,
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nWeights: {result.best_weights if result.best_weights else 'None — insufficient data'}",
        )
    )

    # --- 2. production_threshold ---
    pt_value = None
    if result.production_threshold and result.production_threshold.get("threshold") is not None:
        pt_value = result.production_threshold["threshold"]
    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.production_threshold",
            decision_name="Recommendation: Minimum priority_score for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=pt_value,
            metric_name="recommendation_production_threshold",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=(CalibrationMethod.PERCENTILE_RULE if not is_insufficient else cal_method),
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nThreshold: {pt_value}",
        )
    )

    # --- 3. confidence_threshold ---
    ct_value = None
    if result.confidence_threshold and result.confidence_threshold.get("recommended_min") is not None:
        ct_value = result.confidence_threshold["recommended_min"]
    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.confidence_threshold",
            decision_name="Recommendation: Minimum mapping_confidence for Recommendation confidence",
            decision_type=DecisionType.THRESHOLD,
            current_value=ct_value,
            metric_name="recommendation_confidence_threshold",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=(CalibrationMethod.PERCENTILE_RULE if not is_insufficient else cal_method),
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nConfidence threshold: {ct_value}",
        )
    )

    # --- 4. uncertainty_penalty ---
    up_value = None
    if result.uncertainty_penalty and result.uncertainty_penalty.get("best_penalty") is not None:
        up_value = result.uncertainty_penalty["best_penalty"]
    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.uncertainty_penalty",
            decision_name="Recommendation: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=up_value,
            metric_name="recommendation_uncertainty_penalty",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=(CalibrationMethod.SENSITIVITY_ANALYSIS if not is_insufficient else cal_method),
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nUncertainty penalty: {up_value}",
        )
    )

    # --- 5. minimum_mapping_confidence ---
    mmc_value = None
    if result.minimum_mapping_confidence and result.minimum_mapping_confidence.get("recommended_min") is not None:
        mmc_value = result.minimum_mapping_confidence["recommended_min"]
    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_mapping_confidence",
            decision_name="Recommendation: Minimum mapping_confidence for Recommendation",
            decision_type=DecisionType.THRESHOLD,
            current_value=mmc_value,
            metric_name="recommendation_minimum_mapping_confidence",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=(CalibrationMethod.PERCENTILE_RULE if not is_insufficient else cal_method),
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nMin mapping confidence: {mmc_value}",
        )
    )

    # --- 6. minimum_evidence_support ---
    mes_value = None
    if result.minimum_evidence_support and result.minimum_evidence_support.get("recommended_min") is not None:
        mes_value = result.minimum_evidence_support["recommended_min"]
    records.append(
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_evidence_support",
            decision_name="Recommendation: Minimum Evidence Support Rate",
            decision_type=DecisionType.THRESHOLD,
            current_value=mes_value,
            metric_name="recommendation_minimum_evidence_support",
            value_origin=base_value_origin,
            calibration_status=cal_status,
            calibration_method=(CalibrationMethod.PERCENTILE_RULE if not is_insufficient else cal_method),
            production_allowed=result.production_allowed,
            evidence_source=evidence_source,
            owner="team-recommendation",
            last_calibrated_at=now if not is_insufficient else None,
            notes=f"{notes_template}\nMin evidence support: {mes_value}",
        )
    )

    return records


def _generate_eval_id() -> str:
    now = datetime.now(UTC)
    return f"rec-baseline-{now.strftime('%Y%m%d-%H%M%S')}"


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    check_only = "--check" in sys.argv

    result = run_recommendation_baseline_calibration()
    print(result.report)

    if result.production_allowed:
        print("\nSTATUS: PRODUCTION ALLOWED")
    else:
        print("\nSTATUS: PRODUCTION BLOCKED")
        if result.production_blockers:
            for b in result.production_blockers:
                print(f"  BLOCKER: {b}")

    records = make_recommendation_baseline_records(result)
    print(f"\nGenerated {len(records)} DecisionCalibrationRecords:")
    for r in records:
        print(
            f"  [{r.calibration_status.value}] {r.decision_id} = {r.current_value} "
            f"(production_allowed={r.production_allowed})"
        )

    errors = 0
    for r in records:
        if not r.evidence_source:
            print(f"ERROR: {r.decision_id} missing evidence_source")
            errors += 1
        if r.production_allowed and r.current_value is None:
            print(f"ERROR: {r.decision_id} production_allowed=True but current_value=None")
            errors += 1

    if check_only:
        sys.exit(1 if errors > 0 else 0)
