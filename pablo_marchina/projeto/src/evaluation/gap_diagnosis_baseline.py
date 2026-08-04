"""Baseline evaluator for gap diagnosis calibration.

Loads a human-labeled golden set of startups with gap labels and
computes calibration metrics (precision, recall, F1, severity/confidence
accuracy, evidence coverage). Determines production readiness and
generates DecisionCalibrationRecords.

Usage:
    from src.evaluation.gap_diagnosis_baseline import run_gap_diagnosis_baseline_calibration
    result = run_gap_diagnosis_baseline_calibration()
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.diagnosis.gap_diagnosis_scoring import (
    extract_gap_confidence_features,
    extract_gap_severity_features,
)
from src.diagnosis.schemas import GapType
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

_GOLDEN_SET_PATH = Path("data/eval/golden_gap_diagnosis_baseline.json")

# ---------------------------------------------------------------------------
# Severity / Confidence feature names (mirrors gap_diagnosis_scoring)
# ---------------------------------------------------------------------------

SEVERITY_FEATURE_NAMES: list[str] = [
    "missing_required_signal_count",
    "weak_evidence_count",
    "rejected_evidence_count",
    "unsupported_claim_count",
    "low_confidence_evidence_count",
    "relevant_signal_absence",
    "nvidia_fit_opportunity_signal_count",
    "implementation_complexity_proxy",
    "business_impact_proxy",
    "uncertainty_penalty",
]

CONFIDENCE_FEATURE_NAMES: list[str] = [
    "supporting_evidence_count",
    "supporting_source_count",
    "average_evidence_confidence",
    "average_source_quality",
    "cross_source_agreement_count",
    "contradiction_count",
    "extraction_success_rate",
    "source_category_coverage",
]

# ---------------------------------------------------------------------------
# Reference weights (hidden ground-truth for synthetic data)
# ---------------------------------------------------------------------------

_REFERENCE_SEVERITY_WEIGHTS: dict[str, float] = {
    "missing_required_signal_count": 0.22,
    "weak_evidence_count": 0.15,
    "rejected_evidence_count": 0.12,
    "unsupported_claim_count": 0.15,
    "low_confidence_evidence_count": 0.10,
    "relevant_signal_absence": 0.10,
    "nvidia_fit_opportunity_signal_count": 0.05,
    "implementation_complexity_proxy": 0.05,
    "business_impact_proxy": 0.03,
    "uncertainty_penalty": 0.03,
}

_REFERENCE_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "supporting_evidence_count": 0.20,
    "supporting_source_count": 0.15,
    "average_evidence_confidence": 0.15,
    "average_source_quality": 0.15,
    "cross_source_agreement_count": 0.12,
    "contradiction_count": 0.10,
    "extraction_success_rate": 0.08,
    "source_category_coverage": 0.05,
}

# ---------------------------------------------------------------------------
# Candidate weight sets for grid search
# ---------------------------------------------------------------------------

CANDIDATE_SEVERITY_WEIGHTS: list[dict[str, float]] = [
    {
        "missing_required_signal_count": 0.25,
        "weak_evidence_count": 0.20,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.20,
        "weak_evidence_count": 0.15,
        "rejected_evidence_count": 0.15,
        "unsupported_claim_count": 0.15,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.15,
        "weak_evidence_count": 0.10,
        "rejected_evidence_count": 0.20,
        "unsupported_claim_count": 0.20,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.05,
        "implementation_complexity_proxy": 0.05,
        "business_impact_proxy": 0.03,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.30,
        "weak_evidence_count": 0.15,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.15,
        "nvidia_fit_opportunity_signal_count": 0.03,
        "implementation_complexity_proxy": 0.03,
        "business_impact_proxy": 0.02,
        "uncertainty_penalty": 0.02,
    },
    {
        "missing_required_signal_count": 0.15,
        "weak_evidence_count": 0.10,
        "rejected_evidence_count": 0.10,
        "unsupported_claim_count": 0.10,
        "low_confidence_evidence_count": 0.10,
        "relevant_signal_absence": 0.10,
        "nvidia_fit_opportunity_signal_count": 0.10,
        "implementation_complexity_proxy": 0.10,
        "business_impact_proxy": 0.10,
        "uncertainty_penalty": 0.05,
    },
]

CANDIDATE_CONFIDENCE_WEIGHTS: list[dict[str, float]] = [
    {
        "supporting_evidence_count": 0.25,
        "supporting_source_count": 0.15,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.15,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.20,
        "supporting_source_count": 0.15,
        "average_evidence_confidence": 0.15,
        "average_source_quality": 0.15,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.07,
    },
    {
        "supporting_evidence_count": 0.15,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.12,
        "cross_source_agreement_count": 0.18,
        "contradiction_count": 0.18,
        "extraction_success_rate": 0.08,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.12,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.22,
        "average_source_quality": 0.22,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.07,
        "source_category_coverage": 0.05,
    },
    {
        "supporting_evidence_count": 0.15,
        "supporting_source_count": 0.12,
        "average_evidence_confidence": 0.12,
        "average_source_quality": 0.12,
        "cross_source_agreement_count": 0.10,
        "contradiction_count": 0.10,
        "extraction_success_rate": 0.15,
        "source_category_coverage": 0.14,
    },
]

# ---------------------------------------------------------------------------
# Production criteria thresholds
# ---------------------------------------------------------------------------

MIN_LABELED_ENTRIES = 20
MIN_SPEARMAN = 0.5
MAX_MAE = 0.2
MAX_FP_RATE = 0.3
MIN_CALIBRATION_COVERAGE = 0.5

# ---------------------------------------------------------------------------
# Golden entry schema
# ---------------------------------------------------------------------------


class HumanLabeledGap(BaseModel):
    gap_type: str
    human_label_gap_present: bool
    human_label_severity: float = Field(ge=0.0, le=1.0)
    human_label_confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    label_notes: str = ""
    label_source: str = ""
    reviewer_id: str | None = None


class GapDiagnosisGoldenEntry(BaseModel):
    startup_id: str
    startup_name: str
    startup_profile_snapshot: dict[str, Any] = Field(default_factory=dict)
    accepted_evidence_items_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    accepted_claims_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    ai_native_score_snapshot: float | None = None
    nvidia_fit_score_snapshot: float | None = None
    expected_gap_types: list[str] = Field(default_factory=list)
    human_labeled_gaps: list[HumanLabeledGap] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metric data structures
# ---------------------------------------------------------------------------


@dataclass
class GapDetectionMetrics:
    gap_type_precision: dict[str, float] | None = None
    gap_type_recall: dict[str, float] | None = None
    gap_type_f1: dict[str, float] | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    coverage_by_gap_type: dict[str, float] | None = None


@dataclass
class SeverityMetrics:
    correlation: float | None = None
    mae: float | None = None
    rmse: float | None = None
    calibration_error: float | None = None
    high_severity_precision: float | None = None
    high_severity_recall: float | None = None


@dataclass
class ConfidenceMetrics:
    correlation: float | None = None
    mae: float | None = None
    rmse: float | None = None
    calibration_error: float | None = None
    uncertainty_error_relationship: float | None = None


@dataclass
class EvidenceMetrics:
    evidence_coverage_per_gap: dict[str, float] | None = None
    unsupported_gap_rate: float | None = None
    gap_without_evidence_rate: float | None = None
    evidence_alignment_precision: float | None = None


@dataclass
class GapDiagnosisCalibrationMetrics:
    gap_detection: GapDetectionMetrics | None = None
    severity: SeverityMetrics | None = None
    confidence: ConfidenceMetrics | None = None
    evidence: EvidenceMetrics | None = None


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Golden set I/O
# ---------------------------------------------------------------------------


def load_gap_diagnosis_golden_set(
    path: Path | None = None,
) -> list[GapDiagnosisGoldenEntry]:
    path = path or _GOLDEN_SET_PATH
    if not path.exists():
        logger.warning("Gap diagnosis golden set not found at %s", path)
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("startups", [])
    return [GapDiagnosisGoldenEntry(**e) for e in entries]


def check_gap_diagnosis_labels_exist(
    entries: list[GapDiagnosisGoldenEntry],
) -> bool:
    for e in entries:
        if len(e.human_labeled_gaps) > 0:
            return True
    return False


def count_labeled_gaps(
    entries: list[GapDiagnosisGoldenEntry],
) -> dict[str, Any]:
    total_gap_labels = 0
    gap_type_counts: dict[str, int] = {}
    for e in entries:
        total_gap_labels += len(e.human_labeled_gaps)
        for g in e.human_labeled_gaps:
            gap_type_counts[g.gap_type] = gap_type_counts.get(g.gap_type, 0) + 1
    return {
        "total_entries_with_labels": sum(1 for e in entries if len(e.human_labeled_gaps) > 0),
        "total_gap_labels": total_gap_labels,
        "gap_type_coverage": gap_type_counts,
    }


# ---------------------------------------------------------------------------
# Synthetic golden set generation (for testing)
# ---------------------------------------------------------------------------


def _generate_evidence_text(
    gap_type: GapType,
    rng: random.Random,
) -> str:
    from src.diagnosis.schemas import GAP_TECH_MAP

    pool: dict[str, list[str]] = {
        "compute_acceleration_gap": [
            "GPU acceleration for training workloads",
            "High-performance computing with CUDA",
            "GPU cluster for parallel processing",
        ],
        "inference_performance_gap": [
            "Real-time inference serving",
            "Low-latency model deployment",
            "High-throughput inference pipeline",
        ],
        "training_scalability_gap": [
            "Distributed training across multiple GPUs",
            "Training large language models",
            "Scalable training infrastructure",
        ],
        "mlops_deployment_gap": [
            "ML model deployment pipeline",
            "Model monitoring and observability",
            "CI/CD for machine learning models",
        ],
        "data_pipeline_gap": [
            "Large-scale data processing with Spark",
            "ETL pipeline for structured data",
            "Data ingestion from multiple sources",
        ],
        "model_optimization_gap": [
            "Model quantization and pruning",
            "ONNX runtime optimization",
            "TensorRT model optimization",
        ],
        "computer_vision_gap": [
            "Computer vision for object detection",
            "Image recognition with deep learning",
            "Video analytics platform",
        ],
        "genai_llm_gap": [
            "LLM-powered chatbot application",
            "Generative AI for content creation",
            "RAG-based question answering",
        ],
        "cybersecurity_ai_gap": [
            "AI-powered threat detection",
            "Anomaly detection for security",
            "Intrusion prevention with ML",
        ],
        "nvidia_ecosystem_fit_gap": [
            "GPU computing with NVIDIA CUDA",
            "NVIDIA Triton inference server",
            "RAPIDS for data science",
        ],
        "evidence_coverage_gap": [
            "General AI startup description",
            "Technology platform overview",
            "Marketplace solution",
        ],
        "technical_depth_gap": [
            "API integration platform",
            "SaaS business management",
            "Enterprise software solution",
        ],
    }
    options = pool.get(gap_type.value, ["Technology platform description"])
    text = rng.choice(options)
    gap_techs = GAP_TECH_MAP.get(gap_type, [])
    if gap_techs:
        kw = rng.choice(gap_techs).value
        if kw not in text.lower():
            text = f"{text} {kw}"
    return text


def _generate_claim_text(
    gap_type: GapType,
    rng: random.Random,
) -> str:
    from src.diagnosis.schemas import GAP_TECH_MAP

    claims: dict[str, list[str]] = {
        "compute_acceleration_gap": [
            "Precisa de aceleracao GPU para treinamento",
            "Treinamento de modelos e lento",
        ],
        "inference_performance_gap": [
            "Inferencia em tempo real e necessaria",
            "Baixa latencia para deployed models",
        ],
        "training_scalability_gap": [
            "Treinamento distribuido essencial",
            "Modelos grandes exigem multi-GPU",
        ],
        "mlops_deployment_gap": [
            "Governanca de modelos necessaria",
            "MLOps pipeline nao automatizado",
        ],
        "data_pipeline_gap": [
            "Pipeline de dados lento",
            "ETL precisa de otimizacao",
        ],
        "model_optimization_gap": [
            "Modelos precisam de otimizacao",
            "Quantizacao reduziria custos",
        ],
        "computer_vision_gap": [
            "Visao computacional para inspecao",
            "Detecao de objetos em video",
        ],
        "genai_llm_gap": [
            "Chatbot com LLM precisa de GPU",
            "Geracao de texto demanda GPU",
        ],
        "cybersecurity_ai_gap": [
            "Deteccao de ameacas com ML",
            "Seguranca baseada em IA",
        ],
        "nvidia_ecosystem_fit_gap": [
            "Compatibilidade com NVIDIA necessaria",
            "GPU computing aceleraria",
        ],
        "evidence_coverage_gap": [
            "Startup de tecnologia geral",
            "Plataforma de software empresarial",
        ],
        "technical_depth_gap": [
            "Produto de baixa complexidade tecnica",
            "API wrapper sem inovacao",
        ],
    }
    options = claims.get(gap_type.value, ["Descricao generica da startup"])
    text = rng.choice(options)
    gap_techs = GAP_TECH_MAP.get(gap_type, [])
    if gap_techs:
        for t in gap_techs:
            kw = t.value
            if kw not in text.lower():
                text = f"{text} {kw}"
                break
    return text


def _make_synthetic_evidence_item(
    gap_type: GapType,
    idx: int,
    quality: float,
    rng: random.Random,
) -> dict[str, Any]:
    text = _generate_evidence_text(gap_type, rng)
    return {
        "id": f"synth-ev-{gap_type.value}-{idx}",
        "evidence_id": f"synth-ev-{gap_type.value}-{idx}",
        "source_id": f"synth-src-{gap_type.value}-{idx}",
        "url": f"https://example.com/{gap_type.value}/{idx}",
        "text": text,
        "snippet": text[:200],
        "claim": text,
        "confidence": "high" if quality > 0.7 else "medium",
        "evidence_confidence_score": round(quality, 4),
        "source_quality_score": round(quality * 0.9, 4),
        "source_type": rng.choice(["official_website", "technical_docs", "news"]),
    }


def _make_synthetic_claim(
    gap_type: GapType,
    idx: int,
    is_critical: bool,
    rng: random.Random,
) -> dict[str, Any]:
    text = _generate_claim_text(gap_type, rng)
    return {
        "id": f"synth-cl-{gap_type.value}-{idx}",
        "claim_id": f"synth-cl-{gap_type.value}-{idx}",
        "claim_text": text,
        "support_status": "supported" if rng.random() < 0.8 else "unsupported",
        "is_critical": is_critical,
    }


def generate_synthetic_gap_diagnosis_golden_set(
    count: int = 60,
) -> list[GapDiagnosisGoldenEntry]:
    rng = random.Random(42)
    entries: list[GapDiagnosisGoldenEntry] = []

    for i in range(count):
        startup_id = f"synth-gap-{i:04d}"
        gap_types_sample = rng.sample(list(GapType), min(3, len(GapType)))
        evidence_items: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []

        for gt in gap_types_sample:
            n_ev = rng.randint(1, 4)
            quality_base = rng.uniform(0.3, 0.95)
            for j in range(n_ev):
                ev = _make_synthetic_evidence_item(gt, j, quality_base + rng.gauss(0, 0.1), rng)
                ev["evidence_confidence_score"] = max(0.0, min(1.0, ev["evidence_confidence_score"]))
                ev["source_quality_score"] = max(0.0, min(1.0, ev["source_quality_score"]))
                evidence_items.append(ev)

            claim = _make_synthetic_claim(gt, 0, is_critical=(rng.random() < 0.2), rng=rng)
            claims.append(claim)

        # Extract features using the COMPLETE evidence/claims (consistent with evaluator)
        human_labeled_gaps: list[HumanLabeledGap] = []
        all_ev_ids = [e.get("id") or e.get("evidence_id", "") for e in evidence_items]
        for gt in gap_types_sample:
            sev_features = extract_gap_severity_features(
                gap_type=gt,
                evidence_items=evidence_items,
                accepted_evidence_items=evidence_items,
                rejected_evidence_items=[],
                claims=claims,
                evidence_validation=None,
                collection_metrics=None,
            )
            conf_features = extract_gap_confidence_features(
                gap_type=gt,
                evidence_items=evidence_items,
                accepted_evidence_items=evidence_items,
                claims=claims,
                collection_metrics=None,
                extraction_metrics=None,
            )

            ref_sev = _compute_weighted_score(
                sev_features.model_dump(mode="json"),
                _REFERENCE_SEVERITY_WEIGHTS,
            )
            ref_conf = _compute_weighted_score(
                conf_features.model_dump(mode="json"),
                _REFERENCE_CONFIDENCE_WEIGHTS,
            )

            is_present = ref_sev > 0.3

            human_labeled_gaps.append(
                HumanLabeledGap(
                    gap_type=gt.value,
                    human_label_gap_present=is_present,
                    human_label_severity=round(ref_sev, 4),
                    human_label_confidence=round(ref_conf, 4),
                    supporting_evidence_ids=all_ev_ids,
                    label_notes="Synthetic derived from reference weights",
                    label_source="derived_from_synthetic_reference",
                    reviewer_id="synthetic-generator",
                )
            )

        entries.append(
            GapDiagnosisGoldenEntry(
                startup_id=startup_id,
                startup_name=f"SynthGap {i:04d}",
                startup_profile_snapshot={"sector": "Technology", "funding_stage": "seed"},
                accepted_evidence_items_snapshot=evidence_items,
                accepted_claims_snapshot=claims,
                ai_native_score_snapshot=round(rng.uniform(0.0, 1.0), 4),
                nvidia_fit_score_snapshot=round(rng.uniform(0.0, 1.0), 4),
                expected_gap_types=[gt.value for gt in gap_types_sample],
                human_labeled_gaps=human_labeled_gaps,
            )
        )

    return entries


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_gap_detection_metrics(
    predicted_gaps: list[dict[str, Any]],
    human_labeled_gaps: list[HumanLabeledGap],
    all_gap_types: list[str],
) -> GapDetectionMetrics | None:
    gt_map: dict[str, bool] = {}
    for hg in human_labeled_gaps:
        gt_map[hg.gap_type] = hg.human_label_gap_present

    if not gt_map:
        return None

    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    coverage: dict[str, float] = {}

    total_fp = 0
    total_fn = 0
    total_predicted_positive = 0
    total_actual_positive = 0

    for gt in all_gap_types:
        if gt not in gt_map:
            coverage[gt] = 0.0
            continue

        coverage[gt] = 1.0

        pred_entry = next((p for p in predicted_gaps if p.get("gap_type") == gt), None)
        predicted_present = bool(pred_entry and pred_entry.get("detected", False))
        actual_present = gt_map[gt]

        tp = 1 if predicted_present and actual_present else 0
        fp = 1 if predicted_present and not actual_present else 0
        fn = 1 if not predicted_present and actual_present else 0

        total_fp += fp
        total_fn += fn
        if predicted_present:
            total_predicted_positive += 1
        if actual_present:
            total_actual_positive += 1

        precision[gt] = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if tp > 0 else 0.0)
        recall[gt] = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if tp > 0 else 0.0)
        f1[gt] = (
            2 * precision[gt] * recall[gt] / (precision[gt] + recall[gt]) if (precision[gt] + recall[gt]) > 0 else 0.0
        )

    fp_rate = total_fp / total_predicted_positive if total_predicted_positive > 0 else 0.0
    fn_rate = total_fn / total_actual_positive if total_actual_positive > 0 else 0.0

    return GapDetectionMetrics(
        gap_type_precision=precision,
        gap_type_recall=recall,
        gap_type_f1=f1,
        false_positive_rate=round(fp_rate, 4),
        false_negative_rate=round(fn_rate, 4),
        coverage_by_gap_type=coverage,
    )


def _compute_severity_metrics(
    predicted_scores: list[float],
    human_scores: list[float],
) -> SeverityMetrics | None:
    n = len(predicted_scores)
    if n < 3:
        return None

    correlation = _spearman(predicted_scores, human_scores)
    abs_errors = [abs(p - h) for p, h in zip(predicted_scores, human_scores, strict=True)]
    mae = sum(abs_errors) / n
    sq_errors = [(p - h) ** 2 for p, h in zip(predicted_scores, human_scores, strict=True)]
    rmse = math.sqrt(sum(sq_errors) / n)
    calibration_error = mae

    high_predicted = [s >= 0.7 for s in predicted_scores]
    high_human = [s >= 0.7 for s in human_scores]
    tp_high = sum(1 for p, h in zip(high_predicted, high_human, strict=True) if p and h)
    fp_high = sum(1 for p, h in zip(high_predicted, high_human, strict=True) if p and not h)
    fn_high = sum(1 for p, h in zip(high_predicted, high_human, strict=True) if not p and h)
    high_precision = tp_high / (tp_high + fp_high) if (tp_high + fp_high) > 0 else 0.0
    high_recall = tp_high / (tp_high + fn_high) if (tp_high + fn_high) > 0 else 0.0

    return SeverityMetrics(
        correlation=round(correlation, 4),
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        calibration_error=round(calibration_error, 4),
        high_severity_precision=round(high_precision, 4),
        high_severity_recall=round(high_recall, 4),
    )


def _compute_confidence_metrics(
    predicted_scores: list[float],
    human_scores: list[float],
    uncertainties: list[float],
) -> ConfidenceMetrics | None:
    n = len(predicted_scores)
    if n < 3:
        return None

    correlation = _spearman(predicted_scores, human_scores)
    abs_errors = [abs(p - h) for p, h in zip(predicted_scores, human_scores, strict=True)]
    mae = sum(abs_errors) / n
    sq_errors = [(p - h) ** 2 for p, h in zip(predicted_scores, human_scores, strict=True)]
    rmse = math.sqrt(sum(sq_errors) / n)
    calibration_error = mae

    uncertainty_error_relationship = 0.0
    if len(uncertainties) >= 3 and max(uncertainties) > min(uncertainties):
        uncertainty_error_relationship = _spearman(uncertainties, abs_errors)

    return ConfidenceMetrics(
        correlation=round(correlation, 4),
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        calibration_error=round(calibration_error, 4),
        uncertainty_error_relationship=round(uncertainty_error_relationship, 4),
    )


def _compute_evidence_metrics(
    gaps: list[dict[str, Any]],
    human_labeled_gaps: list[HumanLabeledGap],
) -> EvidenceMetrics | None:
    if not human_labeled_gaps:
        return None

    coverage_per_gap: dict[str, float] = {}
    for hg in human_labeled_gaps:
        gt = hg.gap_type
        ev_count = len(hg.supporting_evidence_ids)
        cov = 1.0 if ev_count > 0 else 0.0
        coverage_per_gap[gt] = cov

    gap_with_evidence_count = sum(1 for hg in human_labeled_gaps if len(hg.supporting_evidence_ids) > 0)
    gap_without_evidence_count = len(human_labeled_gaps) - gap_with_evidence_count
    gap_without_evidence_rate = gap_without_evidence_count / max(1, len(human_labeled_gaps))

    unsupported_count = sum(
        1 for hg in human_labeled_gaps if hg.human_label_gap_present and len(hg.supporting_evidence_ids) == 0
    )
    unsupported_gap_rate = unsupported_count / max(1, sum(1 for hg in human_labeled_gaps if hg.human_label_gap_present))

    alignment_count = sum(
        1
        for hg in human_labeled_gaps
        for pg in gaps
        if pg.get("gap_type") == hg.gap_type and pg.get("detected", False) and len(hg.supporting_evidence_ids) > 0
    )
    total_detected = sum(1 for pg in gaps if pg.get("detected", False))
    evidence_alignment_precision = alignment_count / max(1, total_detected)

    return EvidenceMetrics(
        evidence_coverage_per_gap=coverage_per_gap,
        unsupported_gap_rate=round(unsupported_gap_rate, 4),
        gap_without_evidence_rate=round(gap_without_evidence_rate, 4),
        evidence_alignment_precision=round(evidence_alignment_precision, 4),
    )


# ---------------------------------------------------------------------------
# Grid search over weight candidates
# ---------------------------------------------------------------------------


@dataclass
class WeightCandidateResult:
    candidate_index: int
    weights: dict[str, float]
    weight_type: str
    spearman: float | None = None
    mae: float | None = None
    rmse: float | None = None
    gap_f1: float | None = None
    fp_rate: float | None = None
    fn_rate: float | None = None
    predicted_scores: list[float] = field(default_factory=list)
    human_labels: list[float] = field(default_factory=list)


def _compute_scores_for_entries(
    entries: list[GapDiagnosisGoldenEntry],
    weights: dict[str, float],
    weight_type: str,
) -> tuple[list[float], list[float]]:
    predicted: list[float] = []
    human_labels: list[float] = []
    for e in entries:
        for hg in e.human_labeled_gaps:
            gap_type_str = hg.gap_type
            try:
                gt = GapType(gap_type_str)
            except ValueError:
                continue

            if weight_type == "severity":
                sev_feats = extract_gap_severity_features(
                    gap_type=gt,
                    evidence_items=e.accepted_evidence_items_snapshot,
                    accepted_evidence_items=e.accepted_evidence_items_snapshot,
                    rejected_evidence_items=[],
                    claims=e.accepted_claims_snapshot,
                    evidence_validation=None,
                    collection_metrics=None,
                )
                label = hg.human_label_severity
                feat_dict = sev_feats.model_dump(mode="json")
            else:
                conf_feats = extract_gap_confidence_features(
                    gap_type=gt,
                    evidence_items=e.accepted_evidence_items_snapshot,
                    accepted_evidence_items=e.accepted_evidence_items_snapshot,
                    claims=e.accepted_claims_snapshot,
                    collection_metrics=None,
                    extraction_metrics=None,
                )
                label = hg.human_label_confidence
                feat_dict = conf_feats.model_dump(mode="json")

            score = _compute_weighted_score(feat_dict, weights)
            score = _compute_weighted_score(feat_dict, weights)
            predicted.append(score)
            human_labels.append(label)
    return predicted, human_labels


def _evaluate_weight_candidates(
    entries: list[GapDiagnosisGoldenEntry],
    candidate_weights: list[dict[str, float]],
    weight_type: str,
) -> list[WeightCandidateResult]:
    results: list[WeightCandidateResult] = []
    for idx, weights in enumerate(candidate_weights):
        predicted, human_labels = _compute_scores_for_entries(entries, weights, weight_type)
        if len(predicted) < 3:
            results.append(
                WeightCandidateResult(
                    candidate_index=idx,
                    weights=dict(weights),
                    weight_type=weight_type,
                    spearman=None,
                    mae=None,
                    rmse=None,
                )
            )
            continue

        correlation = _spearman(predicted, human_labels)
        abs_errors = [abs(p - h) for p, h in zip(predicted, human_labels, strict=True)]
        mae = sum(abs_errors) / len(abs_errors)
        sq_errors = [(p - h) ** 2 for p, h in zip(predicted, human_labels, strict=True)]
        rmse = math.sqrt(sum(sq_errors) / len(sq_errors))

        results.append(
            WeightCandidateResult(
                candidate_index=idx,
                weights=dict(weights),
                weight_type=weight_type,
                spearman=round(correlation, 4),
                mae=round(mae, 4),
                rmse=round(rmse, 4),
                predicted_scores=predicted,
                human_labels=human_labels,
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
            f"Threshold at P{int(percentile)} of predicted score distribution ({n} entries). "
            f"Distribution: mean={distribution['mean']}, p5={distribution['p5']}, p50={distribution['p50']}. "
            f"Scores below P{int(percentile)} are excluded from production."
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
        mae = sum(abs_errors) / n
        sq_errors = [(a - h) ** 2 for a, h in zip(adjusted, human_labels, strict=True)]
        rmse = math.sqrt(sum(sq_errors) / n)
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


def _calibrate_min_evidence_coverage(
    entries: list[GapDiagnosisGoldenEntry],
) -> dict[str, Any]:
    ratios: list[float] = []
    for e in entries:
        for hg in e.human_labeled_gaps:
            total = max(1, len(e.accepted_evidence_items_snapshot))
            supporting = len(hg.supporting_evidence_ids)
            ratios.append(min(1.0, supporting / total))

    if not ratios:
        return {"recommended_min_coverage": 0.10, "method": "insufficient_data", "n": 0}

    ratios_sorted = sorted(ratios)
    n = len(ratios_sorted)
    p25_idx = max(0, int(n * 0.25) - 1)
    p25 = ratios_sorted[p25_idx]
    p10_idx = max(0, int(n * 0.10) - 1)
    p10 = ratios_sorted[p10_idx]

    recommended = max(0.10, round(p25, 2))

    return {
        "p25_support_ratio": round(p25, 4),
        "p10_support_ratio": round(p10, 4),
        "mean": round(sum(ratios) / len(ratios), 4),
        "median": round(ratios_sorted[len(ratios_sorted) // 2], 4),
        "n": n,
        "recommended_min_coverage": recommended,
        "method": "baseline_measurement_p25_percentile",
        "explanation": (
            f"Minimum evidence coverage at P25 of support ratio distribution ({n} entries). "
            f"P25={p25:.4f}, P10={p10:.4f}. Recommended={recommended}. "
            f"Coverage below this threshold triggers NEEDS_MORE_EVIDENCE status."
        ),
    }


# ---------------------------------------------------------------------------
# Production readiness check
# ---------------------------------------------------------------------------


def _check_gap_diagnosis_production_ready(
    labeled_entry_count: int,
    gap_label_count: int,
    coverage_by_type: dict[str, float],
    sev_metrics: SeverityMetrics | None,
    conf_metrics: ConfidenceMetrics | None,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []

    if labeled_entry_count < MIN_LABELED_ENTRIES:
        blockers.append(f"Labeled entries ({labeled_entry_count}) < minimum ({MIN_LABELED_ENTRIES})")
    if gap_label_count < MIN_LABELED_ENTRIES:
        blockers.append(f"Gap labels ({gap_label_count}) < minimum ({MIN_LABELED_ENTRIES})")

    if sev_metrics is not None:
        if sev_metrics.correlation is not None and sev_metrics.correlation < MIN_SPEARMAN:
            blockers.append(f"Severity spearman ({sev_metrics.correlation:.4f}) < minimum ({MIN_SPEARMAN})")
        if sev_metrics.mae is not None and sev_metrics.mae > MAX_MAE:
            blockers.append(f"Severity MAE ({sev_metrics.mae:.4f}) > maximum ({MAX_MAE})")

    if conf_metrics is not None:
        if conf_metrics.correlation is not None and conf_metrics.correlation < MIN_SPEARMAN:
            blockers.append(f"Confidence spearman ({conf_metrics.correlation:.4f}) < minimum ({MIN_SPEARMAN})")
        if conf_metrics.mae is not None and conf_metrics.mae > MAX_MAE:
            blockers.append(f"Confidence MAE ({conf_metrics.mae:.4f}) > maximum ({MAX_MAE})")

    if coverage_by_type:
        gap_types_present = sum(1 for c in coverage_by_type.values() if c > 0)
        total_gap_types = max(1, len(coverage_by_type))
        coverage_ratio = gap_types_present / total_gap_types
        if coverage_ratio < MIN_CALIBRATION_COVERAGE:
            blockers.append(f"Gap type coverage ({coverage_ratio:.2f}) < minimum ({MIN_CALIBRATION_COVERAGE})")

    return len(blockers) == 0, blockers


# ---------------------------------------------------------------------------
# Baseline calibration orchestrator
# ---------------------------------------------------------------------------


@dataclass
class GapDiagnosisCalibrationResult:
    calibration_status: str
    production_allowed: bool
    golden_set_size: int
    has_human_labels: bool
    label_coverage: dict[str, Any]
    severity_candidates: list[WeightCandidateResult] = field(default_factory=list)
    confidence_candidates: list[WeightCandidateResult] = field(default_factory=list)
    best_severity_candidate_index: int | None = None
    best_confidence_candidate_index: int | None = None
    best_severity_metrics: SeverityMetrics | None = None
    best_confidence_metrics: ConfidenceMetrics | None = None
    gap_detection_metrics: GapDetectionMetrics | None = None
    evidence_metrics: EvidenceMetrics | None = None
    production_threshold: dict[str, Any] | None = None
    uncertainty_penalty: dict[str, Any] | None = None
    min_evidence_coverage: dict[str, Any] | None = None
    production_blockers: list[str] | None = None
    report: str = ""


def _format_report(result: GapDiagnosisCalibrationResult) -> str:
    lines = [
        "=" * 72,
        "GAP DIAGNOSIS BASELINE — CALIBRATION REPORT",
        "=" * 72,
        "",
        f"Golden set size: {result.golden_set_size}",
        f"Has human labels: {result.has_human_labels}",
        f"Calibration status: {result.calibration_status}",
        f"Production allowed: {result.production_allowed}",
    ]
    lc = result.label_coverage
    lines.append(f"Entries with labels: {lc.get('total_entries_with_labels', 0)}")
    lines.append(f"Total gap labels: {lc.get('total_gap_labels', 0)}")
    lines.append(f"Gap type coverage: {lc.get('gap_type_coverage', {})}")
    if result.production_blockers:
        lines.append("Blockers:")
        for b in result.production_blockers:
            lines.append(f"  - {b}")
    lines.append("")

    if result.severity_candidates:
        lines.append("--- Severity weight candidates ---")
        for c in result.severity_candidates:
            lines.append(f"  Candidate {c.candidate_index}: spearman={c.spearman}, mae={c.mae}, rmse={c.rmse}")
        if result.best_severity_candidate_index is not None:
            bc = result.severity_candidates[result.best_severity_candidate_index]
            lines.append(f"  Best severity: candidate {result.best_severity_candidate_index} — weights={bc.weights}")
    if result.best_severity_metrics:
        sm = result.best_severity_metrics
        lines.append(
            f"  Severity metrics: correlation={sm.correlation}, mae={sm.mae}, "
            f"rmse={sm.rmse}, calibration_error={sm.calibration_error}"
        )
    lines.append("")

    if result.confidence_candidates:
        lines.append("--- Confidence weight candidates ---")
        for c in result.confidence_candidates:
            lines.append(f"  Candidate {c.candidate_index}: spearman={c.spearman}, mae={c.mae}, rmse={c.rmse}")
        if result.best_confidence_candidate_index is not None:
            bc = result.confidence_candidates[result.best_confidence_candidate_index]
            lines.append(
                f"  Best confidence: candidate {result.best_confidence_candidate_index} — weights={bc.weights}"
            )
    if result.best_confidence_metrics:
        cm = result.best_confidence_metrics
        lines.append(
            f"  Confidence metrics: correlation={cm.correlation}, mae={cm.mae}, "
            f"rmse={cm.rmse}, uncertainty_error_relationship={cm.uncertainty_error_relationship}"
        )
    lines.append("")

    if result.gap_detection_metrics:
        d = result.gap_detection_metrics
        lines.append("--- Gap detection ---")
        lines.append(f"  False positive rate: {d.false_positive_rate}")
        lines.append(f"  False negative rate: {d.false_negative_rate}")
        if d.gap_type_f1:
            avg_f1 = sum(d.gap_type_f1.values()) / max(1, len(d.gap_type_f1))
            lines.append(f"  Average F1 by gap type: {avg_f1:.4f}")
    lines.append("")

    if result.production_threshold:
        lines.append("--- Production threshold ---")
        lines.append(f"  Threshold: {result.production_threshold.get('threshold')}")
        lines.append(f"  Method: {result.production_threshold.get('method')}")
    if result.uncertainty_penalty:
        lines.append("--- Uncertainty penalty ---")
        lines.append(f"  Best penalty: {result.uncertainty_penalty.get('best_penalty')}")
        lines.append(f"  Best MAE: {result.uncertainty_penalty.get('best_mae')}")
    if result.min_evidence_coverage:
        lines.append("--- Minimum evidence coverage ---")
        lines.append(f"  Recommended: {result.min_evidence_coverage.get('recommended_min_coverage')}")
        lines.append(f"  Method: {result.min_evidence_coverage.get('method')}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def run_gap_diagnosis_baseline_calibration(
    golden_path: Path | None = None,
    auto_generate_synthetic: bool = True,
) -> GapDiagnosisCalibrationResult:
    path = golden_path or _GOLDEN_SET_PATH
    entries = load_gap_diagnosis_golden_set(path)

    if not entries and auto_generate_synthetic:
        logger.info("Golden set empty — generating synthetic entries ...")
        entries = generate_synthetic_gap_diagnosis_golden_set(count=60)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"startups": [e.model_dump(mode="json") for e in entries]},
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"Saved {len(entries)} synthetic entries to {path}")
        # Reload to ensure round-trip consistency
        entries = load_gap_diagnosis_golden_set(path)

    if not entries:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            label_coverage={
                "total_entries_with_labels": 0,
                "total_gap_labels": 0,
                "gap_type_coverage": {},
            },
            production_blockers=["Golden set is empty. Add human-labeled entries."],
        )
        result.report = _format_report(result)
        return result

    has_labels = check_gap_diagnosis_labels_exist(entries)
    label_coverage = count_labeled_gaps(entries)
    labeled_entry_count = label_coverage["total_entries_with_labels"]
    total_gap_labels = label_coverage["total_gap_labels"]

    if not has_labels or labeled_entry_count < 3:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=len(entries),
            has_human_labels=has_labels,
            label_coverage=label_coverage,
            production_blockers=[
                f"Insufficient labeled entries ({labeled_entry_count}). Need at least {MIN_LABELED_ENTRIES}."
            ],
        )
        result.report = _format_report(result)
        return result

    severity_candidates = _evaluate_weight_candidates(entries, CANDIDATE_SEVERITY_WEIGHTS, "severity")
    confidence_candidates = _evaluate_weight_candidates(entries, CANDIDATE_CONFIDENCE_WEIGHTS, "confidence")

    best_sev_idx = _select_best_candidate(severity_candidates)
    best_conf_idx = _select_best_candidate(confidence_candidates)

    best_sev_metrics: SeverityMetrics | None = None
    best_conf_metrics: ConfidenceMetrics | None = None
    best_sev_weights = CANDIDATE_SEVERITY_WEIGHTS[0]
    best_conf_weights = CANDIDATE_CONFIDENCE_WEIGHTS[0]
    best_sev_predicted: list[float] = []
    best_sev_human: list[float] = []
    best_conf_predicted: list[float] = []
    best_conf_human: list[float] = []
    sev_uncertainties: list[float] = []
    conf_uncertainties: list[float] = []

    if best_sev_idx is not None:
        bc = severity_candidates[best_sev_idx]
        best_sev_weights = bc.weights
        best_sev_predicted, best_sev_human = _compute_scores_for_entries(entries, best_sev_weights, "severity")
        if len(best_sev_predicted) >= 3:
            best_sev_metrics = _compute_severity_metrics(best_sev_predicted, best_sev_human)
            sev_uncertainties = [abs(p - h) for p, h in zip(best_sev_predicted, best_sev_human, strict=True)]
    else:
        best_sev_predicted, best_sev_human = _compute_scores_for_entries(entries, best_sev_weights, "severity")
        if len(best_sev_predicted) >= 3:
            best_sev_metrics = _compute_severity_metrics(best_sev_predicted, best_sev_human)

    if best_conf_idx is not None:
        bc = confidence_candidates[best_conf_idx]
        best_conf_weights = bc.weights
        best_conf_predicted, best_conf_human = _compute_scores_for_entries(entries, best_conf_weights, "confidence")
        if len(best_conf_predicted) >= 3:
            best_conf_metrics = _compute_confidence_metrics(
                best_conf_predicted, best_conf_human, conf_uncertainties or [0.0]
            )
    else:
        best_conf_predicted, best_conf_human = _compute_scores_for_entries(entries, best_conf_weights, "confidence")
        if len(best_conf_predicted) >= 3:
            best_conf_metrics = _compute_confidence_metrics(
                best_conf_predicted, best_conf_human, conf_uncertainties or [0.0]
            )

    gap_detection_metrics = _compute_gap_detection_metrics(
        predicted_gaps=[
            {"gap_type": hg.gap_type, "detected": hg.human_label_gap_present}
            for e in entries
            for hg in e.human_labeled_gaps
        ],
        human_labeled_gaps=[hg for e in entries for hg in e.human_labeled_gaps],
        all_gap_types=[g.value for g in GapType],
    )

    evidence_metrics = _compute_evidence_metrics(
        gaps=[
            {"gap_type": hg.gap_type, "detected": hg.human_label_gap_present}
            for e in entries
            for hg in e.human_labeled_gaps
        ],
        human_labeled_gaps=[hg for e in entries for hg in e.human_labeled_gaps],
    )

    production_threshold = None
    if len(best_sev_predicted) >= 3:
        production_threshold = _calibrate_threshold_from_scores(best_sev_predicted, percentile=5.0)

    uncertainty_penalty = None
    if best_sev_metrics is not None and len(best_sev_predicted) >= 3:
        uncertainty_penalty = _calibrate_uncertainty_penalty_from_scores(
            best_sev_predicted,
            best_sev_human,
            sev_uncertainties or [0.0],
        )

    min_evidence_coverage = _calibrate_min_evidence_coverage(entries)

    gap_type_coverage: dict[str, float] = {k: float(v) for k, v in label_coverage.get("gap_type_coverage", {}).items()}
    prod_ready, blockers = _check_gap_diagnosis_production_ready(
        labeled_entry_count=labeled_entry_count,
        gap_label_count=total_gap_labels,
        coverage_by_type=gap_type_coverage,
        sev_metrics=best_sev_metrics,
        conf_metrics=best_conf_metrics,
    )

    # Block production if ALL labels are synthetic (not human-labeled)
    all_synthetic = (
        any(lg.label_source and "synthetic" in lg.label_source.lower() for e in entries for lg in e.human_labeled_gaps)
        if entries
        else False
    )

    if (
        prod_ready
        and has_labels
        and labeled_entry_count >= MIN_LABELED_ENTRIES
        and total_gap_labels >= MIN_LABELED_ENTRIES
    ):
        if all_synthetic:
            calibration_status = "baseline_measured_blocked"
            production_allowed = False
            blockers.append("Labels are synthetic — requires human-labeled data for production")
        else:
            calibration_status = "baseline_measured"
            production_allowed = True
    elif not has_labels:
        calibration_status = "baseline_dataset_insufficient"
        production_allowed = False
    else:
        calibration_status = "baseline_measured_blocked"
        production_allowed = False

    result = GapDiagnosisCalibrationResult(
        calibration_status=calibration_status,
        production_allowed=production_allowed,
        golden_set_size=len(entries),
        has_human_labels=has_labels,
        label_coverage=label_coverage,
        severity_candidates=severity_candidates,
        confidence_candidates=confidence_candidates,
        best_severity_candidate_index=best_sev_idx,
        best_confidence_candidate_index=best_conf_idx,
        best_severity_metrics=best_sev_metrics,
        best_confidence_metrics=best_conf_metrics,
        gap_detection_metrics=gap_detection_metrics,
        evidence_metrics=evidence_metrics,
        production_threshold=production_threshold,
        uncertainty_penalty=uncertainty_penalty,
        min_evidence_coverage=min_evidence_coverage,
        production_blockers=blockers,
    )
    result.report = _format_report(result)
    return result


# ---------------------------------------------------------------------------
# Registry record generation
# ---------------------------------------------------------------------------


def make_gap_diagnosis_baseline_records(
    cal_result: GapDiagnosisCalibrationResult,
) -> list[DecisionCalibrationRecord]:
    from datetime import datetime

    _now = datetime(2026, 6, 18, tzinfo=UTC)

    is_insufficient = cal_result.calibration_status == "baseline_dataset_insufficient"
    is_blocked = cal_result.calibration_status == "baseline_measured_blocked"

    if is_insufficient or is_blocked or not cal_result.production_allowed:
        sev_weights_value = None
        conf_weights_value = None
        threshold_value = None
        penalty_value = None
        coverage_value = None
        status = CalibrationStatus.UNCALIBRATED
        prod = False
        notes = (
            f"Baseline calibration blocked: {cal_result.calibration_status}. "
            f"Golden set: {cal_result.golden_set_size} entries, "
            f"labeled: {cal_result.label_coverage.get('total_entries_with_labels', 0)}. "
            f"Requires >= {MIN_LABELED_ENTRIES} labeled entries with spearman>={MIN_SPEARMAN}, mae<={MAX_MAE}. "
            f"Blockers: {'; '.join(cal_result.production_blockers) if cal_result.production_blockers else 'none'}"
        )
    else:
        sev_weights_value = None
        conf_weights_value = None
        if cal_result.best_severity_candidate_index is not None and cal_result.severity_candidates:
            sev_weights_value = cal_result.severity_candidates[cal_result.best_severity_candidate_index].weights
        if cal_result.best_confidence_candidate_index is not None and cal_result.confidence_candidates:
            conf_weights_value = cal_result.confidence_candidates[cal_result.best_confidence_candidate_index].weights
        threshold_value = cal_result.production_threshold.get("threshold") if cal_result.production_threshold else None
        penalty_value = cal_result.uncertainty_penalty.get("best_penalty") if cal_result.uncertainty_penalty else None
        coverage_value = (
            cal_result.min_evidence_coverage.get("recommended_min_coverage")
            if cal_result.min_evidence_coverage
            else None
        )
        status = CalibrationStatus.BASELINE_MEASURED
        prod = True
        notes = (
            f"Baseline calibration measured: {cal_result.golden_set_size} entries, "
            f"{cal_result.label_coverage.get('total_gap_labels', 0)} gap labels. "
            f"Severity: spearman={cal_result.best_severity_metrics.correlation if cal_result.best_severity_metrics else 'N/A'}, "
            f"mae={cal_result.best_severity_metrics.mae if cal_result.best_severity_metrics else 'N/A'}. "
            f"Confidence: spearman={cal_result.best_confidence_metrics.correlation if cal_result.best_confidence_metrics else 'N/A'}, "
            f"mae={cal_result.best_confidence_metrics.mae if cal_result.best_confidence_metrics else 'N/A'}."
        )

    evidence_source = (
        f"src/evaluation/gap_diagnosis_baseline.py :: run_gap_diagnosis_baseline_calibration -- "
        f"golden_path=data/eval/golden_gap_diagnosis_baseline.json. "
        f"Status: {cal_result.calibration_status}. "
        f"Entries: {cal_result.golden_set_size}, Labels: {cal_result.label_coverage.get('total_gap_labels', 0)}. "
        f"Production: {cal_result.production_allowed}."
    )

    value_origin_base = (
        f"src/evaluation/gap_diagnosis_baseline.py :: run_gap_diagnosis_baseline_calibration -- "
        f"grid search over {len(CANDIDATE_SEVERITY_WEIGHTS)} severity + {len(CANDIDATE_CONFIDENCE_WEIGHTS)} confidence candidates "
        f"on {cal_result.golden_set_size} golden entries. "
    )

    sev_origin = f"{value_origin_base}Best severity candidate: {cal_result.best_severity_candidate_index}."
    conf_origin = f"{value_origin_base}Best confidence candidate: {cal_result.best_confidence_candidate_index}."

    return [
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.severity_weights",
            decision_name="Gap Diagnosis: Per-Feature Severity Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=sev_weights_value,
            metric_name="gap_diagnosis_severity_weights",
            value_origin=sev_origin,
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=status,
            production_allowed=prod,
            owner="team-diagnosis",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.confidence_weights",
            decision_name="Gap Diagnosis: Per-Feature Confidence Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=conf_weights_value,
            metric_name="gap_diagnosis_confidence_weights",
            value_origin=conf_origin,
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=status,
            production_allowed=prod,
            owner="team-diagnosis",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.production_threshold",
            decision_name="Gap Diagnosis: Maximum Severity for Production",
            decision_type=DecisionType.THRESHOLD,
            current_value=threshold_value,
            metric_name="gap_diagnosis_production_threshold",
            value_origin=f"src/evaluation/gap_diagnosis_baseline.py :: _calibrate_threshold_from_scores -- percentile of severity distribution from {cal_result.golden_set_size} entries.",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=status,
            production_allowed=prod,
            owner="team-diagnosis",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.uncertainty_penalty",
            decision_name="Gap Diagnosis: Uncertainty Penalty Multiplier",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=penalty_value,
            metric_name="gap_diagnosis_uncertainty_penalty",
            value_origin=f"src/evaluation/gap_diagnosis_baseline.py :: _calibrate_uncertainty_penalty_from_scores -- sensitivity analysis over {cal_result.golden_set_size} entries.",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=status,
            production_allowed=prod,
            owner="team-diagnosis",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.minimum_evidence_coverage",
            decision_name="Gap Diagnosis: Minimum Evidence Coverage Ratio",
            decision_type=DecisionType.THRESHOLD,
            current_value=coverage_value,
            metric_name="gap_diagnosis_min_evidence_coverage",
            value_origin=f"src/evaluation/gap_diagnosis_baseline.py :: _calibrate_min_evidence_coverage -- baseline measurement from {cal_result.golden_set_size} entries.",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=status,
            production_allowed=prod,
            owner="team-diagnosis",
            last_calibrated_at=_now,
            evidence_source=evidence_source,
            notes=notes,
        ),
    ]


__all__ = [
    "CANDIDATE_CONFIDENCE_WEIGHTS",
    "CANDIDATE_SEVERITY_WEIGHTS",
    "GapDiagnosisCalibrationMetrics",
    "GapDiagnosisCalibrationResult",
    "GapDiagnosisGoldenEntry",
    "HumanLabeledGap",
    "MAX_FP_RATE",
    "MAX_MAE",
    "MIN_LABELED_ENTRIES",
    "MIN_SPEARMAN",
    "SeverityMetrics",
    "ConfidenceMetrics",
    "WeightCandidateResult",
    "check_gap_diagnosis_labels_exist",
    "count_labeled_gaps",
    "generate_synthetic_gap_diagnosis_golden_set",
    "load_gap_diagnosis_golden_set",
    "make_gap_diagnosis_baseline_records",
    "run_gap_diagnosis_baseline_calibration",
]
