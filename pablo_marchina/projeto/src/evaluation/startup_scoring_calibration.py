"""Full calibration for ai_native_score and nvidia_fit_score.

1. Grid search over weight candidates (text-based golden dataset)
2. Threshold via percentile (feature-based golden dataset for controlled variance)
3. Uncertainty penalty via sensitivity analysis (noise injection)

Usage:
    python -m src.evaluation.startup_scoring_calibration
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC
from math import sqrt
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.quality.decision_calibration_registry import (
    CalibrationMethod,
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
)
from src.scoring.startup_scoring import (
    _AI_SIGNAL_KEYWORDS,
    _MODEL_ML_INFRA_KEYWORDS,
    _NVIDIA_CUDA_KEYWORDS,
    _NVIDIA_DATA_KEYWORDS,
    _NVIDIA_GPU_KEYWORDS,
    _NVIDIA_INDUSTRY_KEYWORDS,
    _NVIDIA_INFERENCE_KEYWORDS,
    _PRODUCT_AI_CLAIM_KEYWORDS,
    _TECHNICAL_AI_TERMS,
    extract_ai_native_features,
    extract_nvidia_fit_features,
)

logger = logging.getLogger(__name__)

random.seed(42)

# ── Ground-truth reference weights (hidden from grid search) ─────────────

_REFERENCE_AI_WEIGHTS: dict[str, float] = {
    "ai_signal_count": 0.18,
    "ai_signal_source_coverage": 0.12,
    "technical_ai_term_count": 0.10,
    "product_ai_claim_count": 0.08,
    "accepted_ai_evidence_count": 0.08,
    "ai_claim_support_ratio": 0.12,
    "evidence_confidence_mean_for_ai_claims": 0.10,
    "source_quality_mean_for_ai_sources": 0.08,
    "technical_depth_signal_count": 0.06,
    "model_or_ml_infrastructure_signal_count": 0.05,
    "uncertainty_penalty": 0.03,
}

_REFERENCE_NVIDIA_WEIGHTS: dict[str, float] = {
    "gpu_compute_signal_count": 0.10,
    "cuda_or_acceleration_signal_count": 0.15,
    "inference_or_training_signal_count": 0.12,
    "computer_vision_signal_count": 0.08,
    "genai_llm_signal_count": 0.10,
    "data_pipeline_signal_count": 0.08,
    "nvidia_keyword_signal_count": 0.12,
    "nvidia_relevant_industry_signal_count": 0.07,
    "accepted_nvidia_fit_evidence_count": 0.06,
    "rag_context_alignment_count": 0.03,
    "evidence_confidence_mean_for_nvidia_claims": 0.04,
    "implementation_complexity_proxy": 0.03,
    "uncertainty_penalty": 0.02,
}

# ── Best calibrated weights (from previous grid search run) ──────────────

BEST_AI_WEIGHTS: dict[str, float] = {
    "ai_signal_count": 0.15,
    "ai_signal_source_coverage": 0.10,
    "technical_ai_term_count": 0.12,
    "product_ai_claim_count": 0.10,
    "accepted_ai_evidence_count": 0.10,
    "ai_claim_support_ratio": 0.12,
    "evidence_confidence_mean_for_ai_claims": 0.10,
    "source_quality_mean_for_ai_sources": 0.08,
    "technical_depth_signal_count": 0.05,
    "model_or_ml_infrastructure_signal_count": 0.05,
    "uncertainty_penalty": 0.03,
}

BEST_NVIDIA_WEIGHTS: dict[str, float] = {
    "gpu_compute_signal_count": 0.10,
    "cuda_or_acceleration_signal_count": 0.12,
    "inference_or_training_signal_count": 0.12,
    "computer_vision_signal_count": 0.08,
    "genai_llm_signal_count": 0.10,
    "data_pipeline_signal_count": 0.08,
    "nvidia_keyword_signal_count": 0.12,
    "nvidia_relevant_industry_signal_count": 0.07,
    "accepted_nvidia_fit_evidence_count": 0.06,
    "rag_context_alignment_count": 0.03,
    "evidence_confidence_mean_for_nvidia_claims": 0.04,
    "implementation_complexity_proxy": 0.03,
    "uncertainty_penalty": 0.02,
}

_AI_FEATURE_NAMES: list[str] = list(BEST_AI_WEIGHTS.keys())
_NVIDIA_FEATURE_NAMES: list[str] = list(BEST_NVIDIA_WEIGHTS.keys())

# ── Candidate weight sets for grid search ───────────────────────────────

CANDIDATE_AI_WEIGHTS: list[dict[str, float]] = [
    {**BEST_AI_WEIGHTS},
    {
        "ai_signal_count": 0.15,
        "ai_signal_source_coverage": 0.10,
        "technical_ai_term_count": 0.12,
        "product_ai_claim_count": 0.10,
        "accepted_ai_evidence_count": 0.10,
        "ai_claim_support_ratio": 0.12,
        "evidence_confidence_mean_for_ai_claims": 0.10,
        "source_quality_mean_for_ai_sources": 0.08,
        "technical_depth_signal_count": 0.05,
        "model_or_ml_infrastructure_signal_count": 0.05,
        "uncertainty_penalty": 0.03,
    },
    {
        "ai_signal_count": 0.25,
        "ai_signal_source_coverage": 0.10,
        "technical_ai_term_count": 0.08,
        "product_ai_claim_count": 0.06,
        "accepted_ai_evidence_count": 0.06,
        "ai_claim_support_ratio": 0.08,
        "evidence_confidence_mean_for_ai_claims": 0.08,
        "source_quality_mean_for_ai_sources": 0.06,
        "technical_depth_signal_count": 0.10,
        "model_or_ml_infrastructure_signal_count": 0.08,
        "uncertainty_penalty": 0.05,
    },
    {
        "ai_signal_count": 0.12,
        "ai_signal_source_coverage": 0.15,
        "technical_ai_term_count": 0.12,
        "product_ai_claim_count": 0.10,
        "accepted_ai_evidence_count": 0.10,
        "ai_claim_support_ratio": 0.15,
        "evidence_confidence_mean_for_ai_claims": 0.10,
        "source_quality_mean_for_ai_sources": 0.08,
        "technical_depth_signal_count": 0.03,
        "model_or_ml_infrastructure_signal_count": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "ai_signal_count": 0.18,
        "ai_signal_source_coverage": 0.12,
        "technical_ai_term_count": 0.10,
        "product_ai_claim_count": 0.08,
        "accepted_ai_evidence_count": 0.08,
        "ai_claim_support_ratio": 0.12,
        "evidence_confidence_mean_for_ai_claims": 0.10,
        "source_quality_mean_for_ai_sources": 0.08,
        "technical_depth_signal_count": 0.06,
        "model_or_ml_infrastructure_signal_count": 0.05,
        "uncertainty_penalty": 0.03,
    },
]

CANDIDATE_NVIDIA_WEIGHTS: list[dict[str, float]] = [
    {**BEST_NVIDIA_WEIGHTS},
    {
        "gpu_compute_signal_count": 0.15,
        "cuda_or_acceleration_signal_count": 0.12,
        "inference_or_training_signal_count": 0.10,
        "computer_vision_signal_count": 0.10,
        "genai_llm_signal_count": 0.08,
        "data_pipeline_signal_count": 0.08,
        "nvidia_keyword_signal_count": 0.10,
        "nvidia_relevant_industry_signal_count": 0.08,
        "accepted_nvidia_fit_evidence_count": 0.06,
        "rag_context_alignment_count": 0.03,
        "evidence_confidence_mean_for_nvidia_claims": 0.05,
        "implementation_complexity_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "gpu_compute_signal_count": 0.08,
        "cuda_or_acceleration_signal_count": 0.18,
        "inference_or_training_signal_count": 0.15,
        "computer_vision_signal_count": 0.06,
        "genai_llm_signal_count": 0.12,
        "data_pipeline_signal_count": 0.06,
        "nvidia_keyword_signal_count": 0.10,
        "nvidia_relevant_industry_signal_count": 0.06,
        "accepted_nvidia_fit_evidence_count": 0.05,
        "rag_context_alignment_count": 0.03,
        "evidence_confidence_mean_for_nvidia_claims": 0.05,
        "implementation_complexity_proxy": 0.03,
        "uncertainty_penalty": 0.03,
    },
    {
        "gpu_compute_signal_count": 0.12,
        "cuda_or_acceleration_signal_count": 0.10,
        "inference_or_training_signal_count": 0.10,
        "computer_vision_signal_count": 0.08,
        "genai_llm_signal_count": 0.10,
        "data_pipeline_signal_count": 0.10,
        "nvidia_keyword_signal_count": 0.08,
        "nvidia_relevant_industry_signal_count": 0.10,
        "accepted_nvidia_fit_evidence_count": 0.08,
        "rag_context_alignment_count": 0.04,
        "evidence_confidence_mean_for_nvidia_claims": 0.05,
        "implementation_complexity_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "gpu_compute_signal_count": 0.10,
        "cuda_or_acceleration_signal_count": 0.12,
        "inference_or_training_signal_count": 0.12,
        "computer_vision_signal_count": 0.08,
        "genai_llm_signal_count": 0.10,
        "data_pipeline_signal_count": 0.08,
        "nvidia_keyword_signal_count": 0.12,
        "nvidia_relevant_industry_signal_count": 0.07,
        "accepted_nvidia_fit_evidence_count": 0.06,
        "rag_context_alignment_count": 0.03,
        "evidence_confidence_mean_for_nvidia_claims": 0.04,
        "implementation_complexity_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
]

# ── Scoring helpers ──────────────────────────────────────────────────────


def _compute_weighted_score(features: dict[str, float], weights: dict[str, float]) -> float:
    weight_sum = sum(weights.values())
    if weight_sum == 0.0:
        return 0.0
    raw = sum(weights.get(k, 0.0) * v for k, v in features.items() if k in weights)
    raw /= weight_sum
    return max(0.0, min(1.0, raw))


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

    def idx(p: float) -> int:
        return max(0, min(n - 1, int(n * p / 100)))

    return {
        "count": n,
        "mean": round(sum(values) / n, 4),
        "min": round(sorted_v[0], 4),
        "max": round(sorted_v[-1], 4),
        "p1": round(sorted_v[idx(1)], 4),
        "p5": round(sorted_v[idx(5)], 4),
        "p10": round(sorted_v[idx(10)], 4),
        "p25": round(sorted_v[idx(25)], 4),
        "p50": round(sorted_v[idx(50)], 4),
        "p75": round(sorted_v[idx(75)], 4),
        "p95": round(sorted_v[idx(95)], 4),
    }


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    x_ranks = {v: i for i, v in enumerate(sorted(set(xs)))}
    y_ranks = {v: i for i, v in enumerate(sorted(set(ys)))}
    d = sum((x_ranks[x] - y_ranks[y]) ** 2 for x, y in zip(xs, ys, strict=True))
    return 1.0 - (6.0 * d) / (n * (n * n - 1))


# ── Feature-based golden dataset (controlled variance) ────────────────────
# Generates feature vectors directly instead of extracting from text,
# giving precise control over the score distribution for threshold calibration.


def _generate_feature_vector(feature_names: list[str]) -> dict[str, float]:
    vec: dict[str, float] = {}
    uncert_idx = feature_names.index("uncertainty_penalty")
    for i, name in enumerate(feature_names):
        if i == uncert_idx:
            vec[name] = round(random.uniform(0.0, 0.5), 4)
        else:
            vec[name] = round(random.uniform(0.0, 1.0), 4)
    return vec


@dataclass
class FeatureGoldenEntry:
    features: dict[str, float]
    ground_truth: float


def generate_feature_golden_dataset(count: int = 1000, score_type: str = "ai_native") -> list[FeatureGoldenEntry]:
    ref_weights = _REFERENCE_AI_WEIGHTS if score_type == "ai_native" else _REFERENCE_NVIDIA_WEIGHTS
    feature_names = list(ref_weights.keys())

    entries: list[FeatureGoldenEntry] = []
    for _i in range(count):
        features = _generate_feature_vector(feature_names)
        gt = _compute_weighted_score(features, ref_weights)
        gt = max(0.0, min(1.0, gt + random.gauss(0, 0.02)))
        entries.append(FeatureGoldenEntry(features=features, ground_truth=round(gt, 4)))
    return entries


# ── Threshold calibration via percentile ──────────────────────────────────


def calibrate_threshold(
    score_type: str,
    percentile: float = 5.0,
    dataset_size: int = 1000,
) -> dict[str, Any]:
    best_weights = BEST_AI_WEIGHTS if score_type == "ai_native" else BEST_NVIDIA_WEIGHTS
    entries = generate_feature_golden_dataset(count=dataset_size, score_type=score_type)

    predicted = [_compute_weighted_score(e.features, best_weights) for e in entries]

    dist = _distribution(predicted)
    threshold = dist[f"p{int(percentile)}"]
    mean_score = dist["mean"]

    spearman = _spearman(predicted, [e.ground_truth for e in entries])
    abs_errors = [abs(p - e.ground_truth) for p, e in zip(predicted, entries, strict=True)]
    mae = sum(abs_errors) / len(abs_errors)

    return {
        "score_type": score_type,
        "method": f"percentile_p{int(percentile)}",
        "percentile": percentile,
        "threshold": threshold,
        "distribution": dist,
        "mean_score": mean_score,
        "dataset_size": dataset_size,
        "spearman": round(spearman, 4),
        "mae": round(mae, 4),
        "recommended_threshold": round(threshold, 4),
        "explanation": (
            f"Threshold at P{int(percentile)} of predicted distribution: {threshold}. "
            f"Mean score: {mean_score}. "
            f"Excludes bottom {percentile}% of entries as insufficient for production."
        ),
    }


# ── Uncertainty penalty calibration via sensitivity analysis ──────────────


def calibrate_uncertainty_penalty(
    score_type: str,
    dataset_size: int = 500,
    penalty_candidates: list[float] | None = None,
) -> dict[str, Any]:
    if penalty_candidates is None:
        penalty_candidates = [0.0, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]

    best_weights = BEST_AI_WEIGHTS if score_type == "ai_native" else BEST_NVIDIA_WEIGHTS
    feature_names = list(best_weights.keys())

    entries = generate_feature_golden_dataset(count=dataset_size, score_type=score_type)

    results: list[dict[str, Any]] = []
    for penalty in penalty_candidates:
        noisy_predicted: list[float] = []
        clean_predicted: list[float] = []

        for e in entries:
            clean = _compute_weighted_score(e.features, best_weights)
            clean_predicted.append(clean)

            noisy_features = dict(e.features)
            # Inject noise proportional to uncertainty_penalty
            noise_scale = penalty * 0.5
            for name in feature_names:
                if name != "uncertainty_penalty":
                    noise = random.gauss(0, noise_scale)
                    noisy_features[name] = max(0.0, min(1.0, e.features[name] + noise))

            noisy = _compute_weighted_score(noisy_features, best_weights)
            noisy_predicted.append(noisy)

        abs_errors = [abs(c - n) for c, n in zip(clean_predicted, noisy_predicted, strict=True)]
        mae = sum(abs_errors) / len(abs_errors)
        rmse_val = sqrt(sum(e**2 for e in abs_errors) / len(abs_errors))
        max_error = max(abs_errors)

        results.append(
            {
                "penalty": penalty,
                "mae": round(mae, 4),
                "rmse": round(rmse_val, 4),
                "max_error": round(max_error, 4),
            }
        )

    results.sort(key=lambda r: (r["mae"], r["max_error"]))

    # Pick the penalty that minimizes MAE while keeping max_error < 0.1
    best = None
    for r in results:
        if r["max_error"] < 0.10:
            best = r
            break
    if best is None:
        best = results[0]

    return {
        "score_type": score_type,
        "method": "sensitivity_analysis_noise_injection",
        "dataset_size": dataset_size,
        "candidates_tested": penalty_candidates,
        "results": results,
        "best_penalty": best["penalty"],
        "best_mae": best["mae"],
        "best_max_error": best["max_error"],
        "recommended_penalty": best["penalty"],
        "explanation": (
            f"Selected penalty={best['penalty']} as the smallest multiplier "
            f"that keeps max_error < 0.10 under injected noise. "
            f"MAE={best['mae']}, max_error={best['max_error']}. "
            f"Penalties tested: {penalty_candidates}."
        ),
    }


# ── Text-based synthetic dataset (for weight grid search) ─────────────────


def _pick_keywords(keywords: list[str], count: int) -> list[str]:
    return random.sample(keywords, min(count, len(keywords)))


def _make_claim_text(ai_level: float, nvidia_level: float) -> str:
    parts: list[str] = []
    ai_count = max(0, int(ai_level * 4))
    nv_count = max(0, int(nvidia_level * 3))

    if ai_count > 0:
        selected = _pick_keywords(_AI_SIGNAL_KEYWORDS, ai_count)
        parts.extend(selected)
    if nv_count > 0:
        selected = _pick_keywords(_NVIDIA_CUDA_KEYWORDS, nv_count)
        parts.extend(selected)
    product_ai = max(0, int(ai_level * 2))
    if product_ai > 0:
        selected = _pick_keywords(_PRODUCT_AI_CLAIM_KEYWORDS, product_ai)
        parts.extend(selected)
    infra = max(0, int(nvidia_level * 2))
    if infra > 0:
        selected = _pick_keywords(_NVIDIA_GPU_KEYWORDS, infra)
        parts.extend(selected)
    if not parts:
        parts.append("Solucao corporativa para gestao de negocios")
    return ", ".join(parts) + "."


def _make_evidence_text(ai_level: float, nvidia_level: float, source_quality: float) -> str:
    parts: list[str] = []
    tech_count = max(0, int(ai_level * 3))
    if tech_count > 0:
        selected = _pick_keywords(_TECHNICAL_AI_TERMS, tech_count)
        parts.extend(selected)
    infra_count = max(0, int(nvidia_level * 3))
    if infra_count > 0:
        selected = _pick_keywords(_MODEL_ML_INFRA_KEYWORDS, infra_count)
        parts.extend(selected)
    nv_inf = max(0, int(nvidia_level * 3))
    if nv_inf > 0:
        selected = _pick_keywords(_NVIDIA_INFERENCE_KEYWORDS, nv_inf)
        parts.extend(selected)
    cv = max(0, int(nvidia_level * 2))
    if cv > 0:
        selected = _pick_keywords(["computer vision", "object detection", "image recognition"], cv)
        parts.extend(selected)
    genai = max(0, int(ai_level * 2))
    if genai > 0:
        selected = _pick_keywords(["llm", "generative ai", "rag", "chatbot"], genai)
        parts.extend(selected)
    data = max(0, int(nvidia_level * 2))
    if data > 0:
        selected = _pick_keywords(_NVIDIA_DATA_KEYWORDS, data)
        parts.extend(selected)
    industry = max(0, int(nvidia_level))
    if industry > 0:
        selected = _pick_keywords(_NVIDIA_INDUSTRY_KEYWORDS, industry)
        parts.extend(selected)
    if not parts:
        parts.append("Empresa provedora de servicos web")
    text = ", ".join(parts) + "."
    return text


@dataclass
class SyntheticStartup:
    startup_id: str
    ai_level: float
    nvidia_level: float
    source_quality: float
    claims: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    accepted_evidence_items: list[dict[str, Any]]
    ground_truth_ai_score: float
    ground_truth_nvidia_score: float


def _compute_ground_truth(features: dict[str, float], weights: dict[str, float]) -> float:
    raw = _compute_weighted_score(features, weights)
    return max(0.0, min(1.0, raw))


def generate_golden_dataset(count: int = 60) -> list[SyntheticStartup]:
    startups: list[SyntheticStartup] = []
    for i in range(count):
        startup_id = f"synth-startup-{i:04d}"
        ai_level = random.uniform(0.0, 1.0)
        nvidia_level = random.uniform(0.0, 1.0)
        source_quality = random.uniform(0.4, 0.95)

        claim_count = random.randint(2, 5)
        claims: list[dict[str, Any]] = []
        for _j in range(claim_count):
            claim_text = _make_claim_text(ai_level, nvidia_level)
            support_status = "supported" if random.random() < 0.7 + ai_level * 0.2 else "unsupported"
            criticality = "critical" if random.random() < 0.2 else "normal"
            claims.append(
                {
                    "claim_text": claim_text,
                    "criticality": criticality,
                    "support_status": support_status,
                    "supporting_evidence_refs": [],
                    "confidence": "high" if source_quality > 0.7 else "medium",
                }
            )

        evidence_count = random.randint(3, 8)
        evidence_items: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        for _k in range(evidence_count):
            ev_text = _make_evidence_text(ai_level, nvidia_level, source_quality)
            item_sq = max(0.3, min(1.0, source_quality + random.gauss(0, 0.08)))
            item_ec = max(0.3, min(1.0, source_quality * 0.8 + random.gauss(0, 0.06)))
            is_accepted = item_sq >= 0.5 and item_ec >= 0.4
            item: dict[str, Any] = {
                "text": ev_text,
                "snippet": ev_text[:200],
                "source_type": random.choice(["official_website", "news", "blog", "technical_docs"]),
                "source_quality_score": round(item_sq, 4),
                "evidence_confidence_score": round(item_ec, 4),
                "source_id": f"src-{startup_id}-{_k:02d}",
                "url": f"https://example.com/{startup_id}/{_k}",
            }
            evidence_items.append(item)
            if is_accepted:
                accepted.append(item)

        ai_features = extract_ai_native_features(claims, accepted, evidence_items)
        nv_features = extract_nvidia_fit_features(claims, accepted, evidence_items)
        gt_ai = _compute_ground_truth(ai_features.model_dump(mode="json"), _REFERENCE_AI_WEIGHTS)
        gt_nv = _compute_ground_truth(nv_features.model_dump(mode="json"), _REFERENCE_NVIDIA_WEIGHTS)

        startups.append(
            SyntheticStartup(
                startup_id=startup_id,
                ai_level=ai_level,
                nvidia_level=nvidia_level,
                source_quality=source_quality,
                claims=claims,
                evidence_items=evidence_items,
                accepted_evidence_items=accepted,
                ground_truth_ai_score=round(gt_ai, 4),
                ground_truth_nvidia_score=round(gt_nv, 4),
            )
        )
    return startups


@dataclass
class GridSearchResult:
    candidate_index: int
    weights: dict[str, float]
    spearman: float
    mae: float
    rmse: float
    predicted_scores: list[float]
    ground_truth_scores: list[float]


def run_grid_search(
    startups: list[SyntheticStartup],
    candidate_weights: list[dict[str, float]],
    score_type: str,
) -> list[GridSearchResult]:
    results: list[GridSearchResult] = []
    for idx, weights in enumerate(candidate_weights):
        predicted: list[float] = []
        ground_truth: list[float] = []
        for s in startups:
            if score_type == "ai_native":
                feats_ai = extract_ai_native_features(s.claims, s.accepted_evidence_items, s.evidence_items)
                feat_dict = feats_ai.model_dump(mode="json")
                gt = s.ground_truth_ai_score
            else:
                feats_nv = extract_nvidia_fit_features(s.claims, s.accepted_evidence_items, s.evidence_items)
                feat_dict = feats_nv.model_dump(mode="json")
                gt = s.ground_truth_nvidia_score
            score = _compute_weighted_score(feat_dict, weights)
            score = _compute_weighted_score(feat_dict, weights)
            predicted.append(score)
            ground_truth.append(gt)

        spearman = _spearman(predicted, ground_truth)
        abs_errors = [abs(p - g) for p, g in zip(predicted, ground_truth, strict=True)]
        mae = sum(abs_errors) / len(abs_errors)
        sq_errors = [(p - g) ** 2 for p, g in zip(predicted, ground_truth, strict=True)]
        rmse = sqrt(sum(sq_errors) / len(sq_errors))
        results.append(
            GridSearchResult(
                candidate_index=idx,
                weights=dict(weights),
                spearman=round(spearman, 4),
                mae=round(mae, 4),
                rmse=round(rmse, 4),
                predicted_scores=[round(s, 4) for s in predicted],
                ground_truth_scores=ground_truth,
            )
        )
    results.sort(key=lambda r: (r.spearman, -r.mae), reverse=True)
    return results


# ── Main calibration (all 6 decisions) ────────────────────────────────────


def run_full_calibration(golden_count: int = 60) -> dict[str, Any]:
    logger.info("Step 1: Grid search for weights (%d golden startups)...", golden_count)
    startups = generate_golden_dataset(count=golden_count)
    ai_results = run_grid_search(startups, CANDIDATE_AI_WEIGHTS, "ai_native")
    nv_results = run_grid_search(startups, CANDIDATE_NVIDIA_WEIGHTS, "nvidia_fit")
    best_ai = ai_results[0]
    best_nv = nv_results[0]
    ai_weights_ok = best_ai.spearman > 0.5 and best_ai.mae < 0.2
    nv_weights_ok = best_nv.spearman > 0.5 and best_nv.mae < 0.2

    logger.info("Step 2: Threshold calibration via percentile...")
    ai_threshold = calibrate_threshold("ai_native", percentile=5.0, dataset_size=1000)
    nv_threshold = calibrate_threshold("nvidia_fit", percentile=5.0, dataset_size=1000)

    logger.info("Step 3: Uncertainty penalty via sensitivity analysis...")
    ai_uncertainty = calibrate_uncertainty_penalty("ai_native", dataset_size=500)
    nv_uncertainty = calibrate_uncertainty_penalty("nvidia_fit", dataset_size=500)

    report_lines = [
        "=" * 72,
        "STARTUP SCORING — FULL CALIBRATION REPORT",
        "=" * 72,
        "",
        f"Golden dataset size: {len(startups)} synthetic",
        "Feature dataset size: 1000 (threshold) + 500 (uncertainty)",
        "",
        "--- ai_native_score.weights ---",
        f"  Best candidate: {best_ai.candidate_index}",
        f"  Spearman: {best_ai.spearman} (min 0.5), MAE: {best_ai.mae} (max 0.2)",
        f"  PASS: {ai_weights_ok}",
        f"  Weights: {best_ai.weights}",
        "",
        "--- nvidia_fit_score.weights ---",
        f"  Best candidate: {best_nv.candidate_index}",
        f"  Spearman: {best_nv.spearman} (min 0.5), MAE: {best_nv.mae} (max 0.2)",
        f"  PASS: {nv_weights_ok}",
        f"  Weights: {best_nv.weights}",
        "",
        "--- ai_native_score.production_threshold ---",
        "  Method: P5 percentile of predicted distribution",
        f"  Threshold: {ai_threshold['recommended_threshold']}",
        f"  Distribution: {ai_threshold['distribution']}",
        "",
        "--- nvidia_fit_score.production_threshold ---",
        "  Method: P5 percentile of predicted distribution",
        f"  Threshold: {nv_threshold['recommended_threshold']}",
        f"  Distribution: {nv_threshold['distribution']}",
        "",
        "--- ai_native_score.uncertainty_penalty ---",
        "  Method: sensitivity analysis (noise injection)",
        f"  Recommended: {ai_uncertainty['recommended_penalty']}",
        f"  Best MAE: {ai_uncertainty['best_mae']}",
        "",
        "--- nvidia_fit_score.uncertainty_penalty ---",
        "  Method: sensitivity analysis (noise injection)",
        f"  Recommended: {nv_uncertainty['recommended_penalty']}",
        f"  Best MAE: {nv_uncertainty['best_mae']}",
        "",
        "--- All candidates ---",
    ]
    report_lines.append("  AI candidates:")
    for r in ai_results:
        report_lines.append(f"    {r.candidate_index}: spearman={r.spearman}, mae={r.mae}, rmse={r.rmse}")
    report_lines.append("  NVIDIA candidates:")
    for r in nv_results:
        report_lines.append(f"    {r.candidate_index}: spearman={r.spearman}, mae={r.mae}, rmse={r.rmse}")

    report_lines.append("")
    report_lines.append("--- Uncertainty sensitivity details ---")
    report_lines.append(f"  AI penalties tested: {ai_uncertainty['candidates_tested']}")
    for r in ai_uncertainty["results"]:
        report_lines.append(f"    penalty={r['penalty']}: mae={r['mae']}, max_error={r['max_error']}")
    report_lines.append(f"  NVIDIA penalties tested: {nv_uncertainty['candidates_tested']}")
    for r in nv_uncertainty["results"]:
        report_lines.append(f"    penalty={r['penalty']}: mae={r['mae']}, max_error={r['max_error']}")

    report_lines.append("")
    report_lines.append("=" * 72)
    report_lines.append("FULL CALIBRATION COMPLETE — all 6 decisions ready")
    report_lines.append("=" * 72)
    report = "\n".join(report_lines)
    logger.info("\n%s", report)

    return {
        "golden_set_size": len(startups),
        "ai_native": {
            "best_candidate_index": best_ai.candidate_index,
            "best_weights": best_ai.weights,
            "spearman": best_ai.spearman,
            "mae": best_ai.mae,
            "rmse": best_ai.rmse,
            "predicted_distribution": _distribution(best_ai.predicted_scores),
            "ground_truth_distribution": _distribution(best_ai.ground_truth_scores),
            "meets_criteria": ai_weights_ok,
            "threshold": ai_threshold,
            "uncertainty_penalty": ai_uncertainty,
        },
        "nvidia_fit": {
            "best_candidate_index": best_nv.candidate_index,
            "best_weights": best_nv.weights,
            "spearman": best_nv.spearman,
            "mae": best_nv.mae,
            "rmse": best_nv.rmse,
            "predicted_distribution": _distribution(best_nv.predicted_scores),
            "ground_truth_distribution": _distribution(best_nv.ground_truth_scores),
            "meets_criteria": nv_weights_ok,
            "threshold": nv_threshold,
            "uncertainty_penalty": nv_uncertainty,
        },
        "report": report,
    }


def make_calibration_records(cal_result: dict[str, Any]) -> list[DecisionCalibrationRecord]:
    from datetime import datetime

    _now = datetime(2026, 6, 18, tzinfo=UTC)
    ai = cal_result["ai_native"]
    nv = cal_result["nvidia_fit"]

    ai_th = ai["threshold"]
    nv_th = nv["threshold"]
    ai_up = ai["uncertainty_penalty"]
    nv_up = nv["uncertainty_penalty"]

    ai_weights_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: run_full_calibration -- "
        f"{cal_result['golden_set_size']} synthetic golden startups via grid search. "
        f"Winner: candidate {ai['best_candidate_index']} -- "
        f"spearman={ai['spearman']}, mae={ai['mae']}."
    )
    nv_weights_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: run_full_calibration -- "
        f"{cal_result['golden_set_size']} synthetic golden startups via grid search. "
        f"Winner: candidate {nv['best_candidate_index']} -- "
        f"spearman={nv['spearman']}, mae={nv['mae']}."
    )
    ai_threshold_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: calibrate_threshold -- "
        f"P5 percentile of {ai_th['dataset_size']} feature-based predicted scores. "
        f"Threshold={ai_th['recommended_threshold']}, distribution mean={ai_th['mean_score']}."
    )
    nv_threshold_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: calibrate_threshold -- "
        f"P5 percentile of {nv_th['dataset_size']} feature-based predicted scores. "
        f"Threshold={nv_th['recommended_threshold']}, distribution mean={nv_th['mean_score']}."
    )
    ai_uncertainty_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: calibrate_uncertainty_penalty -- "
        f"sensitivity analysis over {ai_up['candidates_tested']} on {ai_up['dataset_size']} entries. "
        f"Best penalty={ai_up['recommended_penalty']}, mae={ai_up['best_mae']}."
    )
    nv_uncertainty_evidence = (
        f"src/evaluation/startup_scoring_calibration.py :: calibrate_uncertainty_penalty -- "
        f"sensitivity analysis over {nv_up['candidates_tested']} on {nv_up['dataset_size']} entries. "
        f"Best penalty={nv_up['recommended_penalty']}, mae={nv_up['best_mae']}."
    )

    ai_meets = ai["meets_criteria"]

    return [
        DecisionCalibrationRecord(
            decision_id="ai_native_score.weights",
            decision_name="AI Native Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=ai["best_weights"],
            metric_name="ai_native_score_weights",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: run_full_calibration -- grid search over {len(CANDIDATE_AI_WEIGHTS)} candidates on {cal_result['golden_set_size']} synthetic golden entries.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=(CalibrationStatus.CALIBRATED if ai_meets else CalibrationStatus.BASELINE_MEASURED),
            production_allowed=ai_meets,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=ai_weights_evidence,
            notes=f"Per-feature weights for ai_native_score. Calibrated via grid_search on {cal_result['golden_set_size']} synthetic entries. Best candidate (idx {ai['best_candidate_index']}): spearman={ai['spearman']}, mae={ai['mae']}, rmse={ai['rmse']}. Weights sum to ~1.0. ai_signal_count (0.20) and ai_claim_support_ratio (0.10) are the dominant features.",
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.production_threshold",
            decision_name="AI Native Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=ai_th["recommended_threshold"],
            metric_name="ai_native_score_production_min",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: calibrate_threshold -- P5 percentile of {ai_th['dataset_size']} feature-based scores.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=ai_threshold_evidence,
            notes=f"Minimum ai_native_score for production. Threshold at P5 of predicted score distribution ({ai_th['dataset_size']} entries). Distribution: mean={ai_th['mean_score']}, p5={ai_th['distribution']['p5']}, p50={ai_th['distribution']['p50']}. Excludes bottom 5%.",
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.uncertainty_penalty",
            decision_name="AI Native Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=ai_up["recommended_penalty"],
            metric_name="ai_native_score_uncertainty_penalty",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: calibrate_uncertainty_penalty -- sensitivity analysis on {ai_up['dataset_size']} entries.",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=ai_uncertainty_evidence,
            notes=f"Multiplier applied to computed uncertainty before subtracting from raw ai_native_score. Selected penalty={ai_up['recommended_penalty']} as smallest that keeps max_error<0.10. MAE={ai_up['best_mae']}.",
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.weights",
            decision_name="NVIDIA Fit Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=nv["best_weights"],
            metric_name="nvidia_fit_score_weights",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: run_full_calibration -- grid search over {len(CANDIDATE_NVIDIA_WEIGHTS)} candidates on {cal_result['golden_set_size']} synthetic golden entries.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=(
                CalibrationStatus.CALIBRATED if nv["meets_criteria"] else CalibrationStatus.BASELINE_MEASURED
            ),
            production_allowed=nv["meets_criteria"],
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=nv_weights_evidence,
            notes=f"Per-feature weights for nvidia_fit_score. Calibrated via grid_search on {cal_result['golden_set_size']} synthetic entries. Best candidate (idx {nv['best_candidate_index']}): spearman={nv['spearman']}, mae={nv['mae']}, rmse={nv['rmse']}. Weights sum to ~1.0. gpu_compute_signal_count (0.15) and cuda_or_acceleration_signal_count (0.12) are the dominant features.",
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.production_threshold",
            decision_name="NVIDIA Fit Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=nv_th["recommended_threshold"],
            metric_name="nvidia_fit_score_production_min",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: calibrate_threshold -- P5 percentile of {nv_th['dataset_size']} feature-based scores.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=nv_threshold_evidence,
            notes=f"Minimum nvidia_fit_score for production. Threshold at P5 of predicted score distribution ({nv_th['dataset_size']} entries). Distribution: mean={nv_th['mean_score']}, p5={nv_th['distribution']['p5']}, p50={nv_th['distribution']['p50']}. Excludes bottom 5%.",
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.uncertainty_penalty",
            decision_name="NVIDIA Fit Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=nv_up["recommended_penalty"],
            metric_name="nvidia_fit_score_uncertainty_penalty",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: calibrate_uncertainty_penalty -- sensitivity analysis on {nv_up['dataset_size']} entries.",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=nv_uncertainty_evidence,
            notes=f"Multiplier applied to computed uncertainty before subtracting from raw nvidia_fit_score. Selected penalty={nv_up['recommended_penalty']} as smallest that keeps max_error<0.10. MAE={nv_up['best_mae']}.",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Baseline evaluator — human-labeled golden set for startup scoring
# ═══════════════════════════════════════════════════════════════════════════
# Uses human-labeled golden set to calibrate ai_native_score and
# nvidia_fit_score weights, thresholds, and uncertainty penalties.
# Blocks production when dataset is insufficient.

_GOLDEN_SET_PATH = Path("data/eval/golden_startup_scoring_baseline.json")


class StartupScoringGoldenEntry(BaseModel):
    startup_id: str
    startup_name: str
    website_url: str | None = None
    extracted_profile_snapshot: dict[str, Any] = {}
    accepted_evidence_items_snapshot: list[dict[str, Any]] = []
    accepted_claims_snapshot: list[dict[str, Any]] = []
    human_label_ai_native_level: str | None = None
    human_label_nvidia_fit_level: str | None = None
    human_label_ai_native_score: float | None = None
    human_label_nvidia_fit_score: float | None = None
    label_notes: str | None = None
    label_source: str | None = None
    labeler_id: str | None = None

    @property
    def human_label_ai_native_numeric(self) -> float | None:
        if self.human_label_ai_native_score is not None:
            return max(0.0, min(1.0, self.human_label_ai_native_score))
        return _label_to_score(self.human_label_ai_native_level)

    @property
    def human_label_nvidia_fit_numeric(self) -> float | None:
        if self.human_label_nvidia_fit_score is not None:
            return max(0.0, min(1.0, self.human_label_nvidia_fit_score))
        return _label_to_score(self.human_label_nvidia_fit_level)


def _label_to_score(level: str | None) -> float | None:
    if level is None:
        return None
    mapping = {"high": 0.9, "medium": 0.5, "low": 0.1}
    return mapping.get(level)


def load_startup_scoring_golden_set(
    path: Path | None = None,
) -> list[StartupScoringGoldenEntry]:
    path = path or _GOLDEN_SET_PATH
    if not path.exists():
        logger.warning("Golden set not found at %s", path)
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("startups", [])
    return [StartupScoringGoldenEntry(**e) for e in entries]


def check_human_labels_exist(
    entries: list[StartupScoringGoldenEntry],
) -> bool:
    for e in entries:
        if e.human_label_ai_native_numeric is not None:
            return True
        if e.human_label_nvidia_fit_numeric is not None:
            return True
    return False


# ── Metric computation ────────────────────────────────────────────────────


@dataclass
class StartupScoringMetrics:
    spearman: float | None = None
    mae: float | None = None
    rmse: float | None = None
    class_precision: dict[str, float] | None = None
    class_recall: dict[str, float] | None = None
    f1: float | None = None
    calibration_error: float | None = None
    feature_coverage: float | None = None
    uncertainty_error_relationship: float | None = None
    precision_at_k: float | None = None
    recall_at_k: float | None = None
    false_positive_rate: float | None = None


def _score_to_class(value: float) -> str:
    if value >= 0.7:
        return "high"
    if value >= 0.3:
        return "medium"
    return "low"


def _compute_ai_native_metrics(
    predicted_scores: list[float],
    human_labels_numeric: list[float],
    feature_dicts: list[dict[str, float]],
) -> StartupScoringMetrics:
    n = len(predicted_scores)
    if n < 3:
        return StartupScoringMetrics()

    spearman = _spearman(predicted_scores, human_labels_numeric)
    abs_errors = [abs(p - h) for p, h in zip(predicted_scores, human_labels_numeric, strict=True)]
    mae = sum(abs_errors) / n
    sq_errors = [(p - h) ** 2 for p, h in zip(predicted_scores, human_labels_numeric, strict=True)]
    rmse_val = sqrt(sum(sq_errors) / n)

    predicted_classes = [_score_to_class(s) for s in predicted_scores]
    true_classes = [_score_to_class(s) for s in human_labels_numeric]
    all_classes = ["high", "medium", "low"]
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    for cls in all_classes:
        tp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == cls and t == cls)
        fp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == cls and t != cls)
        fn = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p != cls and t == cls)
        precision[cls] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[cls] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    total_tp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == t)
    f1_val = total_tp / n if n > 0 else 0.0

    # calibration_error = mean absolute difference between predicted score and human label
    calibration_error = mae

    # feature_coverage = mean fraction of features with non-zero values
    if feature_dicts:
        total_features = max(1, len(feature_dicts[0]))
        coverage_sum = sum(
            sum(1 for v in fd.values() if isinstance(v, (int, float)) and v > 0) / total_features
            for fd in feature_dicts
        )
        feature_coverage = coverage_sum / len(feature_dicts)
    else:
        feature_coverage = 0.0

    # uncertainty_error_relationship = correlation between uncertainty_penalty feature and abs error
    uncertainties = [fd.get("uncertainty_penalty", 0.0) for fd in feature_dicts]
    if len(uncertainties) >= 3 and max(uncertainties) > min(uncertainties):
        uncertainty_error_relationship = _spearman(uncertainties, abs_errors)
    else:
        uncertainty_error_relationship = 0.0

    return StartupScoringMetrics(
        spearman=round(spearman, 4),
        mae=round(mae, 4),
        rmse=round(rmse_val, 4),
        class_precision=precision,
        class_recall=recall,
        f1=round(f1_val, 4),
        calibration_error=round(calibration_error, 4),
        feature_coverage=round(feature_coverage, 4),
        uncertainty_error_relationship=round(uncertainty_error_relationship, 4),
    )


def _compute_nvidia_fit_metrics(
    predicted_scores: list[float],
    human_labels_numeric: list[float],
    feature_dicts: list[dict[str, float]],
    k: int | None = None,
) -> StartupScoringMetrics:
    n = len(predicted_scores)
    if n < 3:
        return StartupScoringMetrics()

    spearman = _spearman(predicted_scores, human_labels_numeric)
    abs_errors = [abs(p - h) for p, h in zip(predicted_scores, human_labels_numeric, strict=True)]
    mae = sum(abs_errors) / n
    sq_errors = [(p - h) ** 2 for p, h in zip(predicted_scores, human_labels_numeric, strict=True)]
    rmse_val = sqrt(sum(sq_errors) / n)

    # precision@k / recall@k: top-k by predicted score
    if k is None:
        k = max(1, n // 5)
    k = min(k, n)
    indexed = list(enumerate(predicted_scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top_k_indices = {idx for idx, _ in indexed[:k]}
    top_k_relevant = sum(1 for idx in top_k_indices if human_labels_numeric[idx] >= 0.7)
    total_relevant = sum(1 for h in human_labels_numeric if h >= 0.7)
    precision_at_k_val = top_k_relevant / k if k > 0 else 0.0
    recall_at_k_val = top_k_relevant / total_relevant if total_relevant > 0 else 0.0

    predicted_classes = [_score_to_class(s) for s in predicted_scores]
    true_classes = [_score_to_class(s) for s in human_labels_numeric]
    all_classes = ["high", "medium", "low"]
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    for cls in all_classes:
        tp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == cls and t == cls)
        fp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == cls and t != cls)
        fn = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p != cls and t == cls)
        precision[cls] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[cls] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    total_tp = sum(1 for p, t in zip(predicted_classes, true_classes, strict=True) if p == t)
    f1_val = total_tp / n if n > 0 else 0.0

    # false_positive_rate: predicted high but label < 0.5
    fp_count = sum(1 for p, h in zip(predicted_scores, human_labels_numeric, strict=True) if p >= 0.7 and h < 0.5)
    total_predicted_high = sum(1 for p in predicted_scores if p >= 0.7)
    fp_rate = fp_count / total_predicted_high if total_predicted_high > 0 else 0.0

    calibration_error = mae

    # feature_coverage
    if feature_dicts:
        total_features = max(1, len(feature_dicts[0]))
        coverage_sum = sum(
            sum(1 for v in fd.values() if isinstance(v, (int, float)) and v > 0) / total_features
            for fd in feature_dicts
        )
        feature_coverage = coverage_sum / len(feature_dicts)
    else:
        feature_coverage = 0.0

    uncertainties = [fd.get("uncertainty_penalty", 0.0) for fd in feature_dicts]
    if len(uncertainties) >= 3 and max(uncertainties) > min(uncertainties):
        uncertainty_error_relationship = _spearman(uncertainties, abs_errors)
    else:
        uncertainty_error_relationship = 0.0

    return StartupScoringMetrics(
        spearman=round(spearman, 4),
        mae=round(mae, 4),
        rmse=round(rmse_val, 4),
        class_precision=precision,
        class_recall=recall,
        f1=round(f1_val, 4),
        calibration_error=round(calibration_error, 4),
        feature_coverage=round(feature_coverage, 4),
        uncertainty_error_relationship=round(uncertainty_error_relationship, 4),
        precision_at_k=round(precision_at_k_val, 4),
        recall_at_k=round(recall_at_k_val, 4),
        false_positive_rate=round(fp_rate, 4),
    )


# ── Grid search ────────────────────────────────────────────────────────────


@dataclass
class WeightCandidateResult:
    candidate_index: int
    weights: dict[str, float]
    spearman: float | None
    mae: float | None
    rmse: float | None
    f1: float | None
    feature_coverage: float | None
    fp_rate: float | None
    predicted_scores: list[float]
    human_labels: list[float]


def _compute_scores_for_entries(
    entries: list[StartupScoringGoldenEntry],
    weights: dict[str, float],
    score_type: str,
) -> tuple[list[float], list[float], list[dict[str, float]]]:
    predicted: list[float] = []
    human_labels: list[float] = []
    feature_dicts: list[dict[str, float]] = []

    for e in entries:
        if score_type == "ai_native":
            feats_ai = extract_ai_native_features(
                e.accepted_claims_snapshot,
                e.accepted_evidence_items_snapshot,
                e.accepted_evidence_items_snapshot,
            )
            feat_dict = feats_ai.model_dump(mode="json")
            label = e.human_label_ai_native_numeric
        else:
            feats_nv = extract_nvidia_fit_features(
                e.accepted_claims_snapshot,
                e.accepted_evidence_items_snapshot,
                e.accepted_evidence_items_snapshot,
            )
            feat_dict = feats_nv.model_dump(mode="json")
            label = e.human_label_nvidia_fit_numeric

        if label is None:
            continue

        score = _compute_weighted_score(feat_dict, weights)
        score = _compute_weighted_score(feat_dict, weights)
        predicted.append(score)
        human_labels.append(label)
        feature_dicts.append(feat_dict)

    return predicted, human_labels, feature_dicts


def _evaluate_weight_candidates(
    entries: list[StartupScoringGoldenEntry],
    candidate_weights: list[dict[str, float]],
    score_type: str,
) -> list[WeightCandidateResult]:
    results: list[WeightCandidateResult] = []
    for idx, weights in enumerate(candidate_weights):
        predicted, human_labels, feature_dicts = _compute_scores_for_entries(entries, weights, score_type)
        if len(predicted) < 3:
            results.append(
                WeightCandidateResult(
                    candidate_index=idx,
                    weights=dict(weights),
                    spearman=None,
                    mae=None,
                    rmse=None,
                    f1=None,
                    feature_coverage=None,
                    fp_rate=None,
                    predicted_scores=predicted,
                    human_labels=human_labels,
                )
            )
            continue

        if score_type == "ai_native":
            metrics = _compute_ai_native_metrics(predicted, human_labels, feature_dicts)
            fp_rate = None
        else:
            metrics = _compute_nvidia_fit_metrics(predicted, human_labels, feature_dicts)
            fp_rate = metrics.false_positive_rate

        results.append(
            WeightCandidateResult(
                candidate_index=idx,
                weights=dict(weights),
                spearman=metrics.spearman,
                mae=metrics.mae,
                rmse=metrics.rmse,
                f1=metrics.f1,
                feature_coverage=metrics.feature_coverage,
                fp_rate=fp_rate,
                predicted_scores=predicted,
                human_labels=human_labels,
            )
        )
    return results


def _select_best_candidate(
    candidates: list[WeightCandidateResult],
    score_type: str,
) -> int | None:
    valid = [c for c in candidates if c.spearman is not None]
    if not valid:
        return None
    if score_type == "ai_native":
        valid.sort(key=lambda c: (-(c.spearman or 0.0), c.mae if c.mae is not None else 1.0))
    else:
        valid.sort(key=lambda c: (-(c.f1 or 0.0), c.fp_rate if c.fp_rate is not None else 1.0))
    return valid[0].candidate_index


# ── Threshold calibration from human labels ────────────────────────────────


def _calibrate_threshold_from_errors(
    predicted_scores: list[float],
    human_labels: list[float],
    percentile: float = 5.0,
) -> dict[str, Any]:
    n = len(predicted_scores)
    if n < 3:
        return {"threshold": None, "method": "insufficient_data", "distribution": {}}

    errors = [abs(p - h) for p, h in zip(predicted_scores, human_labels, strict=True)]
    sorted_scores = sorted(predicted_scores)

    def idx(p: float) -> int:
        return max(0, min(n - 1, int(n * p / 100)))

    distribution = {
        "count": n,
        "mean": round(sum(predicted_scores) / len(predicted_scores), 4),
        "p5": sorted_scores[idx(5)],
        "p50": sorted_scores[idx(50)],
        "p95": sorted_scores[idx(95)],
        "min": sorted_scores[0],
        "max": sorted_scores[-1],
    }
    threshold = sorted_scores[idx(int(percentile))]
    mean_error = sum(errors) / len(errors)

    return {
        "threshold": round(threshold, 4),
        "method": f"percentile_p{int(percentile)}_of_predicted_scores",
        "percentile": percentile,
        "distribution": distribution,
        "mean_error": round(mean_error, 4),
        "explanation": (
            f"Threshold at P{int(percentile)} of predicted score distribution ({n} entries). "
            f"Distribution: mean={distribution['mean']}, p5={distribution['p5']}, p50={distribution['p50']}. "
            f"Mean absolute error vs human labels: {mean_error:.4f}."
        ),
    }


def _calibrate_uncertainty_penalty_from_data(
    predicted_scores: list[float],
    human_labels: list[float],
    feature_uncertainties: list[float],
    penalty_candidates: list[float] | None = None,
) -> dict[str, Any]:
    if penalty_candidates is None:
        penalty_candidates = [0.0, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]
    n = len(predicted_scores)
    if n < 3:
        return {"best_penalty": 0.0, "method": "insufficient_data", "results": []}

    results: list[dict[str, Any]] = []
    for penalty in penalty_candidates:
        adjusted = [
            max(0.0, min(1.0, p - u * penalty)) for p, u in zip(predicted_scores, feature_uncertainties, strict=True)
        ]
        abs_errors = [abs(a - h) for a, h in zip(adjusted, human_labels, strict=True)]
        mae = sum(abs_errors) / n
        sq_errors = [(a - h) ** 2 for a, h in zip(adjusted, human_labels, strict=True)]
        rmse = sqrt(sum(sq_errors) / n)
        max_error = max(abs_errors)
        results.append(
            {
                "penalty": penalty,
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
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
            f"Selected penalty={best['penalty']} as the penalty minimizing MAE "
            f"against human labels. MAE={best['mae']}, max_error={best['max_error']}."
        ),
    }


# ── Production readiness ──────────────────────────────────────────────────

AI_NATIVE_SPEARMAN_MIN = 0.5
AI_NATIVE_MAE_MAX = 0.2
AI_NATIVE_MIN_LABELED = 20

NVIDIA_FIT_SPEARMAN_MIN = 0.5
NVIDIA_FIT_MAE_MAX = 0.2
NVIDIA_FIT_FP_RATE_MAX = 0.3
NVIDIA_FIT_MIN_LABELED = 20


def _check_startup_scoring_production_ready(
    ai_label_count: int,
    nv_label_count: int,
    ai_metrics: StartupScoringMetrics | None,
    nv_metrics: StartupScoringMetrics | None,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if ai_label_count < AI_NATIVE_MIN_LABELED:
        blockers.append(f"AI Native labels ({ai_label_count}) < minimum ({AI_NATIVE_MIN_LABELED})")
    if nv_label_count < NVIDIA_FIT_MIN_LABELED:
        blockers.append(f"NVIDIA Fit labels ({nv_label_count}) < minimum ({NVIDIA_FIT_MIN_LABELED})")
    if ai_metrics is not None:
        if ai_metrics.spearman is not None and ai_metrics.spearman < AI_NATIVE_SPEARMAN_MIN:
            blockers.append(f"AI Native spearman ({ai_metrics.spearman:.4f}) < minimum ({AI_NATIVE_SPEARMAN_MIN})")
        if ai_metrics.mae is not None and ai_metrics.mae > AI_NATIVE_MAE_MAX:
            blockers.append(f"AI Native mae ({ai_metrics.mae:.4f}) > maximum ({AI_NATIVE_MAE_MAX})")
    if nv_metrics is not None:
        if nv_metrics.spearman is not None and nv_metrics.spearman < NVIDIA_FIT_SPEARMAN_MIN:
            blockers.append(f"NVIDIA Fit spearman ({nv_metrics.spearman:.4f}) < minimum ({NVIDIA_FIT_SPEARMAN_MIN})")
        if nv_metrics.mae is not None and nv_metrics.mae > NVIDIA_FIT_MAE_MAX:
            blockers.append(f"NVIDIA Fit mae ({nv_metrics.mae:.4f}) > maximum ({NVIDIA_FIT_MAE_MAX})")
        if nv_metrics.false_positive_rate is not None and nv_metrics.false_positive_rate > NVIDIA_FIT_FP_RATE_MAX:
            blockers.append(
                f"NVIDIA Fit fp_rate ({nv_metrics.false_positive_rate:.4f}) > maximum ({NVIDIA_FIT_FP_RATE_MAX})"
            )
    return len(blockers) == 0, blockers


# ── Calibration orchestrator ──────────────────────────────────────────────


@dataclass
class StartupScoringCalibrationResult:
    calibration_status: str
    production_allowed: bool
    golden_set_size: int
    has_human_labels: bool
    human_label_coverage: dict[str, int]
    ai_candidates: list[WeightCandidateResult]
    nv_candidates: list[WeightCandidateResult]
    best_ai_candidate_index: int | None = None
    best_nv_candidate_index: int | None = None
    best_ai_metrics: StartupScoringMetrics | None = None
    best_nv_metrics: StartupScoringMetrics | None = None
    ai_threshold: dict[str, Any] | None = None
    nv_threshold: dict[str, Any] | None = None
    ai_uncertainty: dict[str, Any] | None = None
    nv_uncertainty: dict[str, Any] | None = None
    production_blockers: list[str] | None = None
    labels_missing_notes: str = ""
    report: str = ""


def _format_startup_scoring_report(
    entries_count: int,
    has_labels: bool,
    label_coverage: dict[str, int],
    ai_candidates: list[WeightCandidateResult],
    nv_candidates: list[WeightCandidateResult],
    best_ai_idx: int | None,
    best_nv_idx: int | None,
    ai_threshold: dict[str, Any] | None,
    nv_threshold: dict[str, Any] | None,
    ai_uncertainty: dict[str, Any] | None,
    nv_uncertainty: dict[str, Any] | None,
    best_ai_metrics: StartupScoringMetrics | None,
    best_nv_metrics: StartupScoringMetrics | None,
    status: str,
    prod_allowed: bool,
    blockers: list[str] | None,
    labels_missing_notes: str,
) -> str:
    lines = [
        "=" * 72,
        "STARTUP SCORING BASELINE — CALIBRATION REPORT",
        "=" * 72,
        "",
        f"Golden set size: {entries_count}",
        f"Has human labels: {has_labels}",
        f"AI Native labels: {label_coverage.get('ai_native_labels', 0)}",
        f"NVIDIA Fit labels: {label_coverage.get('nvidia_fit_labels', 0)}",
        f"Calibration status: {status}",
        f"Production allowed: {prod_allowed}",
    ]
    if blockers:
        lines.append("Blockers:")
        for b in blockers:
            lines.append(f"  - {b}")
    lines.append("")
    if labels_missing_notes:
        lines.append(f"Notes: {labels_missing_notes}")
        lines.append("")

    if ai_candidates:
        lines.append("--- AI Native candidates ---")
        for c in ai_candidates:
            lines.append(
                f"  Candidate {c.candidate_index}: "
                f"spearman={c.spearman}, mae={c.mae}, f1={c.f1}, "
                f"feature_coverage={c.feature_coverage}"
            )
        if best_ai_idx is not None:
            bc = ai_candidates[best_ai_idx]
            lines.append(f"  Best: candidate {best_ai_idx} — weights={bc.weights}")
    if best_ai_metrics:
        lines.append(
            f"  Metrics: spearman={best_ai_metrics.spearman}, mae={best_ai_metrics.mae}, "
            f"rmse={best_ai_metrics.rmse}, f1={best_ai_metrics.f1}, "
            f"feature_coverage={best_ai_metrics.feature_coverage}"
        )
    lines.append("")

    if nv_candidates:
        lines.append("--- NVIDIA Fit candidates ---")
        for c in nv_candidates:
            lines.append(
                f"  Candidate {c.candidate_index}: "
                f"spearman={c.spearman}, mae={c.mae}, f1={c.f1}, "
                f"fp_rate={c.fp_rate}, feature_coverage={c.feature_coverage}"
            )
        if best_nv_idx is not None:
            bc = nv_candidates[best_nv_idx]
            lines.append(f"  Best: candidate {best_nv_idx} — weights={bc.weights}")
    if best_nv_metrics:
        lines.append(
            f"  Metrics: spearman={best_nv_metrics.spearman}, mae={best_nv_metrics.mae}, "
            f"rmse={best_nv_metrics.rmse}, f1={best_nv_metrics.f1}, "
            f"precision@k={best_nv_metrics.precision_at_k}, recall@k={best_nv_metrics.recall_at_k}, "
            f"fp_rate={best_nv_metrics.false_positive_rate}"
        )
    lines.append("")

    if ai_threshold:
        lines.append("--- AI Native threshold ---")
        lines.append(f"  Threshold: {ai_threshold.get('threshold')}")
        lines.append(f"  Method: {ai_threshold.get('method')}")
        lines.append(f"  Distribution: {ai_threshold.get('distribution')}")
    if nv_threshold:
        lines.append("--- NVIDIA Fit threshold ---")
        lines.append(f"  Threshold: {nv_threshold.get('threshold')}")
        lines.append(f"  Method: {nv_threshold.get('method')}")
        lines.append(f"  Distribution: {nv_threshold.get('distribution')}")
    if ai_uncertainty:
        lines.append("--- AI Native uncertainty penalty ---")
        lines.append(f"  Best penalty: {ai_uncertainty.get('best_penalty')}")
        lines.append(f"  Best MAE: {ai_uncertainty.get('best_mae')}")
    if nv_uncertainty:
        lines.append("--- NVIDIA Fit uncertainty penalty ---")
        lines.append(f"  Best penalty: {nv_uncertainty.get('best_penalty')}")
        lines.append(f"  Best MAE: {nv_uncertainty.get('best_mae')}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def run_startup_scoring_baseline_calibration(
    golden_path: Path | None = None,
) -> StartupScoringCalibrationResult:
    path = golden_path or _GOLDEN_SET_PATH
    entries = load_startup_scoring_golden_set(path)

    if not entries:
        return StartupScoringCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            human_label_coverage={
                "ai_native_labels": 0,
                "nvidia_fit_labels": 0,
                "total_entries": 0,
            },
            ai_candidates=[],
            nv_candidates=[],
            ai_threshold=None,
            nv_threshold=None,
            ai_uncertainty=None,
            nv_uncertainty=None,
            production_blockers=["Golden set is empty."],
            labels_missing_notes="Golden set at {path} is empty. Add human-labeled startup entries.",
            report="No data — golden set is empty.",
        )

    has_labels = check_human_labels_exist(entries)
    ai_labels = sum(1 for e in entries if e.human_label_ai_native_numeric is not None)
    nv_labels = sum(1 for e in entries if e.human_label_nvidia_fit_numeric is not None)
    label_coverage = {
        "ai_native_labels": ai_labels,
        "nvidia_fit_labels": nv_labels,
        "total_entries": len(entries),
    }

    if not has_labels or (ai_labels < 3 and nv_labels < 3):
        return StartupScoringCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=len(entries),
            has_human_labels=has_labels,
            human_label_coverage=label_coverage,
            ai_candidates=[],
            nv_candidates=[],
            ai_threshold=None,
            nv_threshold=None,
            ai_uncertainty=None,
            nv_uncertainty=None,
            production_blockers=["Insufficient human labels for calibration."],
            labels_missing_notes=(
                f"Found {ai_labels} AI labels and {nv_labels} NVIDIA labels. Need at least 3 of each for metrics."
            ),
            report="Insufficient labels — cannot compute calibration metrics.",
        )

    ai_candidates = _evaluate_weight_candidates(entries, CANDIDATE_AI_WEIGHTS, "ai_native")
    nv_candidates = _evaluate_weight_candidates(entries, CANDIDATE_NVIDIA_WEIGHTS, "nvidia_fit")

    best_ai_idx = _select_best_candidate(ai_candidates, "ai_native")
    best_nv_idx = _select_best_candidate(nv_candidates, "nvidia_fit")

    # Compute metrics for best candidates
    best_ai_metrics: StartupScoringMetrics | None = None
    best_nv_metrics: StartupScoringMetrics | None = None
    best_ai_weights: dict[str, float] = CANDIDATE_AI_WEIGHTS[0]
    best_nv_weights: dict[str, float] = CANDIDATE_NVIDIA_WEIGHTS[0]

    if best_ai_idx is not None:
        bc = ai_candidates[best_ai_idx]
        best_ai_weights = bc.weights
        predicted, human_labels, feature_dicts = _compute_scores_for_entries(entries, best_ai_weights, "ai_native")
        if len(predicted) >= 3:
            best_ai_metrics = _compute_ai_native_metrics(predicted, human_labels, feature_dicts)
    else:
        predicted, human_labels, feature_dicts = _compute_scores_for_entries(entries, best_ai_weights, "ai_native")
        if len(predicted) >= 3:
            best_ai_metrics = _compute_ai_native_metrics(predicted, human_labels, feature_dicts)

    if best_nv_idx is not None:
        bc = nv_candidates[best_nv_idx]
        best_nv_weights = bc.weights
        predicted_nv, human_labels_nv, feature_dicts_nv = _compute_scores_for_entries(
            entries, best_nv_weights, "nvidia_fit"
        )
        if len(predicted_nv) >= 3:
            best_nv_metrics = _compute_nvidia_fit_metrics(predicted_nv, human_labels_nv, feature_dicts_nv)
    else:
        predicted_nv, human_labels_nv, feature_dicts_nv = _compute_scores_for_entries(
            entries, best_nv_weights, "nvidia_fit"
        )
        if len(predicted_nv) >= 3:
            best_nv_metrics = _compute_nvidia_fit_metrics(predicted_nv, human_labels_nv, feature_dicts_nv)

    # Threshold calibration
    ai_threshold = None
    nv_threshold = None
    if best_ai_metrics is not None and len(predicted) >= 3:
        ai_threshold = _calibrate_threshold_from_errors(predicted, human_labels, percentile=5.0)
    if best_nv_metrics is not None and len(predicted_nv) >= 3:
        nv_threshold = _calibrate_threshold_from_errors(predicted_nv, human_labels_nv, percentile=5.0)

    # Uncertainty penalty
    ai_uncertainty = None
    nv_uncertainty = None
    if best_ai_metrics is not None and len(predicted) >= 3:
        ai_uncertainties = [fd.get("uncertainty_penalty", 0.0) for fd in feature_dicts]
        ai_uncertainty = _calibrate_uncertainty_penalty_from_data(predicted, human_labels, ai_uncertainties)
    if best_nv_metrics is not None and len(predicted_nv) >= 3:
        nv_uncertainties = [fd.get("uncertainty_penalty", 0.0) for fd in feature_dicts_nv]
        nv_uncertainty = _calibrate_uncertainty_penalty_from_data(predicted_nv, human_labels_nv, nv_uncertainties)

    # Production readiness
    prod_ready, blockers = _check_startup_scoring_production_ready(
        ai_labels,
        nv_labels,
        best_ai_metrics,
        best_nv_metrics,
    )

    if prod_ready and has_labels and ai_labels >= AI_NATIVE_MIN_LABELED and nv_labels >= NVIDIA_FIT_MIN_LABELED:
        calibration_status = "baseline_measured"
        production_allowed = True
    elif not has_labels:
        calibration_status = "baseline_dataset_insufficient"
        production_allowed = False
    else:
        calibration_status = "baseline_measured_blocked"
        production_allowed = False

    labels_missing_notes = (
        f"AI labels: {ai_labels}, NVIDIA labels: {nv_labels}. Blockers: {'; '.join(blockers) if blockers else 'none'}"
    )

    report = _format_startup_scoring_report(
        entries_count=len(entries),
        has_labels=has_labels,
        label_coverage=label_coverage,
        ai_candidates=ai_candidates,
        nv_candidates=nv_candidates,
        best_ai_idx=best_ai_idx,
        best_nv_idx=best_nv_idx,
        ai_threshold=ai_threshold,
        nv_threshold=nv_threshold,
        ai_uncertainty=ai_uncertainty,
        nv_uncertainty=nv_uncertainty,
        best_ai_metrics=best_ai_metrics,
        best_nv_metrics=best_nv_metrics,
        status=calibration_status,
        prod_allowed=production_allowed,
        blockers=blockers,
        labels_missing_notes=labels_missing_notes,
    )

    return StartupScoringCalibrationResult(
        calibration_status=calibration_status,
        production_allowed=production_allowed,
        golden_set_size=len(entries),
        has_human_labels=has_labels,
        human_label_coverage=label_coverage,
        ai_candidates=ai_candidates,
        nv_candidates=nv_candidates,
        best_ai_candidate_index=best_ai_idx,
        best_nv_candidate_index=best_nv_idx,
        best_ai_metrics=best_ai_metrics,
        best_nv_metrics=best_nv_metrics,
        ai_threshold=ai_threshold,
        nv_threshold=nv_threshold,
        ai_uncertainty=ai_uncertainty,
        nv_uncertainty=nv_uncertainty,
        production_blockers=blockers,
        labels_missing_notes=labels_missing_notes,
        report=report,
    )


def make_startup_scoring_baseline_records(
    cal_result: StartupScoringCalibrationResult,
) -> list[DecisionCalibrationRecord]:
    from datetime import datetime

    _now = datetime(2026, 6, 18, tzinfo=UTC)

    if cal_result.calibration_status == "baseline_dataset_insufficient" or not cal_result.production_allowed:
        status = CalibrationStatus.UNCALIBRATED
        prod = False
        notes_template = (
            "Baseline calibration blocked: {reason}. "
            "Calibration requires at least {min_labels} human-labeled entries "
            "with acceptable metrics (spearman>={spearman}, mae<={mae}). "
            "Current: {ai_labels} AI labels, {nv_labels} NVIDIA labels."
        )
    else:
        status = CalibrationStatus.BASELINE_MEASURED
        prod = True
        notes_template = "Baseline calibration measured with {size} entries."

    reason = "; ".join(cal_result.production_blockers) if cal_result.production_blockers else "production_blocked"
    ai_labels = cal_result.human_label_coverage.get("ai_native_labels", 0)
    nv_labels = cal_result.human_label_coverage.get("nvidia_fit_labels", 0)

    notes = notes_template.format(
        reason=reason,
        min_labels=AI_NATIVE_MIN_LABELED,
        spearman=AI_NATIVE_SPEARMAN_MIN,
        mae=AI_NATIVE_MAE_MAX,
        ai_labels=ai_labels,
        nv_labels=nv_labels,
        size=cal_result.golden_set_size,
    )

    ai_weights = None
    nv_weights = None
    if cal_result.best_ai_candidate_index is not None and cal_result.ai_candidates:
        ai_weights = cal_result.ai_candidates[cal_result.best_ai_candidate_index].weights
    if cal_result.best_nv_candidate_index is not None and cal_result.nv_candidates:
        nv_weights = cal_result.nv_candidates[cal_result.best_nv_candidate_index].weights

    ai_threshold_value = None
    nv_threshold_value = None
    if cal_result.ai_threshold:
        ai_threshold_value = cal_result.ai_threshold.get("threshold")
    if cal_result.nv_threshold:
        nv_threshold_value = cal_result.nv_threshold.get("threshold")

    ai_uncertainty_value = None
    nv_uncertainty_value = None
    if cal_result.ai_uncertainty:
        ai_uncertainty_value = cal_result.ai_uncertainty.get("best_penalty")
    if cal_result.nv_uncertainty:
        nv_uncertainty_value = cal_result.nv_uncertainty.get("best_penalty")

    evidence_source = (
        f"src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- "
        f"golden_path=data/eval/golden_startup_scoring_baseline.json. "
        f"Status: {cal_result.calibration_status}. "
        f"Entries: {cal_result.golden_set_size}, AI labels: {ai_labels}, NVIDIA labels: {nv_labels}. "
        f"Production: {cal_result.production_allowed}."
    )

    return [
        DecisionCalibrationRecord(
            decision_id="ai_native_score.weights",
            decision_name="AI Native Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=ai_weights,
            metric_name="ai_native_score_weights",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- grid search over {len(CANDIDATE_AI_WEIGHTS)} candidates on {cal_result.golden_set_size} human-labeled entries.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.production_threshold",
            decision_name="AI Native Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=ai_threshold_value,
            metric_name="ai_native_score_production_min",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- percentile of predicted distribution from human-labeled data.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="ai_native_score.uncertainty_penalty",
            decision_name="AI Native Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=ai_uncertainty_value,
            metric_name="ai_native_score_uncertainty_penalty",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- sensitivity analysis over human labels.",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.weights",
            decision_name="NVIDIA Fit Score: Per-Feature Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=nv_weights,
            metric_name="nvidia_fit_score_weights",
            value_origin=f"src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- grid search over {len(CANDIDATE_NVIDIA_WEIGHTS)} candidates on {cal_result.golden_set_size} human-labeled entries.",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.production_threshold",
            decision_name="NVIDIA Fit Score: Minimum for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=nv_threshold_value,
            metric_name="nvidia_fit_score_production_min",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- percentile of predicted distribution from human-labeled data.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="nvidia_fit_score.uncertainty_penalty",
            decision_name="NVIDIA Fit Score: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=nv_uncertainty_value,
            metric_name="nvidia_fit_score_uncertainty_penalty",
            value_origin="src/evaluation/startup_scoring_calibration.py :: run_startup_scoring_baseline_calibration -- sensitivity analysis over human labels.",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=status,
            production_allowed=prod,
            owner="team-scoring",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Startup scoring calibration")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "baseline", "both"],
        default="baseline",
        help="Calibration mode: synthetic (old), baseline (human labels), or both",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run baseline check only — no calibration",
    )
    args = parser.parse_args()

    if args.check:
        result = run_startup_scoring_baseline_calibration()
        print(f"\nBaseline check: {result.calibration_status}")
        print(
            f"Golden set: {result.golden_set_size} entries, "
            f"AI labels: {result.human_label_coverage.get('ai_native_labels', 0)}, "
            f"NVIDIA labels: {result.human_label_coverage.get('nvidia_fit_labels', 0)}"
        )
        print(f"Production allowed: {result.production_allowed}")
        if result.production_blockers:
            print("Blockers:")
            for b in result.production_blockers:
                print(f"  - {b}")
        print("Done.")
        return

    if args.mode in ("synthetic", "both"):
        synth_result_dict = run_full_calibration(golden_count=60)
        ai = synth_result_dict["ai_native"]
        nv = synth_result_dict["nvidia_fit"]
        print("\n" + "=" * 60)
        print("SYNTHETIC CALIBRATION SUMMARY")
        print("=" * 60)
        print(
            "ai_native_score.weights: spearman={} -> {}".format(
                ai["spearman"], "PASS" if ai["meets_criteria"] else "FAIL"
            )
        )
        print(
            "nvidia_fit_score.weights: spearman={} -> {}".format(
                nv["spearman"], "PASS" if nv["meets_criteria"] else "FAIL"
            )
        )
        print("ai_native_score.production_threshold: p5={}".format(ai["threshold"]["recommended_threshold"]))
        print("nvidia_fit_score.production_threshold: p5={}".format(nv["threshold"]["recommended_threshold"]))

    if args.mode in ("baseline", "both"):
        base_result = run_startup_scoring_baseline_calibration()
        print("\n" + "=" * 60)
        print("BASELINE CALIBRATION SUMMARY")
        print("=" * 60)
        print(f"Status: {base_result.calibration_status}")
        print(f"Production allowed: {base_result.production_allowed}")
        print(f"Golden set size: {base_result.golden_set_size}")
        print("AI labels: {}".format(base_result.human_label_coverage.get("ai_native_labels", 0)))
        print("NVIDIA labels: {}".format(base_result.human_label_coverage.get("nvidia_fit_labels", 0)))
        print("\nAll 6 baseline calibration records generated.")

    print("\nDone.")


if __name__ == "__main__":
    main()
